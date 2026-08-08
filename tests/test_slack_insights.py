import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.routers.slack_insights as slack_insights_router
from app.core.database import SessionLocal
from app.main import app
from app.models.command_center import (
    SlackInsightEventRecord,
    SlackInsightThreadSession,
)
from app.services.slack_insights import (
    SlackInsightEvent,
    SlackInsightSettings,
    parse_slack_insight_event,
    process_slack_insight_event,
    resolve_slack_insight_turn,
    verify_slack_signature,
)
from app.services.supervity import SupervityRunHandle

pytestmark = pytest.mark.asyncio


def _signed_headers(body: bytes, secret: str, timestamp: int | None = None) -> dict:
    request_timestamp = timestamp or int(time.time())
    base = b"v0:" + str(request_timestamp).encode() + b":" + body
    digest = hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()
    return {
        "x-slack-request-timestamp": str(request_timestamp),
        "x-slack-signature": f"v0={digest}",
        "content-type": "application/json",
    }


async def test_slack_url_verification_is_public_but_signature_protected(
    monkeypatch,
) -> None:
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "signing-secret")
    monkeypatch.setenv("SUPERVITY_INSIGHT_WORKFLOW_ID", "INSIGHT-WORKFLOW")
    body = json.dumps(
        {"type": "url_verification", "challenge": "challenge-123"}
    ).encode()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/command-center/slack/events",
            content=body,
            headers=_signed_headers(body, "signing-secret"),
        )
        rejected = await client.post(
            "/api/command-center/slack/events",
            content=body,
            headers={
                **_signed_headers(body, "wrong-secret"),
                "x-slack-signature": "v0=invalid",
            },
        )
    assert response.status_code == 200
    assert response.json() == {"challenge": "challenge-123"}
    assert rejected.status_code == 401


async def test_app_mention_is_acknowledged_and_dispatched(monkeypatch) -> None:
    monkeypatch.setenv("SLACK_SIGNING_SECRET", "signing-secret")
    monkeypatch.setenv("SUPERVITY_INSIGHT_WORKFLOW_ID", "INSIGHT-WORKFLOW")
    captured: list[SlackInsightEvent] = []

    async def fake_process(event: SlackInsightEvent, **_kwargs) -> str:
        captured.append(event)
        return "triggered"

    monkeypatch.setattr(slack_insights_router, "process_slack_insight_event", fake_process)
    payload = {
        "type": "event_callback",
        "event_id": "Ev-test-1",
        "event": {
            "type": "app_mention",
            "channel": "C-INSIGHT",
            "ts": "1720000000.001",
            "thread_ts": "1720000000.000",
            "user": "U-MANAGER",
            "text": "<@U-BOT> show inventory risk",
        },
    }
    body = json.dumps(payload).encode()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(
            "/api/command-center/slack/events",
            content=body,
            headers=_signed_headers(body, "signing-secret"),
        )
    assert response.status_code == 200
    assert response.json() == {"ok": True, "event_id": "Ev-test-1"}
    assert len(captured) == 1
    assert captured[0].thread_ts == "1720000000.000"
    assert captured[0].text == "<@U-BOT> show inventory risk"


async def test_signature_replay_window_and_bot_events_fail_closed() -> None:
    body = b'{"type":"event_callback"}'
    old_timestamp = 1_700_000_000
    headers = _signed_headers(body, "secret", old_timestamp)
    assert not verify_slack_signature(
        raw_body=body,
        timestamp=headers["x-slack-request-timestamp"],
        signature=headers["x-slack-signature"],
        signing_secret="secret",
        now=old_timestamp + 301,
    )


async def test_only_threaded_human_messages_become_follow_up_events() -> None:
    payload = {
        "type": "event_callback",
        "event_id": "Ev-thread-1",
        "event": {
            "type": "message",
            "channel_type": "channel",
            "channel": "C-INSIGHT",
            "ts": "1720000001.002",
            "thread_ts": "1720000000.001",
            "user": "U-MANAGER",
            "text": "show the recommended actions",
        },
    }
    event = parse_slack_insight_event(payload)
    assert event is not None
    assert event.event_type == "thread_reply"
    assert event.thread_ts == "1720000000.001"
    assert parse_slack_insight_event(
        {
            **payload,
            "event": {**payload["event"], "thread_ts": None},
        }
    ) is None
    assert parse_slack_insight_event(
        {
            **payload,
            "event": {**payload["event"], "bot_id": "B-SUPERVITY"},
        }
    ) is None


