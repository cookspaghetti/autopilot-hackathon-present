"""Reconcile Supervity-managed integration health from its management API."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from sqlalchemy.orm import Session

from ..domain import utc_now
from ..models.command_center import IntegrationHealthRecord
from .supervity import (
    SupervityAPIError,
    SupervityClient,
    SupervityConfigurationError,
)


@dataclass(frozen=True, slots=True)
class IntegrationHealthReconciliation:
    applied: bool
    error_kind: str | None = None
    error: str | None = None


_MANAGED_INTEGRATIONS = (
    ("supervity-auto", "Supervity Auto", "agent_platform", None),
    ("outlook", "Outlook", "channel", "outlook"),
    ("slack-via-supervity", "Slack", "channel", "slack"),
)


def _remote_list(source: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _remote_text(source: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _integration_key(value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())
    if normalized.startswith("microsoft"):
        normalized = normalized.removeprefix("microsoft")
    if normalized == "slackviasupervity":
        return "slack"
    return normalized


def _record(
    db: Session,
    *,
    integration_id: str,
    name: str,
    category: str,
) -> IntegrationHealthRecord:
    record = (
        db.query(IntegrationHealthRecord)
        .filter(IntegrationHealthRecord.integration_id == integration_id)
        .first()
    )
    if record is None:
        record = IntegrationHealthRecord(
            integration_id=integration_id,
            name=name,
            category=category,
            status="unknown",
            checked_at=utc_now(),
            metadata_json={},
        )
        db.add(record)
    record.name = name
    record.category = category
    return record


def _mark_source_unavailable(db: Session, error: str) -> None:
    now = utc_now()
    for integration_id, name, category, _ in _MANAGED_INTEGRATIONS:
        record = _record(
            db,
            integration_id=integration_id,
            name=name,
            category=category,
        )
        record.status = "degraded"
        record.checked_at = now
        record.last_error = error
        record.metadata_json = {
            **dict(record.metadata_json or {}),
            "status_source": "supervity_integrations_api",
        }
    db.commit()


async def reconcile_supervity_integration_health(
    db: Session,
) -> IntegrationHealthReconciliation:
    """Persist one canonical health view for all Supervity-managed integrations."""
    try:
        payload = await SupervityClient.from_environment().integration_inventory()
    except SupervityConfigurationError as exc:
        # A local/test installation without Supervity configured may still use
        # callback-derived health. Do not erase that evidence.
        return IntegrationHealthReconciliation(
            applied=False,
            error_kind="configuration",
            error=str(exc),
        )
    except SupervityAPIError as exc:
        _mark_source_unavailable(db, str(exc))
        return IntegrationHealthReconciliation(
            applied=False,
            error_kind="api",
            error=str(exc),
        )

    accounts: dict[str, Mapping[str, Any]] = {}
    for item in _remote_list(
        payload, "integrations", "connectedIntegrations", "connected_accounts"
    ):
        key = _integration_key(
            _remote_text(item, "integrationSlug", "integration_slug", "slug")
        )
        if key:
            accounts[key] = item

    action_counts: dict[str, int] = {}
    actions = _remote_list(payload, "userActions", "user_actions", "actions")
    for item in actions:
        group = item.get("group") if isinstance(item.get("group"), Mapping) else item
        key = _integration_key(
            _remote_text(
                group,
                "name",
                "displayName",
                "integrationSlug",
                "integration_slug",
            )
        )
        if key:
            action_counts[key] = action_counts.get(key, 0) + 1

    now = utc_now()
    for integration_id, name, category, account_key in _MANAGED_INTEGRATIONS:
        record = _record(
            db,
            integration_id=integration_id,
            name=name,
            category=category,
        )
        account = accounts.get(account_key) if account_key else None
        connected = account_key is None or account is not None
        record.status = "healthy" if connected else "disconnected"
        record.checked_at = now
        record.last_error = (
            None if connected else f"{name} is not connected in Supervity"
        )
        if connected:
            record.last_success_at = now
        metadata = dict(record.metadata_json or {})
        metadata.update(
            {
                "status_source": "supervity_integrations_api",
                "actions_count": (
                    len(actions)
                    if account_key is None
                    else action_counts.get(account_key, 0)
                ),
            }
        )
        if account_key is not None:
            metadata["auto_account"] = (
                _remote_text(account, "accountIdentifier", "account_identifier")
                if account
                else None
            )
        record.metadata_json = metadata

    db.commit()
    return IntegrationHealthReconciliation(applied=True)
