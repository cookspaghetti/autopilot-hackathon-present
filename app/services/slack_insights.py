"""Verified Slack mention ingress for the management insight workflow."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..models.command_center import (
    SlackInsightEventRecord,
    SlackInsightThreadSession,
)
from .supabase import SupabaseClient
from .supervity import SupervityClient

log = logging.getLogger(__name__)


class SlackInsightConfigurationError(RuntimeError):
    pass


class SlackInsightPayloadError(ValueError):
    pass


class SlackInsightRouteError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class SlackInsightSettings:
    signing_secret: str
    workflow_id: str
    workspace_key: str = "default"
    signature_max_age_seconds: int = 300

    @classmethod
    def from_environment(cls) -> SlackInsightSettings:
        signing_secret = os.getenv("SLACK_SIGNING_SECRET", "").strip()
        workflow_id = os.getenv("SUPERVITY_INSIGHT_WORKFLOW_ID", "").strip()
        missing = []
        if not signing_secret:
            missing.append("SLACK_SIGNING_SECRET")
        if not workflow_id:
            missing.append("SUPERVITY_INSIGHT_WORKFLOW_ID")
        if missing:
            raise SlackInsightConfigurationError(
                f"Missing backend configuration: {', '.join(missing)}"
            )
        return cls(
            signing_secret=signing_secret,
            workflow_id=workflow_id,
            workspace_key=(
                os.getenv("SLACK_INSIGHT_WORKSPACE_KEY", "").strip() or "default"
            ),
            signature_max_age_seconds=int(
                os.getenv("SLACK_SIGNATURE_MAX_AGE_SECONDS", "").strip() or "300"
            ),
        )


@dataclass(frozen=True, slots=True)
class SlackInsightEvent:
    event_id: str
    channel_id: str
    message_ts: str
    thread_ts: str
    user_id: str
    text: str
    event_type: str = "app_mention"

    def workflow_inputs(
        self,
        *,
        conversation_id: str = "",
        turn_number: int = 1,
        prior_intent: str = "",
        conversation_intent: str = "",
        interaction_mode: str = "initial",
        conversation_history: list[dict[str, str]] | None = None,
    ) -> dict[str, str]:
        return {
            "channel_id": self.channel_id,
            "message_ts": self.message_ts,
            "thread_ts": self.thread_ts,
            "user_id": self.user_id,
            "text": self.text,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "conversation_id": conversation_id,
            "turn_number": str(turn_number),
            "prior_intent": prior_intent,
            "conversation_intent": conversation_intent,
            "interaction_mode": interaction_mode,
            "conversation_history": json.dumps(
                conversation_history or [],
                separators=(",", ":"),
            ),
        }


@dataclass(frozen=True, slots=True)
class SlackInsightTurn:
    intent: str | None
    interaction_mode: str
    normalized_text: str


def verify_slack_signature(
    *,
    raw_body: bytes,
    timestamp: str | None,
    signature: str | None,
    signing_secret: str,
    now: float | None = None,
    max_age_seconds: int = 300,
) -> bool:
    """Validate Slack's v0 request signature and replay window."""
    if not timestamp or not signature or not signing_secret:
        return False
    try:
        request_time = int(timestamp)
    except ValueError:
        return False
    current_time = time.time() if now is None else now
    if abs(current_time - request_time) > max_age_seconds:
        return False
    base = b"v0:" + timestamp.encode("utf-8") + b":" + raw_body
    digest = hmac.new(
        signing_secret.encode("utf-8"),
        base,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(f"v0={digest}", signature)


def parse_slack_insight_event(payload: Mapping[str, Any]) -> SlackInsightEvent | None:
    """Normalize an app mention or a human reply inside an existing thread."""
    if payload.get("type") != "event_callback":
        return None
    raw_event = payload.get("event")
    if not isinstance(raw_event, Mapping):
        return None
    raw_event_type = str(raw_event.get("type") or "").strip()
    if raw_event_type == "app_mention":
        event_type = "app_mention"
    elif raw_event_type == "message":
        if raw_event.get("channel_type") not in {None, "channel"}:
            return None
        if not str(raw_event.get("thread_ts") or "").strip():
            return None
        event_type = "thread_reply"
    else:
        return None
    if (
        raw_event.get("bot_id")
        or raw_event.get("bot_profile")
        or raw_event.get("subtype")
    ):
        return None

    channel_id = _required_text(raw_event, "channel")
    message_ts = _required_text(raw_event, "ts")
    user_id = _required_text(raw_event, "user")
    text = _required_text(raw_event, "text")
    thread_ts = str(raw_event.get("thread_ts") or message_ts).strip()
    event_id = str(payload.get("event_id") or "").strip()
    if not event_id:
        event_id = "derived:" + hashlib.sha256(
            f"{channel_id}|{message_ts}|{user_id}".encode("utf-8")
        ).hexdigest()
    return SlackInsightEvent(
        event_id=event_id,
        channel_id=channel_id,
        message_ts=message_ts,
        thread_ts=thread_ts,
        user_id=user_id,
        text=text,
        event_type=event_type,
    )


def resolve_slack_insight_turn(
    text: str,
    *,
    prior_intent: str | None = None,
) -> SlackInsightTurn:
    """Resolve a deterministic domain intent and conversational follow-up mode."""
    normalized_text = re.sub(r"<@[A-Z0-9]+>", " ", text.upper())
    normalized_text = re.sub(r"\s+", " ", normalized_text).strip().lower()
    intent_patterns = (
        ("inventory_risk", r"\b(inventory|stock|sku|shortage|safety stock|reorder)\b"),
        (
            "supplier_risk",
            r"\b(supplier|vendor|sole source|tier[- ]?[123]|supplier risk)\b",
        ),
        (
            "incident_status",
            r"\b(incident|disruption|case status|incident status|open cases?)\b",
        ),
        (
            "daily_briefing",
            r"\b(daily briefing|briefing|today|daily summary|overview)\b",
        ),
    )
    explicit_intent = next(
        (
            name
            for name, pattern in intent_patterns
            if re.search(pattern, normalized_text)
        ),
        None,
    )
    intent = explicit_intent or prior_intent
    follow_up_patterns = (
        (
            "decision_support",
            r"\b(help me decide|decide|compare|trade[- ]?offs?|best (choice|option))\b",
        ),
        (
            "recommended_action",
            r"\b(recommend(?:ed|ation)?|what should (we|i) do|next (action|step)|actions?)\b",
        ),
        ("explain", r"\b(why|explain|reason|risk factors?|how did)\b"),
        (
            "affected_scope",
            r"\b(affected|impact(?:ed)?|which (orders?|incidents?|suppliers?|skus?))\b",
        ),
    )
    interaction_mode = next(
        (
            name
            for name, pattern in follow_up_patterns
            if re.search(pattern, normalized_text)
        ),
        None,
    )
    if interaction_mode is None:
        if explicit_intent and prior_intent and explicit_intent != prior_intent:
            interaction_mode = "intent_switch"
        elif prior_intent:
            interaction_mode = "follow_up"
        elif explicit_intent:
            interaction_mode = "initial"
        else:
            interaction_mode = "help"
    return SlackInsightTurn(
        intent=intent,
        interaction_mode=interaction_mode,
        normalized_text=normalized_text,
    )


async def process_slack_insight_event(
    event: SlackInsightEvent,
    *,
    settings: SlackInsightSettings | None = None,
    supabase_client: SupabaseClient | None = None,
    supervity_client: SupervityClient | None = None,
    workflow_envs: Mapping[str, str] | None = None,
    session_factory: Callable[[], Session] = SessionLocal,
) -> str:
    """Deduplicate, authorize the route, and trigger the saved insight workflow."""
    resolved_settings = settings or SlackInsightSettings.from_environment()
    db = session_factory()
    record: SlackInsightEventRecord | None = None
    try:
        duplicate = db.execute(
            select(SlackInsightEventRecord).where(
                (SlackInsightEventRecord.event_id == event.event_id)
                | (
                    (SlackInsightEventRecord.channel_id == event.channel_id)
                    & (SlackInsightEventRecord.message_ts == event.message_ts)
                )
            )
        ).scalars().first()
        if duplicate is not None:
            return "duplicate"
        conversation_id = _conversation_id(
            resolved_settings.workspace_key,
            event.channel_id,
            event.thread_ts,
        )
        session = db.get(SlackInsightThreadSession, conversation_id)
        if event.event_type == "thread_reply" and (
            session is None or session.status != "active"
        ):
            return "ignored"
        record = SlackInsightEventRecord(
            event_id=event.event_id,
            channel_id=event.channel_id,
            message_ts=event.message_ts,
            thread_ts=event.thread_ts,
            user_id=event.user_id,
            message_text=event.text,
            event_type=event.event_type,
            conversation_id=conversation_id,
            status="received",
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return "duplicate"

        route_client = supabase_client or SupabaseClient.from_environment()
        rows = await route_client.fetch_rows(
            "channel_routes",
            select="destination_id,channel_name",
            filters={
                "workspace_key": f"eq.{resolved_settings.workspace_key}",
                "route_key": "eq.management_insights",
                "provider": "eq.slack",
                "enabled": "is.true",
            },
            limit=2,
        )
        if len(rows) != 1 or not str(rows[0].get("destination_id") or "").strip():
            raise SlackInsightRouteError(
                "Expected exactly one enabled management_insights Slack route"
            )
        expected_channel = str(rows[0]["destination_id"]).strip()
        if not hmac.compare_digest(expected_channel, event.channel_id):
            raise SlackInsightRouteError(
                "Slack mention did not originate from the configured insight channel"
            )

        prior_intent = session.current_intent if session is not None else None
        turn = resolve_slack_insight_turn(event.text, prior_intent=prior_intent)
        if session is None:
            session = SlackInsightThreadSession(
                conversation_id=conversation_id,
                workspace_key=resolved_settings.workspace_key,
                channel_id=event.channel_id,
                thread_ts=event.thread_ts,
                root_user_id=event.user_id,
                status="active",
            )
            db.add(session)
        turn_number = int(session.turn_count or 0) + 1
        recent_messages = list(session.recent_messages or [])[-7:]
        recent_messages.append(
            {
                "turn": str(turn_number),
                "event_id": event.event_id,
                "user_id": event.user_id,
                "text": event.text[:1000],
                "intent": turn.intent or "",
                "interaction_mode": turn.interaction_mode,
            }
        )
        session.turn_count = turn_number
        session.current_intent = turn.intent
        session.interaction_mode = turn.interaction_mode
        session.recent_messages = recent_messages
        session.last_event_id = event.event_id
        record.intent = turn.intent
        record.interaction_mode = turn.interaction_mode

        workflow_client = supervity_client or SupervityClient.from_environment()
        resolved_workflow_envs = (
            dict(workflow_envs)
            if workflow_envs is not None
            else _workflow_environment_from_environment()
        )
        handle = await workflow_client.trigger_workflow(
            workflow_id=resolved_settings.workflow_id,
            inputs=event.workflow_inputs(
                conversation_id=conversation_id,
                turn_number=turn_number,
                prior_intent=prior_intent or "",
                conversation_intent=turn.intent or "",
                interaction_mode=turn.interaction_mode,
                conversation_history=recent_messages,
            ),
            envs=resolved_workflow_envs,
        )
        record.status = "triggered"
        record.auto_run_id = handle.run_id
        record.last_error = None
        session.last_auto_run_id = handle.run_id
        db.commit()
        return "triggered"
    except SlackInsightRouteError as exc:
        if record is not None:
            record.status = "rejected"
            record.last_error = str(exc)
            db.commit()
        log.warning("Rejected Slack insight event %s: %s", event.event_id, exc)
        return "rejected"
    except Exception as exc:
        if record is not None:
            record.status = "failed"
            record.last_error = str(exc)[:1000]
            db.commit()
        log.exception("Slack insight event %s failed", event.event_id)
        return "failed"
    finally:
        db.close()


def _required_text(container: Mapping[str, Any], key: str) -> str:
    value = str(container.get(key) or "").strip()
    if not value:
        raise SlackInsightPayloadError(f"Slack event field {key!r} is required")
    return value


def _conversation_id(workspace_key: str, channel_id: str, thread_ts: str) -> str:
    return hashlib.sha256(
        f"{workspace_key}|{channel_id}|{thread_ts}".encode("utf-8")
    ).hexdigest()


def _workflow_environment_from_environment() -> dict[str, str]:
    values = {
        "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN", "").strip(),
        "SUPABASE_URL": os.getenv("SUPABASE_URL", "").strip(),
        "SUPABASE_KEY": (
            os.getenv("SUPABASE_SECRET_KEY", "").strip()
            or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.getenv("SUPABASE_API_KEY", "").strip()
        ),
    }
    missing = [name for name, value in values.items() if not value]
    if missing:
        raise SlackInsightConfigurationError(
            "Missing insight workflow environment: " + ", ".join(missing)
        )
    return values