async def test_turn_resolution_inherits_context_and_recognizes_follow_ups() -> None:
    first = resolve_slack_insight_turn("show supplier risk")
    assert first.intent == "supplier_risk"
    assert first.interaction_mode == "initial"

    recommendation = resolve_slack_insight_turn(
        "What should we do about that one?",
        prior_intent=first.intent,
    )
    assert recommendation.intent == "supplier_risk"
    assert recommendation.interaction_mode == "recommended_action"

    switched = resolve_slack_insight_turn(
        "Actually show inventory risk",
        prior_intent=first.intent,
    )
    assert switched.intent == "inventory_risk"
    assert switched.interaction_mode == "intent_switch"
    assert (
        parse_slack_insight_event(
            {
                "type": "event_callback",
                "event": {
                    "type": "app_mention",
                    "channel": "C-INSIGHT",
                    "ts": "1.2",
                    "user": "U-BOT",
                    "text": "ignore me",
                    "bot_id": "B-1",
                },
            }
        )
        is None
    )


async def test_processor_resolves_route_triggers_once_and_records_run() -> None:
    event_id = f"Ev-{uuid4().hex}"
    event = SlackInsightEvent(
        event_id=event_id,
        channel_id="C-INSIGHT",
        message_ts="1720000000.001",
        thread_ts="1720000000.001",
        user_id="U-MANAGER",
        text="daily briefing",
    )

    class FakeSupabase:
        async def fetch_rows(self, table, **kwargs):
            assert table == "channel_routes"
            assert kwargs["filters"]["route_key"] == "eq.management_insights"
            return [{"destination_id": "C-INSIGHT", "channel_name": "insight"}]

    class FakeSupervity:
        def __init__(self):
            self.calls = []

        async def trigger_workflow(self, *, workflow_id, inputs, envs):
            self.calls.append((workflow_id, inputs, envs))
            return SupervityRunHandle(run_id="AUTO-INSIGHT-1", raw_response={})

    supervity = FakeSupervity()
    settings = SlackInsightSettings(
        signing_secret="unused",
        workflow_id="INSIGHT-WORKFLOW",
    )
    first = await process_slack_insight_event(
        event,
        settings=settings,
        supabase_client=FakeSupabase(),
        supervity_client=supervity,
        workflow_envs={
            "SLACK_BOT_TOKEN": "xoxb-test",
            "SUPABASE_URL": "https://supabase.example.test",
            "SUPABASE_KEY": "supabase-test",
        },
    )
    second = await process_slack_insight_event(
        event,
        settings=settings,
        supabase_client=FakeSupabase(),
        supervity_client=supervity,
        workflow_envs={
            "SLACK_BOT_TOKEN": "xoxb-test",
            "SUPABASE_URL": "https://supabase.example.test",
            "SUPABASE_KEY": "supabase-test",
        },
    )
    duplicate_delivery = await process_slack_insight_event(
        SlackInsightEvent(
            event_id=f"Ev-{uuid4().hex}",
            channel_id=event.channel_id,
            message_ts=event.message_ts,
            thread_ts=event.thread_ts,
            user_id=event.user_id,
            text=event.text,
            event_type="thread_reply",
        ),
        settings=settings,
        supabase_client=FakeSupabase(),
        supervity_client=supervity,
        workflow_envs={
            "SLACK_BOT_TOKEN": "xoxb-test",
            "SUPABASE_URL": "https://supabase.example.test",
            "SUPABASE_KEY": "supabase-test",
        },
    )
    assert first == "triggered"
    assert second == "duplicate"
    assert duplicate_delivery == "duplicate"
    assert len(supervity.calls) == 1
    assert supervity.calls[0][0] == "INSIGHT-WORKFLOW"
    assert supervity.calls[0][1]["event_id"] == event_id
    assert supervity.calls[0][1]["conversation_intent"] == "daily_briefing"
    assert supervity.calls[0][1]["interaction_mode"] == "initial"
    assert supervity.calls[0][1]["turn_number"] == "1"
    assert supervity.calls[0][2]["SLACK_BOT_TOKEN"] == "xoxb-test"

    db = SessionLocal()
    try:
        record = db.get(SlackInsightEventRecord, event_id)
        assert record is not None
        assert record.status == "triggered"
        assert record.auto_run_id == "AUTO-INSIGHT-1"
        assert record.intent == "daily_briefing"
        session = db.get(SlackInsightThreadSession, record.conversation_id)
        assert session is not None
        assert session.current_intent == "daily_briefing"
        assert session.turn_count == 1
        assert session.last_auto_run_id == "AUTO-INSIGHT-1"
    finally:
        db.close()


