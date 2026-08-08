"""Supabase-backed, versioned governance policy persistence."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from ..domain import (
    PolicyCondition,
    PolicyDecision,
    PolicyDefinition,
    PolicyEvaluation,
    PolicyMatchMode,
    PolicyOperator,
    to_primitive,
)
from .supabase import SupabaseClient


def _datetime(value: Any, *, default: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    elif default is not None:
        parsed = default
    else:
        parsed = datetime.now(timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def policy_from_row(row: Mapping[str, Any]) -> PolicyDefinition:
    return PolicyDefinition(
        policy_id=str(row["policy_id"]),
        version=int(row["version"]),
        name=str(row["name"]),
        description=str(row["description"]),
        priority=int(row.get("priority") or 0),
        enabled=bool(row.get("enabled")),
        match_mode=PolicyMatchMode(str(row["match_mode"])),
        conditions=tuple(
            PolicyCondition(
                field_path=str(item["field_path"]),
                operator=PolicyOperator(str(item["operator"])),
                value=item.get("value"),
            )
            for item in row.get("conditions") or []
        ),
        decision=PolicyDecision(str(row["decision"])),
        reason_template=str(row["reason_template"]),
        approval_role=(str(row["approval_role"]) if row.get("approval_role") else None),
        parameters=dict(row.get("parameters") or {}),
        required_facts=tuple(str(item) for item in row.get("required_facts") or []),
        action_classes=tuple(str(item) for item in row.get("action_classes") or []),
        owner=str(row.get("owner") or "command_center"),
        change_reason=str(row.get("change_reason") or ""),
        effective_from=_datetime(row.get("effective_from")),
        expires_at=(
            _datetime(row.get("expires_at")) if row.get("expires_at") else None
        ),
        created_at=_datetime(row.get("created_at")),
        updated_at=_datetime(row.get("updated_at")),
    )


def policy_payload(policy: PolicyDefinition) -> dict[str, Any]:
    return {
        "policy_id": policy.policy_id,
        "name": policy.name,
        "description": policy.description,
        "priority": policy.priority,
        "enabled": policy.enabled,
        "match_mode": policy.match_mode.value,
        "conditions": to_primitive(policy.conditions),
        "decision": policy.decision.value,
        "reason_template": policy.reason_template,
        "approval_role": policy.approval_role,
        "parameters": dict(policy.parameters),
        "required_facts": list(policy.required_facts),
        "action_classes": list(policy.action_classes),
        "owner": policy.owner,
        "change_reason": policy.change_reason,
        "effective_from": policy.effective_from.isoformat(),
        "expires_at": policy.expires_at.isoformat() if policy.expires_at else None,
    }


class SupabaseGovernancePolicyStore:
    def __init__(self, client: SupabaseClient) -> None:
        self.client = client

    @classmethod
    def from_environment(cls) -> "SupabaseGovernancePolicyStore":
        return cls(SupabaseClient.from_environment())

    async def list(
        self,
        *,
        include_history: bool = False,
        policy_id: str | None = None,
    ) -> list[PolicyDefinition]:
        filters: dict[str, str] = {
            "order": "priority.desc,policy_id.asc,version.desc",
        }
        if not include_history:
            filters["is_current"] = "eq.true"
        if policy_id:
            filters["policy_id"] = f"eq.{policy_id}"
        rows = await self.client.fetch_rows(
            "governance_policies",
            filters=filters,
        )
        return [policy_from_row(row) for row in rows]

    async def publish(self, policy: PolicyDefinition) -> PolicyDefinition:
        payload = await self.client.call_rpc(
            "publish_governance_policy",
            {"policy_payload": policy_payload(policy)},
        )
        rows: Sequence[Any]
        if isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
            rows = payload
        elif isinstance(payload, Mapping):
            rows = [payload]
        else:
            rows = []
        definitions = [policy_from_row(row) for row in rows if isinstance(row, Mapping)]
        if len(definitions) != 1:
            raise RuntimeError(
                "Supabase policy publication did not return exactly one version"
            )
        return definitions[0]

    async def record_evaluations(
        self,
        evaluations: Sequence[PolicyEvaluation],
    ) -> None:
        if not evaluations:
            return
        rows = [
            {
                "evaluation_id": item.evaluation_id,
                "policy_id": item.policy_id,
                "policy_version": item.policy_version,
                "command_center_run_id": item.run_id,
                "incident_id": item.incident_id,
                "candidate_action_id": item.candidate_action_id,
                "matched": item.matched,
                "decision": item.decision.value,
                "reason": item.reason,
                "reason_code": item.reason_code,
                "facts": dict(item.facts),
                "input_hash": item.input_hash,
                "matched_conditions": list(item.matched_conditions),
                "missing_facts": list(item.missing_facts),
                "approval_role": item.approval_role,
                "evaluated_at": item.evaluated_at.isoformat(),
            }
            for item in evaluations
        ]
        await self.client.insert_rows(
            "governance_policy_evaluations",
            rows,
        )