async def test_processor_inherits_known_thread_context_for_unmentioned_reply() -> None:
    thread_ts = f"1720{uuid4().int % 10**10}.001"

    class FakeSupabase:
        async def fetch_rows(self, table, **_kwargs):
            assert table == "channel_routes"
            return [{"destination_id": "C-INSIGHT", "channel_name": "insight"}]

    class FakeSupervity:
        def __init__(self):
            self.calls = []

        async def trigger_workflow(self, *, workflow_id, inputs, envs):
            self.calls.append((workflow_id, inputs, envs))
            return SupervityRunHandle(
                run_id=f"AUTO-{len(self.calls)}",
                raw_response={},
            )

    settings = SlackInsightSettings(
        signing_secret="unused",
        workflow_id="INSIGHT-WORKFLOW",
    )
    workflow_envs = {
        "SLACK_BOT_TOKEN": "xoxb-test",
        "SUPABASE_URL": "https://supabase.example.test",
        "SUPABASE_KEY": "supabase-test",
    }
    supervity = FakeSupervity()
    root = SlackInsightEvent(
        event_id=f"Ev-{uuid4().hex}",
        channel_id="C-INSIGHT",
        message_ts=thread_ts,
        thread_ts=thread_ts,
        user_id="U-MANAGER",
        text="show supplier risk",
    )
    follow_up = SlackInsightEvent(
        event_id=f"Ev-{uuid4().hex}",
        channel_id="C-INSIGHT",
        message_ts=f"{thread_ts[:-3]}002",
        thread_ts=thread_ts,
        user_id="U-MANAGER",
        text="show the recommended actions",
        event_type="thread_reply",
    )

    assert await process_slack_insight_event(
        root,
        settings=settings,
        supabase_client=FakeSupabase(),
        supervity_client=supervity,
        workflow_envs=workflow_envs,
    ) == "triggered"
    assert await process_slack_insight_event(
        follow_up,
        settings=settings,
        supabase_client=FakeSupabase(),
        supervity_client=supervity,
        workflow_envs=workflow_envs,
    ) == "triggered"

    second_inputs = supervity.calls[1][1]
    assert second_inputs["prior_intent"] == "supplier_risk"
    assert second_inputs["conversation_intent"] == "supplier_risk"
    assert second_inputs["interaction_mode"] == "recommended_action"
    assert second_inputs["turn_number"] == "2"
    history = json.loads(second_inputs["conversation_history"])
    assert [item["turn"] for item in history] == ["1", "2"]


async def test_processor_ignores_unmentioned_replies_from_unknown_threads() -> None:
    class NeverCalled:
        async def fetch_rows(self, *_args, **_kwargs):
            raise AssertionError("route lookup should not run")

        async def trigger_workflow(self, **_kwargs):
            raise AssertionError("workflow should not run")

    event = SlackInsightEvent(
        event_id=f"Ev-{uuid4().hex}",
        channel_id="C-INSIGHT",
        message_ts="1999999999.002",
        thread_ts="1999999999.001",
        user_id="U-UNRELATED",
        text="this is ordinary channel conversation",
        event_type="thread_reply",
    )
    result = await process_slack_insight_event(
        event,
        settings=SlackInsightSettings(
            signing_secret="unused",
            workflow_id="INSIGHT-WORKFLOW",
        ),
        supabase_client=NeverCalled(),
        supervity_client=NeverCalled(),
        workflow_envs={},
    )
    assert result == "ignored"
