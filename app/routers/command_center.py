"""Database-backed Command Center APIs."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping
from urllib.parse import quote
from uuid import uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
)
from fastapi.responses import RedirectResponse
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..core.database import SessionLocal, get_db
from ..domain import (
    EvidenceReference,
    Money,
    PolicyCondition,
    PolicyDecision,
    PolicyDefinition,
    PolicyEvaluation,
    PolicyMatchMode,
    PolicyOperator,
    Severity,
    WorkbenchDecision,
    WorkbenchItem,
    WorkbenchStatus,
    WorkflowRun,
    WorkflowStatus,
    to_primitive,
    utc_now,
)
from ..models.command_center import (
    ActionRecord,
    InsightRecord,
    IntegrationHealthRecord,
    NotificationRecord,
    OperatorResultRecord,
    PolicyDefinitionRecord,
    PolicyEvaluationRecord,
    ResourceReservationRecord,
    WorkbenchItemRecord,
    WorkflowRunRecord,
)
from ..schemas.command_center import (
    ActionComplete,
    ActionCreate,
    ActionRead,
    DashboardSummary,
    InsightCreate,
    InsightRead,
    NotificationRead,
    IntegrationHealthRead,
    OutlookAuthorizationStartRead,
    OutlookPollRead,
    IntegrationHealthUpsert,
    OperatorResultRead,
    OperatorResultSchema,
    PolicyCreate,
    PolicyEvaluateRequest,
    PolicyEvaluateResponse,
    PolicyEvaluationRead,
    PolicyRead,
    PolicyUpdate,
    ResourceReservationCreate,
    ResourceReservationRead,
    SupervityCallbackRequest,
    SupervityActionAuthorizationRequest,
    SupervityActionCompletionRequest,
    SupervityConnectedAccountRead,
    SupervityDecisionCallbackRequest,
    SupervityFormSyncRead,
    SupervityIntegrationActionRead,
    SupervityIntegrationInventoryRead,
    SupervityNotificationCallbackRequest,
    SupervityOperatorResultRequest,
    SupervityRunSyncRead,
    SupervityScheduleRead,
    WorkbenchDecisionRequest,
    WorkbenchItemCreate,
    WorkbenchItemRead,
    WorkflowRunCreate,
    WorkflowRunRead,
    WorkflowRunUpdate,
)
from ..security import get_current_user
from ..services.audit import audit
from ..services.governance_policies import SupabaseGovernancePolicyStore
from ..services.integration_health import reconcile_supervity_integration_health
from ..services.policy_facts import PolicyFactsError, SupabasePolicyFactsLoader
from ..services.outlook import (
    OutlookAPIError,
    OutlookClient,
    OutlookConfigurationError,
)
from ..services.outlook_auth import (
    OutlookAuthorizationError,
    OutlookOAuthConfigurationError,
    OutlookTokenManager,
    outlook_oauth_configuration,
)
from ..services.policy_engine import effective_decision, evaluate_policies, facts_hash
from ..services.procurement_insights import ProcurementInsightService
from ..services.supabase import (
    SupabaseAPIError,
    SupabaseClient,
    SupabaseConfigurationError,
)
from ..services.supervity import (
    SupervityAPIError,
    SupervityClient,
    SupervityConfigurationError,
)
from ..services.supervity_forms import parse_supervity_user_form

router = APIRouter(prefix="/command-center", tags=["Command Center"])

KNOWN_OPERATOR_NAMES = {
    "Intake & Triage Operator",
    "Impact Assessor Operator",
    "Alternative Sourcer Operator",
    "Contract & Policy Guard Operator",
    "Recovery Planner Operator",
    "Portfolio Prioritizer Operator",
    "Executor & Scribe Operator",
}

SUPERVITY_OPERATOR_STEPS = {
    "Intake & Triage": "Intake & Triage Operator",
    "Impact Assessor": "Impact Assessor Operator",
    "Alternative Sourcer": "Alternative Sourcer Operator",
    "Contract & Policy Guard": "Contract & Policy Guard Operator",
    "Recovery Planner": "Recovery Planner Operator",
    "Portfolio Prioritizer": "Portfolio Prioritizer Operator",
    "Executor & Scribe": "Executor & Scribe Operator",
}

SENSITIVE_REMOTE_KEYS = (
    "authorization",
    "credential",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
)

ORGANIZER_INPUT_TABLES = (
    "suppliers",
    "contracts",
    "purchase_order_headers",
    "purchase_order_lines",
    "order_confirmations",
    "inventory_positions",
    "demand_signals",
    "disruption_notices",
    "warehouses",
    "supplier_tiers",
    "shipments",
    "customer_orders",
    "alternative_suppliers",
    "penalties",
)


def _dump(model: Any, *, exclude_unset: bool = False) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", exclude_unset=exclude_unset)
    return json.loads(model.json(exclude_unset=exclude_unset))


def _canonical_hash(value: Any) -> str:
    canonical = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _remote_text(source: Mapping[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _remote_list(source: Mapping[str, Any], *keys: str) -> list[Mapping[str, Any]]:
    for key in keys:
        value = source.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _integration_key(value: str | None) -> str:
    normalized = re.sub(r"[^a-z0-9]", "", (value or "").strip().lower())
    if normalized.startswith("microsoft"):
        normalized = normalized.removeprefix("microsoft")
    return normalized


def _remote_datetime(value: Any, *, default: datetime | None = None) -> datetime:
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, str) and value.strip():
        try:
            return _aware(datetime.fromisoformat(value.strip().replace("Z", "+00:00")))
        except ValueError:
            pass
    return default or utc_now()


def _sanitize_remote(value: Any, *, key: str = "") -> Any:
    normalized_key = key.lower().replace("-", "_")
    if any(part in normalized_key for part in SENSITIVE_REMOTE_KEYS):
        return "[redacted]"
    if isinstance(value, Mapping):
        return {
            str(child_key): _sanitize_remote(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_remote(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize_remote(item) for item in value]
    return value


def _workflow_status_from_supervity(status: str | None) -> WorkflowStatus:
    normalized = (status or "").strip().lower()
    if normalized in {"scheduled", "queued"}:
        return WorkflowStatus.QUEUED
    if normalized in {"running", "in_progress", "in-progress"}:
        return WorkflowStatus.RUNNING
    if normalized in {"waiting", "paused", "awaiting_approval"}:
        return WorkflowStatus.AWAITING_APPROVAL
    if normalized in {"completed", "complete", "succeeded", "success"}:
        return WorkflowStatus.COMPLETED
    if normalized in {"failed", "error"}:
        return WorkflowStatus.FAILED
    if normalized in {"cancelled", "canceled"}:
        return WorkflowStatus.CANCELLED
    return WorkflowStatus.NEEDS_REVIEW


def _operator_status_from_supervity(status: str | None) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {"completed", "complete", "succeeded", "success", "ok"}:
        return "succeeded"
    if normalized in {"no_match", "no-match", "nomatch"}:
        return "no_match"
    if normalized in {"waiting", "paused", "needs_review", "needs-review"}:
        return "needs_review"
    if normalized in {"failed", "error"}:
        return "failed"
    if normalized in {"scheduled", "pending", "queued"}:
        return "pending"
    if normalized in {"skipped", "cancelled", "canceled"}:
        return "skipped"
    return "running"


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item).strip()]


def _safe_evidence(value: Any, *, fallback_time: datetime) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    evidence: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        system = _remote_text(item, "system")
        entity_type = _remote_text(item, "entity_type", "entityType")
        entity_id = _remote_text(item, "entity_id", "entityId")
        if not system or not entity_type or not entity_id:
            continue
        evidence.append(
            {
                "system": system,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "observed_at": _remote_datetime(
                    item.get("observed_at") or item.get("observedAt"),
                    default=fallback_time,
                ).isoformat(),
                "fields": _string_items(item.get("fields")),
                "observed_values": _sanitize_remote(
                    item.get("observed_values") or item.get("observedValues") or {}
                ),
                "uri": _remote_text(item, "uri"),
                "checksum": _remote_text(item, "checksum"),
            }
        )
    return evidence


def _masked_account_label(value: str | None) -> str:
    if not value:
        return "Connected account"
    if "@" in value:
        _, domain = value.rsplit("@", 1)
        return f"••••@{domain}"
    if len(value) <= 4:
        return "••••"
    return f"••••{value[-4:]}"


def _actor_label(user: dict | None) -> str:
    if not user:
        return "system"
    return (
        user.get("email")
        or user.get("preferred_username")
        or user.get("sub")
        or "unknown"
    )


def _policy_domain(
    record: PolicyDefinitionRecord | PolicyDefinition,
) -> PolicyDefinition:
    if isinstance(record, PolicyDefinition):
        return record
    return PolicyDefinition(
        policy_id=record.policy_id,
        name=record.name,
        description=record.description,
        version=record.version,
        priority=record.priority,
        enabled=record.enabled,
        match_mode=PolicyMatchMode(record.match_mode),
        conditions=tuple(
            PolicyCondition(
                field_path=condition["field_path"],
                operator=PolicyOperator(condition["operator"]),
                value=condition.get("value"),
            )
            for condition in record.conditions
        ),
        decision=PolicyDecision(record.decision),
        reason_template=record.reason_template,
        approval_role=record.approval_role,
        parameters=record.parameters or {},
        required_facts=tuple(record.required_facts or []),
        action_classes=tuple(record.action_classes or []),
        owner=record.owner or "command_center",
        change_reason=record.change_reason or "",
        effective_from=(
            _aware(record.effective_from) if record.effective_from else None
        ),
        expires_at=_aware(record.expires_at) if record.expires_at else None,
        created_at=_aware(record.created_at),
        updated_at=_aware(record.updated_at),
    )


def _policy_read(record: PolicyDefinitionRecord | PolicyDefinition) -> PolicyRead:
    policy = _policy_domain(record)
    return PolicyRead(
        policy_id=policy.policy_id,
        name=policy.name,
        description=policy.description,
        version=policy.version,
        priority=policy.priority,
        enabled=policy.enabled,
        match_mode=policy.match_mode,
        conditions=to_primitive(policy.conditions),
        decision=policy.decision,
        reason_template=policy.reason_template,
        approval_role=policy.approval_role,
        parameters=policy.parameters,
        required_facts=list(policy.required_facts),
        action_classes=list(policy.action_classes),
        owner=policy.owner,
        change_reason=policy.change_reason,
        effective_from=policy.effective_from,
        expires_at=policy.expires_at,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


def _supabase_policy_store_enabled() -> bool:
    return os.getenv("COMMAND_CENTER_POLICY_STORE", "supabase").strip().lower() == (
        "supabase"
    )


async def _load_policy_definitions(
    db: Session,
    *,
    include_history: bool = False,
    policy_id: str | None = None,
) -> list[PolicyDefinition]:
    if _supabase_policy_store_enabled():
        return await SupabaseGovernancePolicyStore.from_environment().list(
            include_history=include_history,
            policy_id=policy_id,
        )
    query = db.query(PolicyDefinitionRecord)
    if not include_history:
        query = query.filter(PolicyDefinitionRecord.is_current.is_(True))
    if policy_id:
        query = query.filter(PolicyDefinitionRecord.policy_id == policy_id)
    records = query.order_by(
        PolicyDefinitionRecord.priority.desc(),
        PolicyDefinitionRecord.policy_id,
        PolicyDefinitionRecord.version.desc(),
    ).all()
    return [_policy_domain(record) for record in records]


def _policy_store_failure_response(
    db: Session,
    *,
    run: WorkflowRunRecord,
    facts: Mapping[str, Any],
    reason: str,
) -> PolicyEvaluateResponse:
    now = utc_now()
    evaluation = PolicyEvaluation(
        evaluation_id=f"PE-{uuid4().hex}",
        policy_id="POLICY-STORE-AVAILABILITY",
        policy_version=1,
        run_id=run.run_id,
        incident_id=run.incident_id,
        matched=True,
        decision=PolicyDecision.REVIEW,
        reason=reason,
        reason_code="POLICY_STORE_UNAVAILABLE",
        facts=dict(facts),
        input_hash=facts_hash(facts),
        approval_role="procurement_commander",
        candidate_action_id=(
            str((facts.get("proposed_action") or {}).get("id"))
            if isinstance(facts.get("proposed_action"), Mapping)
            and (facts.get("proposed_action") or {}).get("id")
            else None
        ),
        evaluated_at=now,
    )
    db.add(
        PolicyEvaluationRecord(
            evaluation_id=evaluation.evaluation_id,
            policy_id=evaluation.policy_id,
            policy_version=evaluation.policy_version,
            run_id=evaluation.run_id,
            incident_id=evaluation.incident_id,
            matched=True,
            decision=evaluation.decision.value,
            reason=evaluation.reason,
            reason_code=evaluation.reason_code,
            facts=evaluation.facts,
            input_hash=evaluation.input_hash,
            candidate_action_id=evaluation.candidate_action_id,
            matched_conditions=[],
            missing_facts=[],
            approval_role=evaluation.approval_role,
            evaluated_at=now,
        )
    )
    target = (
        WorkflowStatus.AWAITING_APPROVAL
        if run.status
        in {
            WorkflowStatus.RUNNING.value,
            WorkflowStatus.NEEDS_REVIEW.value,
        }
        else WorkflowStatus.FAILED
    )
    transitioned = _workflow_domain(run).transition(
        target, updated_at=now, error=reason
    )
    run.status = transitioned.status.value
    run.updated_at = transitioned.updated_at
    run.error = None if target is WorkflowStatus.AWAITING_APPROVAL else reason
    workbench = WorkbenchItemRecord(
        item_id=f"WB-{uuid4().hex}",
        run_id=run.run_id,
        incident_id=run.incident_id,
        title="Governance policy service review required",
        summary=reason,
        severity=run.severity,
        proposed_action=dict(facts.get("proposed_action") or {}),
        alternatives=[],
        policy_evaluation_ids=[evaluation.evaluation_id],
        evidence=[],
        assigned_to="procurement_commander",
        status=WorkbenchStatus.OPEN.value,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(workbench)
    db.commit()
    return PolicyEvaluateResponse(
        effective_decision=PolicyDecision.REVIEW,
        approval_roles=["procurement_commander"],
        evaluations=[PolicyEvaluationRead(**to_primitive(evaluation))],
        workbench_item_id=workbench.item_id,
    )


def _workflow_domain(record: WorkflowRunRecord) -> WorkflowRun:
    return WorkflowRun(
        run_id=record.run_id,
        incident_id=record.incident_id,
        status=WorkflowStatus(record.status),
        severity=Severity(record.severity),
        source=record.source,
        input_payload=record.input_payload,
        output_payload=record.output_payload,
        requested_by=record.requested_by,
        auto_run_id=record.auto_run_id,
        current_operator=record.current_operator,
        plan_run_id=record.plan_run_id,
        error=record.error,
        cost_at_risk=Money(record.cost_at_risk_myr or 0),
        cost_avoided=Money(record.cost_avoided_myr or 0),
        time_to_mitigation_hours=record.time_to_mitigation_hours,
        created_at=_aware(record.created_at),
        updated_at=_aware(record.updated_at),
    )


def _evidence_domain(raw: dict[str, Any]) -> EvidenceReference:
    observed_at = raw["observed_at"]
    if isinstance(observed_at, str):
        observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    return EvidenceReference(
        system=raw["system"],
        entity_type=raw["entity_type"],
        entity_id=raw["entity_id"],
        observed_at=_aware(observed_at),
        fields=tuple(raw.get("fields", [])),
        observed_values=raw.get("observed_values", {}),
        uri=raw.get("uri"),
        checksum=raw.get("checksum"),
    )


def _workbench_domain(record: WorkbenchItemRecord) -> WorkbenchItem:
    return WorkbenchItem(
        item_id=record.item_id,
        run_id=record.run_id,
        incident_id=record.incident_id,
        title=record.title,
        summary=record.summary,
        severity=Severity(record.severity),
        proposed_action=record.proposed_action,
        alternatives=tuple(record.alternatives or []),
        policy_evaluation_ids=tuple(record.policy_evaluation_ids or []),
        evidence=tuple(_evidence_domain(item) for item in (record.evidence or [])),
        assigned_to=record.assigned_to,
        status=WorkbenchStatus(record.status),
        decision=(WorkbenchDecision(record.decision) if record.decision else None),
        decision_by=record.decision_by,
        decision_reason=record.decision_reason,
        decision_payload=record.decision_payload,
        decided_at=_aware(record.decided_at) if record.decided_at else None,
        version=record.version,
        created_at=_aware(record.created_at),
        updated_at=_aware(record.updated_at),
    )


def _workbench_read(record: WorkbenchItemRecord) -> WorkbenchItemRead:
    return WorkbenchItemRead(
        item_id=record.item_id,
        run_id=record.run_id,
        incident_id=record.incident_id,
        title=record.title,
        summary=record.summary,
        severity=record.severity,
        proposed_action=record.proposed_action,
        alternatives=record.alternatives or [],
        policy_evaluation_ids=record.policy_evaluation_ids or [],
        evidence=record.evidence or [],
        assigned_to=record.assigned_to,
        supervity_form_id=record.supervity_form_id,
        supervity_activity_run_id=record.supervity_activity_run_id,
        supervity_form_status=record.supervity_form_status,
        status=record.status,
        decision=record.decision,
        decision_by=record.decision_by,
        decision_reason=record.decision_reason,
        decision_payload=record.decision_payload,
        decision_source=record.decision_source,
        decision_external_ref=record.decision_external_ref,
        decided_at=record.decided_at,
        version=record.version,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


async def _list_all_supervity_user_forms(
    client: SupervityClient,
    *,
    page_size: int = 100,
    max_pages: int = 50,
) -> list[Mapping[str, Any]]:
    """Return the API's complete form inventory without status filtering."""

    forms: list[Mapping[str, Any]] = []
    seen_ids: set[str] = set()
    for page in range(1, max_pages + 1):
        batch = await client.list_user_forms(page=page, limit=page_size)
        for form in batch:
            form_id = _remote_text(form, "id", "formId", "form_id")
            if form_id and form_id in seen_ids:
                continue
            if form_id:
                seen_ids.add(form_id)
            forms.append(form)
        if len(batch) < page_size:
            break
    else:
        raise SupervityAPIError(
            f"Supervity user-form inventory exceeded {max_pages * page_size} rows"
        )
    return forms


def _supervity_run_payload(payload: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("workflowRun", "workflow_run", "data"):
        candidate = payload.get(key)
        if isinstance(candidate, Mapping):
            return candidate
    return payload


def _supervity_form_submission(
    payload: Mapping[str, Any],
    activity_run_id: str,
) -> tuple[dict[str, Any], bool | None, datetime | None]:
    activities = _remote_list(payload, "activityRuns", "activity_runs", "activities")
    if not activities:
        activities = _remote_list(
            _supervity_run_payload(payload),
            "activityRuns",
            "activity_runs",
            "activities",
        )
    for activity in activities:
        if _remote_text(activity, "id", "activityRunId", "activity_run_id") != (
            activity_run_id
        ):
            continue
        user_form = activity.get("userForm") or activity.get("user_form")
        if not isinstance(user_form, Mapping):
            return {}, None, None
        raw_values = user_form.get("values")
        values = dict(raw_values) if isinstance(raw_values, Mapping) else {}
        approved = user_form.get("approved")
        if not isinstance(approved, bool):
            approved = None
        reviewed_at_raw = user_form.get("reviewedAt") or user_form.get("reviewed_at")
        reviewed_at = (
            _remote_datetime(reviewed_at_raw) if reviewed_at_raw is not None else None
        )
        return values, approved, reviewed_at
    return {}, None, None


def _supervity_form_activity(
    payload: Mapping[str, Any],
    activity_run_id: str,
) -> Mapping[str, Any] | None:
    activities = _remote_list(payload, "activityRuns", "activity_runs", "activities")
    if not activities:
        activities = _remote_list(
            _supervity_run_payload(payload),
            "activityRuns",
            "activity_runs",
            "activities",
        )
    return next(
        (
            activity
            for activity in activities
            if _remote_text(activity, "id", "activityRunId", "activity_run_id")
            == activity_run_id
        ),
        None,
    )


def _parsed_form_severity(parsed_form: Mapping[str, Any]) -> Severity:
    context = parsed_form.get("context")
    if isinstance(context, list):
        for item in context:
            if not isinstance(item, Mapping):
                continue
            label = str(item.get("label") or "").strip().lower().rstrip(":")
            if label != "severity":
                continue
            value = str(item.get("value") or "").strip().lower()
            try:
                return Severity(value)
            except ValueError:
                break
    return Severity.LOW


def _submission_value(values: Mapping[str, Any], *names: str) -> Any:
    sources: list[Mapping[str, Any]] = [values]
    nested = values.get("payload")
    if isinstance(nested, Mapping):
        sources.append(nested)
    elif isinstance(nested, str):
        try:
            parsed = json.loads(nested)
        except ValueError:
            parsed = None
        if isinstance(parsed, Mapping):
            sources.append(parsed)
    wanted = {re.sub(r"[^a-z0-9]", "", name.lower()) for name in names}
    for source in sources:
        for key, value in source.items():
            if re.sub(r"[^a-z0-9]", "", str(key).lower()) in wanted:
                return value
    return None


def _remote_form_decision(
    form_status: str,
    values: Mapping[str, Any],
    approved: bool | None,
) -> WorkbenchDecision | None:
    normalized_status = form_status.strip().lower()
    if normalized_status in {"rejected", "reject", "denied"} or approved is False:
        return WorkbenchDecision.REJECT
    if (
        normalized_status not in {"approved", "approve", "completed", "complete"}
        and approved is not True
    ):
        return None
    action = (
        str(_submission_value(values, "Reviewer Action", "action", "decision") or "")
        .strip()
        .lower()
    )
    if action in {"modify", "modified", "request replan", "request_replan", "replan"}:
        return WorkbenchDecision.MODIFY
    if action in {"reject", "rejected"}:
        return WorkbenchDecision.REJECT
    return WorkbenchDecision.APPROVE


def _apply_remote_form_resolution(
    record: WorkbenchItemRecord,
    *,
    form: Mapping[str, Any],
    form_status: str,
    values: Mapping[str, Any],
    approved: bool | None,
    reviewed_at: datetime | None,
) -> bool:
    """Resolve an open local projection from the authoritative API state."""

    decision = _remote_form_decision(form_status, values, approved)
    if decision is None or record.status != WorkbenchStatus.OPEN.value:
        return False
    status_by_decision = {
        WorkbenchDecision.APPROVE: WorkbenchStatus.APPROVED,
        WorkbenchDecision.MODIFY: WorkbenchStatus.MODIFIED,
        WorkbenchDecision.REJECT: WorkbenchStatus.REJECTED,
    }
    decided_at = reviewed_at or _remote_datetime(form.get("updatedAt"))
    decided_at = max(_aware(record.created_at), decided_at)
    reviewer = _submission_value(
        values,
        "decision_by",
        "Approved By",
        "reviewer",
        "reviewed_by",
    )
    rationale = _submission_value(
        values,
        "Decision Rationale",
        "reason",
        "decision_reason",
    )
    source = str(_submission_value(values, "decision_source") or "").strip()
    record.status = status_by_decision[decision].value
    record.decision = decision.value
    record.decision_by = str(reviewer).strip() if reviewer else "Supervity API"
    record.decision_reason = (
        str(rationale).strip()
        if rationale
        else f"Supervity form reported {form_status}"
    )
    record.decision_payload = dict(values) or None
    record.decision_source = (
        "command_center" if source == "command_center" else "supervity_api"
    )
    record.decision_external_ref = f"supervity:{record.supervity_form_id}"
    record.decided_at = decided_at
    record.updated_at = utc_now()
    record.version += 1
    return True


def _expire_remote_form(
    record: WorkbenchItemRecord,
    *,
    reason: str,
) -> bool:
    """Remove a stale API projection from the actionable Workbench queue."""

    if record.status != WorkbenchStatus.OPEN.value:
        return False
    record.status = WorkbenchStatus.EXPIRED.value
    record.supervity_form_status = WorkbenchStatus.EXPIRED.value
    record.decision = None
    record.decision_by = None
    record.decision_reason = reason
    record.decision_payload = None
    record.decision_source = "supervity_api"
    record.decision_external_ref = (
        f"supervity:{record.supervity_form_id}" if record.supervity_form_id else None
    )
    record.decided_at = None
    record.updated_at = utc_now()
    record.version += 1
    return True


async def _confirm_supervity_form_decision(
    client: SupervityClient,
    *,
    form_id: str,
    activity_run_id: str,
    auto_run_id: str,
    expected_decision: WorkbenchDecision,
    attempts: int = 5,
    delay_seconds: float = 0.4,
) -> tuple[
    Mapping[str, Any],
    str,
    Mapping[str, Any],
    dict[str, Any],
    bool | None,
    datetime | None,
]:
    """Poll bounded API reads until the submitted semantic decision is visible."""

    for attempt in range(attempts):
        confirmed_form = next(
            (
                form
                for form in await _list_all_supervity_user_forms(client)
                if _remote_text(form, "id", "formId", "form_id") == form_id
            ),
            None,
        )
        if confirmed_form is not None:
            confirmed_status = (
                (_remote_text(confirmed_form, "status") or "").strip().lower()
            )
            try:
                remote_run_payload = await client.status(auto_run_id)
            except SupervityAPIError:
                remote_run_payload = None
            if remote_run_payload is not None:
                values, approved, reviewed_at = _supervity_form_submission(
                    remote_run_payload,
                    activity_run_id,
                )
                remote_decision = _remote_form_decision(
                    confirmed_status,
                    values,
                    approved,
                )
                if remote_decision is expected_decision:
                    return (
                        confirmed_form,
                        confirmed_status,
                        remote_run_payload,
                        values,
                        approved,
                        reviewed_at,
                    )
        if attempt + 1 < attempts:
            await asyncio.sleep(delay_seconds)
    raise SupervityAPIError(
        "Supervity did not confirm the submitted form decision after bounded retries"
    )


def _notification_read(record: NotificationRecord) -> NotificationRead:
    return NotificationRead(
        notification_id=record.notification_id,
        run_id=record.run_id,
        incident_id=record.incident_id,
        workbench_item_id=record.workbench_item_id,
        provider=record.provider,
        managed_by=record.managed_by,
        notification_type=record.notification_type,
        destination=record.destination,
        external_ref=record.external_ref,
        thread_ref=record.thread_ref,
        status=record.status,
        payload=record.payload or {},
        idempotency_key=record.idempotency_key,
        last_error=record.last_error,
        attempt=record.attempt,
        occurred_at=record.occurred_at,
        delivered_at=record.delivered_at,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _require_run(db: Session, run_id: str) -> WorkflowRunRecord:
    record = (
        db.query(WorkflowRunRecord).filter(WorkflowRunRecord.run_id == run_id).first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    return record


def _verify_run_token(run_id: str, provided_token: str | None) -> None:
    secret = os.getenv("COMMAND_CENTER_CALLBACK_SECRET", "")
    expected = (
        hmac.new(secret.encode(), run_id.encode(), hashlib.sha256).hexdigest()
        if secret
        else ""
    )
    if (
        not expected
        or not provided_token
        or not hmac.compare_digest(expected, provided_token)
    ):
        raise HTTPException(status_code=401, detail="Invalid Command Center run token")


def _set_integration_health(
    db: Session,
    *,
    integration_id: str,
    name: str,
    category: str,
    status: str,
    last_error: str | None = None,
    records_seen: int | None = None,
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
            metadata_json={},
        )
        db.add(record)
    now = utc_now()
    record.name = name
    record.category = category
    record.status = status
    record.checked_at = now
    record.last_error = last_error
    record.records_seen = records_seen
    if status == "healthy":
        record.last_success_at = now
    return record


OUTLOOK_DELTA_LINK_KEY = "_outlook_delta_link"
OUTLOOK_INCIDENT_PATTERN = re.compile(r"\bDN-\d{4,}\b", re.IGNORECASE)


def _integration_metadata(record: IntegrationHealthRecord) -> dict[str, Any]:
    """Return integration metadata without internal cursor material."""
    metadata = {
        str(key): value
        for key, value in (record.metadata_json or {}).items()
        if not str(key).startswith("_")
    }
    if record.integration_id == "outlook":
        metadata.update(outlook_oauth_configuration())
    return metadata


def _outlook_poll_max_pages() -> int:
    raw = os.getenv("OUTLOOK_POLL_MAX_PAGES", "").strip() or "25"
    try:
        value = int(raw)
    except ValueError as exc:
        raise OutlookConfigurationError(
            "OUTLOOK_POLL_MAX_PAGES must be an integer"
        ) from exc
    if value < 1 or value > 100:
        raise OutlookConfigurationError(
            "OUTLOOK_POLL_MAX_PAGES must be between 1 and 100"
        )
    return value


def _authorize_outlook_poll(
    provided_secret: str | None,
    user: dict | None,
) -> None:
    expected_secret = os.getenv("OUTLOOK_POLL_SECRET", "").strip()
    if expected_secret:
        if not provided_secret or not hmac.compare_digest(
            expected_secret, provided_secret
        ):
            raise HTTPException(status_code=401, detail="Invalid Outlook poll secret")
        return
    if user is None:
        raise HTTPException(
            status_code=401,
            detail=("Authenticate the scheduler or configure OUTLOOK_POLL_SECRET"),
        )


def _outlook_sender(message: Mapping[str, Any]) -> str:
    sender = message.get("from")
    if not isinstance(sender, Mapping):
        return "unknown@outlook.invalid"
    email_address = sender.get("emailAddress")
    if not isinstance(email_address, Mapping):
        return "unknown@outlook.invalid"
    address = email_address.get("address")
    return (
        address.strip()
        if isinstance(address, str) and address.strip()
        else "unknown@outlook.invalid"
    )


def _outlook_body(message: Mapping[str, Any]) -> str:
    body = message.get("body")
    if isinstance(body, Mapping):
        content = body.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
    subject = message.get("subject")
    return subject.strip() if isinstance(subject, str) and subject.strip() else ""


def _outlook_source_ref(message: Mapping[str, Any]) -> str:
    raw = message.get("internetMessageId") or message.get("id")
    if not isinstance(raw, str) or not raw.strip():
        raise OutlookAPIError("Outlook message had no stable identifier")
    value = raw.strip()
    if len(value) <= 255:
        return value
    return f"sha256:{hashlib.sha256(value.encode()).hexdigest()}"


def _outlook_incident_id(
    subject: str,
    body: str,
    source_ref: str,
) -> str:
    match = OUTLOOK_INCIDENT_PATTERN.search(f"{subject}\n{body}")
    if match:
        return match.group(0).upper()

    digest = hashlib.sha256(source_ref.encode()).hexdigest()[:16].upper()
    return f"OUTLOOK-{digest}"


def _supervity_inputs(record: WorkflowRunRecord) -> dict[str, Any]:
    payload = record.input_payload or {}
    return {
        **payload,
        "source": payload.get("source") or record.source,
        "source_ref": payload.get("source_ref") or record.incident_id,
        "received_at_raw": payload.get("received_at_raw")
        or record.created_at.isoformat(),
        "sender_email": payload.get("sender_email") or "command-center@local.invalid",
        "body": payload.get("body") or json.dumps(payload, default=str),
    }


async def _consume_supervity_stream(run_id: str) -> None:
    async def persist_auto_run_id(auto_run_id: str) -> None:
        callback_db = SessionLocal()
        try:
            callback_record = (
                callback_db.query(WorkflowRunRecord)
                .filter(WorkflowRunRecord.run_id == run_id)
                .with_for_update()
                .first()
            )
            if callback_record is not None:
                if callback_record.auto_run_id not in {None, auto_run_id}:
                    raise RuntimeError("Supervity returned conflicting run identifiers")
                callback_record.auto_run_id = auto_run_id
                callback_record.updated_at = utc_now()
                callback_db.commit()
        finally:
            callback_db.close()

    async def has_pending_form(auto_run_id: str | None) -> bool:
        if not auto_run_id:
            return False
        try:
            forms = await SupervityClient.from_environment().list_user_forms(
                status="pending",
                limit=100,
            )
        except (SupervityConfigurationError, SupervityAPIError):
            return False
        return any(
            _remote_text(form, "workflowRunId", "workflow_run_id", "runId")
            == auto_run_id
            for form in forms
        )

    snapshot_db = SessionLocal()
    try:
        record = (
            snapshot_db.query(WorkflowRunRecord)
            .filter(WorkflowRunRecord.run_id == run_id)
            .first()
        )
        if record is None:
            return
        incident_id = record.incident_id
        inputs = _supervity_inputs(record)
    finally:
        snapshot_db.close()

    api_url = os.getenv("COMMAND_CENTER_API_URL", "").rstrip("/")
    callback_secret = os.getenv("COMMAND_CENTER_CALLBACK_SECRET", "")
    callback_url = (
        f"{api_url}/api/command-center/supervity/callback"
        if api_url and callback_secret
        else None
    )
    callback_token = (
        hmac.new(callback_secret.encode(), run_id.encode(), hashlib.sha256).hexdigest()
        if callback_url
        else None
    )

    try:
        handle = await SupervityClient.from_environment().trigger(
            command_center_run_id=run_id,
            incident_id=incident_id,
            inputs=inputs,
            callback_url=callback_url,
            callback_token=callback_token,
            on_run_id=persist_auto_run_id,
        )
    except (SupervityConfigurationError, SupervityAPIError) as exc:
        result_db = SessionLocal()
        try:
            record = (
                result_db.query(WorkflowRunRecord)
                .filter(WorkflowRunRecord.run_id == run_id)
                .with_for_update()
                .first()
            )
            pending_review = bool(record and await has_pending_form(record.auto_run_id))
            if record is not None and record.status == WorkflowStatus.RUNNING.value:
                record.status = (
                    WorkflowStatus.AWAITING_APPROVAL.value
                    if pending_review
                    else WorkflowStatus.FAILED.value
                )
                record.error = None if pending_review else str(exc)
                record.updated_at = utc_now()
            _set_integration_health(
                result_db,
                integration_id="supervity-auto",
                name="Supervity Auto",
                category="agent_platform",
                status="healthy" if pending_review else "degraded",
                last_error=None if pending_review else str(exc),
            )
            result_db.commit()
        finally:
            result_db.close()
        return

    result_db = SessionLocal()
    try:
        record = (
            result_db.query(WorkflowRunRecord)
            .filter(WorkflowRunRecord.run_id == run_id)
            .with_for_update()
            .first()
        )
        if record is None:
            return
        record.auto_run_id = handle.run_id
        record.output_payload = {
            "transport": "supervity_execute_stream",
            "auto_run_id": handle.run_id,
            "supervity_status": handle.status,
            "supervity_success": handle.success,
            "supervity_message": handle.message,
            **dict(handle.raw_response),
        }
        failed_statuses = {"failed", "error", "cancelled", "canceled"}
        completed_statuses = {"completed", "complete", "succeeded", "success"}
        normalized_status = (handle.status or "").strip().lower()
        if handle.success is False or normalized_status in failed_statuses:
            record.status = (
                WorkflowStatus.CANCELLED.value
                if normalized_status in {"cancelled", "canceled"}
                else WorkflowStatus.FAILED.value
            )
            record.error = handle.message or "Supervity workflow execution failed"
        elif handle.success is True and normalized_status in completed_statuses:
            record.status = WorkflowStatus.COMPLETED.value
            record.error = None
        elif await has_pending_form(record.auto_run_id or handle.run_id):
            record.status = WorkflowStatus.AWAITING_APPROVAL.value
            record.error = None
        else:
            record.status = WorkflowStatus.NEEDS_REVIEW.value
            record.error = (
                "Supervity stream closed without an explicit successful terminal state"
            )
        record.updated_at = utc_now()
        _set_integration_health(
            result_db,
            integration_id="supervity-auto",
            name="Supervity Auto",
            category="agent_platform",
            status="healthy",
            records_seen=1,
        )
        result_db.commit()
    finally:
        result_db.close()


@router.get("/dashboard", response_model=DashboardSummary)
async def dashboard_summary(db: Session = Depends(get_db)):
    await reconcile_supervity_integration_health(db)
    open_statuses = {
        WorkflowStatus.QUEUED.value,
        WorkflowStatus.RUNNING.value,
        WorkflowStatus.AWAITING_APPROVAL.value,
        WorkflowStatus.EXECUTING.value,
        WorkflowStatus.NEEDS_REVIEW.value,
    }
    open_disruptions = (
        db.query(func.count(WorkflowRunRecord.run_id))
        .filter(WorkflowRunRecord.status.in_(open_statuses))
        .scalar()
        or 0
    )
    critical_disruptions = (
        db.query(func.count(WorkflowRunRecord.run_id))
        .filter(
            WorkflowRunRecord.status.in_(open_statuses),
            WorkflowRunRecord.severity == Severity.CRITICAL.value,
        )
        .scalar()
        or 0
    )
    awaiting_decision = (
        db.query(func.count(WorkbenchItemRecord.item_id))
        .filter(WorkbenchItemRecord.status == WorkbenchStatus.OPEN.value)
        .scalar()
        or 0
    )
    completed_runs = (
        db.query(func.count(WorkflowRunRecord.run_id))
        .filter(WorkflowRunRecord.status == WorkflowStatus.COMPLETED.value)
        .scalar()
        or 0
    )
    totals = db.query(
        func.coalesce(func.sum(WorkflowRunRecord.cost_at_risk_myr), 0),
        func.coalesce(func.sum(WorkflowRunRecord.cost_avoided_myr), 0),
        func.avg(WorkflowRunRecord.time_to_mitigation_hours),
    ).one()
    total_integrations = (
        db.query(func.count(IntegrationHealthRecord.integration_id)).scalar() or 0
    )
    healthy_integrations = (
        db.query(func.count(IntegrationHealthRecord.integration_id))
        .filter(IntegrationHealthRecord.status == "healthy")
        .scalar()
        or 0
    )
    return DashboardSummary(
        open_disruptions=open_disruptions,
        critical_disruptions=critical_disruptions,
        awaiting_decision=awaiting_decision,
        completed_runs=completed_runs,
        cost_at_risk_myr=totals[0],
        cost_avoided_myr=totals[1],
        average_time_to_mitigation_hours=(
            float(totals[2]) if totals[2] is not None else None
        ),
        healthy_integrations=healthy_integrations,
        total_integrations=total_integrations,
    )


@router.get("/runs", response_model=list[WorkflowRunRead])
def list_runs(
    limit: int = Query(default=50, ge=1, le=200), db: Session = Depends(get_db)
):
    return (
        db.query(WorkflowRunRecord)
        .order_by(WorkflowRunRecord.created_at.desc())
        .limit(limit)
        .all()
    )


@router.post("/runs", response_model=WorkflowRunRead, status_code=201)
async def create_run(
    payload: WorkflowRunCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    source = payload.source.strip().lower()
    source_ref = payload.source_ref or next(
        (
            str(payload.input_payload[key]).strip()
            for key in ("source_ref", "notice_id")
            if payload.input_payload.get(key) is not None
            and str(payload.input_payload[key]).strip()
        ),
        payload.incident_id.strip(),
    )
    source_ref = source_ref.strip()
    existing = (
        db.query(WorkflowRunRecord)
        .filter(
            WorkflowRunRecord.source == source,
            WorkflowRunRecord.source_ref == source_ref,
        )
        .with_for_update()
        .first()
    )
    if existing is not None:
        existing.duplicate_trigger_count += 1
        existing.updated_at = utc_now()
        db.commit()
        db.refresh(existing)
        await audit.log(
            action="workflow.duplicate",
            description=f"Ignored duplicate trigger {payload.source}:{source_ref}",
            actor=user,
            category="workflow",
            resource_type="workflow_run",
            resource_id=existing.run_id,
            request=request,
            metadata={
                "incident_id": existing.incident_id,
                "source": existing.source,
                "source_ref": source_ref,
                "duplicate_trigger_count": existing.duplicate_trigger_count,
            },
        )
        return existing
    now = utc_now()
    record = WorkflowRunRecord(
        run_id=f"RUN-{uuid4().hex}",
        incident_id=payload.incident_id,
        status=WorkflowStatus.QUEUED.value,
        severity=Severity.UNKNOWN.value,
        source=source,
        source_ref=source_ref,
        duplicate_trigger_count=0,
        input_payload=payload.input_payload,
        requested_by=payload.requested_by or _actor_label(user),
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent identical trigger may win the unique source identity.
        db.rollback()
        existing = (
            db.query(WorkflowRunRecord)
            .filter(
                WorkflowRunRecord.source == source,
                WorkflowRunRecord.source_ref == source_ref,
            )
            .with_for_update()
            .one()
        )
        existing.duplicate_trigger_count += 1
        existing.updated_at = utc_now()
        db.commit()
        db.refresh(existing)
        return existing
    db.refresh(record)
    await audit.log(
        action="workflow.create",
        description=f"Queued workflow for incident {record.incident_id}",
        actor=user,
        category="workflow",
        resource_type="workflow_run",
        resource_id=record.run_id,
        request=request,
        metadata={
            "incident_id": record.incident_id,
            "source": record.source,
            "source_ref": record.source_ref,
        },
    )
    return record


@router.get("/runs/{run_id}", response_model=WorkflowRunRead)
def get_run(run_id: str, db: Session = Depends(get_db)):
    return _require_run(db, run_id)


@router.post("/runs/{run_id}/sync-supervity", response_model=SupervityRunSyncRead)
async def sync_run_from_supervity(
    run_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    run = _require_run(db, run_id)
    if not run.auto_run_id:
        raise HTTPException(
            status_code=409,
            detail="Cannot sync a run until its Auto run ID has been recorded",
        )
    try:
        payload = await SupervityClient.from_environment().status(run.auto_run_id)
    except SupervityConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SupervityAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    remote_run: Mapping[str, Any] = payload
    for key in ("workflowRun", "workflow_run", "data"):
        candidate = payload.get(key)
        if isinstance(candidate, Mapping):
            remote_run = candidate
            break
    remote_status = _remote_text(remote_run, "status") or "unknown"
    local_status = _workflow_status_from_supervity(remote_status)
    activities = _remote_list(
        payload,
        "activityRuns",
        "activity_runs",
        "activities",
    )
    if not activities:
        activities = _remote_list(
            remote_run,
            "activityRuns",
            "activity_runs",
            "activities",
        )
    added = 0
    last_operator: str | None = None
    for activity in activities:
        step_name = _remote_text(activity, "stepName", "step_name", "name")
        operator_name = SUPERVITY_OPERATOR_STEPS.get(step_name or "")
        if operator_name is None and step_name in KNOWN_OPERATOR_NAMES:
            operator_name = step_name
        if operator_name is None:
            continue
        activity_run_id = _remote_text(
            activity, "id", "activityRunId", "activity_run_id"
        )
        if not activity_run_id:
            continue
        existing = (
            db.query(OperatorResultRecord)
            .filter(
                OperatorResultRecord.workflow_run_id == run.run_id,
                OperatorResultRecord.operator_run_id == activity_run_id,
            )
            .first()
        )
        if existing is not None:
            last_operator = operator_name
            continue
        outputs = activity.get("outputs")
        output_map = outputs if isinstance(outputs, Mapping) else {}
        operator_output: Mapping[str, Any] = output_map
        for key in ("operatorResult", "operator_result", "result"):
            candidate = output_map.get(key)
            if isinstance(candidate, Mapping):
                operator_output = candidate
                break
        started_at = _remote_datetime(
            activity.get("createdAt") or activity.get("created_at")
        )
        normalized_operator_status = _operator_status_from_supervity(
            _remote_text(activity, "status") or _remote_text(operator_output, "status")
        )
        completed_at = (
            _remote_datetime(
                activity.get("updatedAt") or activity.get("updated_at"),
                default=started_at,
            )
            if normalized_operator_status
            in {"succeeded", "no_match", "needs_review", "failed", "skipped"}
            else None
        )
        raw_attempt = activity.get("attempt", 1)
        try:
            attempt = max(1, int(raw_attempt))
        except (TypeError, ValueError):
            attempt = 1
        while (
            db.query(OperatorResultRecord)
            .filter(
                OperatorResultRecord.workflow_run_id == run.run_id,
                OperatorResultRecord.operator_name == operator_name,
                OperatorResultRecord.attempt == attempt,
            )
            .first()
            is not None
        ):
            attempt += 1
        raw_confidence = operator_output.get("confidence")
        try:
            confidence = min(1.0, max(0.0, float(raw_confidence)))
        except (TypeError, ValueError):
            confidence = 1.0 if normalized_operator_status == "succeeded" else 0.0
        raw_facts = operator_output.get("facts")
        facts = (
            _sanitize_remote(raw_facts)
            if isinstance(raw_facts, Mapping)
            else _sanitize_remote(output_map)
        )
        evidence = _safe_evidence(
            operator_output.get("evidence"), fallback_time=started_at
        )
        record = OperatorResultRecord(
            result_id=f"OR-{uuid4().hex}",
            workflow_run_id=run.run_id,
            operator_run_id=activity_run_id,
            schema_version=_remote_text(
                operator_output, "schema_version", "schemaVersion"
            )
            or "2.0",
            incident_id=run.incident_id,
            subject_type=_remote_text(operator_output, "subject_type", "subjectType")
            or "incident",
            subject_id=_remote_text(operator_output, "subject_id", "subjectId")
            or run.incident_id,
            operator_name=operator_name,
            operator_version=_remote_text(
                operator_output, "operator_version", "operatorVersion"
            ),
            attempt=attempt,
            status=normalized_operator_status,
            confidence=confidence,
            facts=facts,
            evidence=evidence,
            assumptions=_string_items(operator_output.get("assumptions")),
            warnings=_string_items(operator_output.get("warnings")),
            errors=_string_items(operator_output.get("errors")),
            proposed_actions=(
                _sanitize_remote(operator_output.get("proposed_actions"))
                if isinstance(operator_output.get("proposed_actions"), list)
                else (
                    _sanitize_remote(operator_output.get("proposedActions"))
                    if isinstance(operator_output.get("proposedActions"), list)
                    else []
                )
            ),
            started_at=started_at,
            completed_at=completed_at,
        )
        db.add(record)
        added += 1
        last_operator = operator_name
        if operator_name == "Recovery Planner Operator":
            run.plan_run_id = activity_run_id

    run.status = local_status.value
    run.current_operator = last_operator or run.current_operator
    run.updated_at = utc_now()
    run.output_payload = {
        **(run.output_payload or {}),
        "supervity_sync": {
            "auto_run_id": run.auto_run_id,
            "status": remote_status,
            "activities_seen": len(activities),
            "synced_at": run.updated_at.isoformat(),
        },
    }
    run.error = (
        _remote_text(remote_run, "error", "message")
        if local_status is WorkflowStatus.FAILED
        else None
    )
    _set_integration_health(
        db,
        integration_id="supervity-auto",
        name="Supervity Auto",
        category="agent_platform",
        status="healthy",
        records_seen=len(activities),
    )
    db.commit()
    await audit.log(
        action="workflow.sync",
        description=f"Synchronized Auto run {run.auto_run_id}",
        actor=user,
        category="workflow",
        resource_type="workflow_run",
        resource_id=run.run_id,
        request=request,
        metadata={
            "remote_status": remote_status,
            "activities_seen": len(activities),
            "operator_results_added": added,
        },
    )
    return SupervityRunSyncRead(
        run_id=run.run_id,
        auto_run_id=run.auto_run_id,
        remote_status=remote_status,
        local_status=local_status,
        activities_seen=len(activities),
        operator_results_added=added,
    )


@router.post("/runs/{run_id}/start", response_model=WorkflowRunRead)
async def start_run(
    run_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    record = (
        db.query(WorkflowRunRecord)
        .filter(WorkflowRunRecord.run_id == run_id)
        .with_for_update()
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if record.auto_run_id:
        return record
    if record.status != WorkflowStatus.QUEUED.value:
        raise HTTPException(status_code=409, detail="Only queued runs can be started")
    try:
        SupervityClient.from_environment()
    except SupervityConfigurationError as exc:
        record.error = str(exc)
        _set_integration_health(
            db,
            integration_id="supervity-auto",
            name="Supervity Auto",
            category="agent_platform",
            status="disconnected",
            last_error=str(exc),
        )
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    transitioned = _workflow_domain(record).transition(
        WorkflowStatus.RUNNING,
        updated_at=utc_now(),
        current_operator="Exception Commander Orchestrator",
    )
    record.status = transitioned.status.value
    record.updated_at = transitioned.updated_at
    record.current_operator = transitioned.current_operator
    record.error = None
    db.commit()
    db.refresh(record)
    background_tasks.add_task(_consume_supervity_stream, record.run_id)
    await audit.log(
        action="workflow.dispatch",
        description="Dispatched workflow to the Supervity execution stream",
        actor=user,
        category="workflow",
        resource_type="workflow_run",
        resource_id=record.run_id,
        request=request,
        metadata={
            "incident_id": record.incident_id,
            "transport": "multipart/form-data stream",
        },
    )
    return record


@router.post("/supervity/callback", response_model=WorkflowRunRead)
async def supervity_callback(
    payload: SupervityCallbackRequest,
    x_command_center_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_run_token(payload.command_center_run_id, x_command_center_secret)
    record = (
        db.query(WorkflowRunRecord)
        .filter(WorkflowRunRecord.run_id == payload.command_center_run_id)
        .with_for_update()
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    if (
        payload.auto_run_id
        and record.auto_run_id
        and payload.auto_run_id != record.auto_run_id
    ):
        raise HTTPException(status_code=409, detail="Auto run ID does not match")
    target_status = WorkflowStatus(payload.status)
    domain = _workflow_domain(record)
    try:
        if domain.status is WorkflowStatus.QUEUED and target_status not in {
            WorkflowStatus.QUEUED,
            WorkflowStatus.RUNNING,
        }:
            domain = domain.transition(
                WorkflowStatus.RUNNING,
                updated_at=utc_now(),
                current_operator=payload.current_operator,
            )
        transitioned = domain.transition(
            target_status,
            updated_at=utc_now(),
            current_operator=payload.current_operator,
            output_payload=payload.output_payload,
            error=payload.error,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record.status = transitioned.status.value
    record.updated_at = transitioned.updated_at
    record.current_operator = transitioned.current_operator
    record.output_payload = transitioned.output_payload
    record.error = transitioned.error
    if payload.auto_run_id:
        record.auto_run_id = payload.auto_run_id
    if payload.plan_run_id:
        record.plan_run_id = payload.plan_run_id
    if payload.severity is not None:
        record.severity = Severity(payload.severity).value
    if payload.cost_at_risk_myr is not None:
        record.cost_at_risk_myr = payload.cost_at_risk_myr
    if payload.cost_avoided_myr is not None:
        record.cost_avoided_myr = payload.cost_avoided_myr
    if payload.time_to_mitigation_hours is not None:
        record.time_to_mitigation_hours = payload.time_to_mitigation_hours
    _set_integration_health(
        db,
        integration_id="supervity-auto",
        name="Supervity Auto",
        category="agent_platform",
        status="healthy",
        records_seen=1,
    )
    db.commit()
    db.refresh(record)
    return record


@router.post(
    "/supervity/notification",
    response_model=NotificationRead,
    status_code=201,
)
async def supervity_notification_callback(
    payload: SupervityNotificationCallbackRequest,
    request: Request,
    x_command_center_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_run_token(payload.command_center_run_id, x_command_center_secret)
    run = _require_run(db, payload.command_center_run_id)
    workbench = None
    if payload.workbench_item_id:
        workbench = (
            db.query(WorkbenchItemRecord)
            .filter(WorkbenchItemRecord.item_id == payload.workbench_item_id)
            .first()
        )
        if workbench is None:
            raise HTTPException(status_code=404, detail="Workbench item not found")
        if workbench.run_id != run.run_id:
            raise HTTPException(
                status_code=409,
                detail="Workbench item and workflow run do not match",
            )

    record = (
        db.query(NotificationRecord)
        .filter(NotificationRecord.idempotency_key == payload.event_id)
        .with_for_update()
        .first()
    )
    if record is not None:
        if record.run_id != run.run_id:
            raise HTTPException(
                status_code=409,
                detail="Notification event ID belongs to another workflow run",
            )
        if record.notification_type != payload.notification_type:
            raise HTTPException(
                status_code=409,
                detail="Notification event ID has a different notification type",
            )
        if record.provider != payload.provider:
            raise HTTPException(
                status_code=409,
                detail="Notification event ID belongs to another provider",
            )
        if (
            payload.workbench_item_id
            and record.workbench_item_id
            and record.workbench_item_id != payload.workbench_item_id
        ):
            raise HTTPException(
                status_code=409,
                detail="Notification event ID belongs to another Workbench item",
            )
        if record.status in {"delivered", "updated"} and payload.status in {
            "requested",
            "failed",
        }:
            return _notification_read(record)
    else:
        now = utc_now()
        record = NotificationRecord(
            notification_id=f"NTF-{uuid4().hex}",
            run_id=run.run_id,
            incident_id=run.incident_id,
            workbench_item_id=payload.workbench_item_id,
            provider=payload.provider,
            managed_by="supervity",
            notification_type=payload.notification_type,
            status="requested",
            payload={},
            idempotency_key=payload.event_id,
            attempt=payload.attempt,
            occurred_at=_aware(payload.occurred_at) if payload.occurred_at else now,
            created_at=now,
            updated_at=now,
        )
        db.add(record)

    occurred_at = _aware(payload.occurred_at) if payload.occurred_at else utc_now()
    record.workbench_item_id = payload.workbench_item_id or record.workbench_item_id
    record.provider = payload.provider
    record.destination = (
        payload.destination_id
        or payload.channel_id
        or payload.conversation_id
        or record.destination
    )
    record.external_ref = (
        payload.message_id or payload.message_ts or record.external_ref
    )
    record.thread_ref = payload.thread_id or payload.thread_ts or record.thread_ref
    record.status = payload.status
    receipt_payload = dict(payload.payload)
    if payload.route_key:
        receipt_payload.setdefault("route_key", payload.route_key)
    if payload.conversation_id:
        receipt_payload.setdefault("conversation_id", payload.conversation_id)
    record.payload = receipt_payload
    record.last_error = payload.error if payload.status == "failed" else None
    record.attempt = payload.attempt
    record.occurred_at = occurred_at
    record.updated_at = utc_now()
    if payload.status in {"delivered", "updated"}:
        record.delivered_at = occurred_at

    db.flush()
    successful_deliveries = (
        db.query(func.count(NotificationRecord.notification_id))
        .filter(
            NotificationRecord.provider == payload.provider,
            NotificationRecord.managed_by == "supervity",
            NotificationRecord.status.in_(("delivered", "updated")),
        )
        .scalar()
        or 0
    )
    health_id = (
        "slack-via-supervity" if payload.provider == "slack" else "supervity-chat"
    )
    health_name = (
        "Slack via Supervity" if payload.provider == "slack" else "Supervity Chat"
    )
    existing_health = (
        db.query(IntegrationHealthRecord)
        .filter(IntegrationHealthRecord.integration_id == health_id)
        .first()
    )
    if payload.status in {"delivered", "updated"}:
        health_status = "healthy"
    elif payload.status == "failed":
        health_status = "degraded"
    else:
        health_status = existing_health.status if existing_health else "unknown"
    health = _set_integration_health(
        db,
        integration_id=health_id,
        name=health_name,
        category="notification",
        status=health_status,
        last_error=payload.error if payload.status == "failed" else None,
        records_seen=successful_deliveries,
    )
    metadata = dict(health.metadata_json or {})
    metadata.update(
        {
            "managed_by": "supervity",
            "transport": payload.provider,
            "last_notification_type": payload.notification_type,
            "last_event_id": payload.event_id,
        }
    )
    if payload.route_key:
        metadata["last_route_key"] = payload.route_key
    if record.destination:
        metadata["last_destination_id"] = record.destination
    if record.external_ref:
        metadata["last_message_id"] = record.external_ref
    if payload.provider == "slack":
        if record.destination:
            metadata["last_channel_id"] = record.destination
        if record.external_ref:
            metadata["last_message_ts"] = record.external_ref
    if record.delivered_at:
        metadata["last_delivery_at"] = _aware(record.delivered_at).isoformat()
    health.metadata_json = metadata

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        replay = (
            db.query(NotificationRecord)
            .filter(NotificationRecord.idempotency_key == payload.event_id)
            .first()
        )
        if (
            replay is not None
            and replay.run_id == payload.command_center_run_id
            and replay.notification_type == payload.notification_type
        ):
            return _notification_read(replay)
        raise HTTPException(
            status_code=409,
            detail="The notification event was recorded concurrently",
        ) from exc
    db.refresh(record)
    await audit.log(
        action=f"notification.{payload.status}",
        description=(
            f"Supervity reported {payload.provider} {payload.notification_type} "
            f"notification as {payload.status}"
        ),
        actor={"sub": "supervity", "email": "supervity"},
        category="integration",
        resource_type="notification",
        resource_id=record.notification_id,
        request=request,
        metadata={
            "run_id": run.run_id,
            "incident_id": run.incident_id,
            "workbench_item_id": record.workbench_item_id,
            "event_id": payload.event_id,
            "provider": payload.provider,
            "route_key": payload.route_key,
            "message_id": record.external_ref,
        },
        success=payload.status != "failed",
        error_message=payload.error,
    )
    return _notification_read(record)


@router.post("/supervity/decision", response_model=WorkbenchItemRead)
async def supervity_decision_callback(
    payload: SupervityDecisionCallbackRequest,
    request: Request,
    x_command_center_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_run_token(payload.command_center_run_id, x_command_center_secret)
    if not payload.workbench_item_id and not payload.supervity_form_id:
        raise HTTPException(
            status_code=422,
            detail="workbench_item_id or supervity_form_id is required",
        )

    duplicate = (
        db.query(WorkbenchItemRecord)
        .filter(
            WorkbenchItemRecord.decision_external_ref == payload.external_interaction_id
        )
        .with_for_update()
        .first()
    )
    if duplicate is not None:
        if (
            duplicate.run_id == payload.command_center_run_id
            and duplicate.decision == WorkbenchDecision(payload.decision).value
            and duplicate.decision_source == payload.decision_source
        ):
            return _workbench_read(duplicate)
        raise HTTPException(
            status_code=409,
            detail="External interaction ID belongs to another decision",
        )

    query = db.query(WorkbenchItemRecord).filter(
        WorkbenchItemRecord.run_id == payload.command_center_run_id
    )
    if payload.workbench_item_id:
        query = query.filter(WorkbenchItemRecord.item_id == payload.workbench_item_id)
    else:
        query = query.filter(
            WorkbenchItemRecord.supervity_form_id == payload.supervity_form_id
        )
    record = query.with_for_update().first()
    if record is None:
        raise HTTPException(status_code=404, detail="Workbench item not found")
    if record.status != WorkbenchStatus.OPEN.value:
        if (
            record.decision_external_ref == payload.external_interaction_id
            and record.decision == WorkbenchDecision(payload.decision).value
            and record.decision_source == payload.decision_source
        ):
            return _workbench_read(record)
        raise HTTPException(
            status_code=409,
            detail="Workbench item is already resolved",
        )

    run = (
        db.query(WorkflowRunRecord)
        .filter(WorkflowRunRecord.run_id == payload.command_center_run_id)
        .with_for_update()
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Workflow run not found")
    decision = WorkbenchDecision(payload.decision)
    if (
        run.status == WorkflowStatus.NEEDS_REVIEW.value
        and decision is WorkbenchDecision.APPROVE
    ):
        raise HTTPException(
            status_code=409,
            detail="A policy-blocked action must be modified or rejected, not approved",
        )

    try:
        resolved = _workbench_domain(record).resolve(
            decision=decision,
            decided_by=payload.decision_by,
            reason=payload.reason,
            payload=payload.payload,
            decided_at=(
                _aware(payload.decided_at) if payload.decided_at else utc_now()
            ),
        )
        if decision is WorkbenchDecision.ESCALATE:
            target_status = WorkflowStatus.NEEDS_REVIEW
        elif decision is WorkbenchDecision.REJECT:
            target_status = WorkflowStatus.CANCELLED
        elif run.status == WorkflowStatus.NEEDS_REVIEW.value:
            target_status = WorkflowStatus.RUNNING
        else:
            target_status = WorkflowStatus.EXECUTING
        transitioned = _workflow_domain(run).transition(
            target_status,
            updated_at=utc_now(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    record.status = resolved.status.value
    record.decision = resolved.decision.value
    record.decision_by = resolved.decision_by
    record.decision_reason = resolved.decision_reason
    record.decision_payload = resolved.decision_payload
    record.decision_source = payload.decision_source
    record.decision_external_ref = payload.external_interaction_id
    record.decided_at = resolved.decided_at
    record.updated_at = resolved.updated_at
    record.version = resolved.version
    if record.supervity_form_id and decision is not WorkbenchDecision.ESCALATE:
        record.supervity_form_status = (
            "rejected" if decision is WorkbenchDecision.REJECT else "approved"
        )
    run.status = transitioned.status.value
    run.updated_at = transitioned.updated_at
    run.error = None

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The decision was already recorded by another channel",
        ) from exc
    db.refresh(record)
    await audit.log(
        action=f"workbench.{decision.value}",
        description=(
            f"{decision.value.title()} decision for {record.incident_id} "
            f"from {payload.decision_source}"
        ),
        actor={
            "sub": f"supervity:{payload.decision_source}",
            "email": payload.decision_by,
        },
        category="workbench",
        resource_type="workbench_item",
        resource_id=record.item_id,
        request=request,
        metadata={
            "run_id": record.run_id,
            "decision": decision.value,
            "decision_source": payload.decision_source,
            "external_interaction_id": payload.external_interaction_id,
            "version": record.version,
        },
    )
    return _workbench_read(record)


@router.post(
    "/supervity/operator-result",
    response_model=OperatorResultRead,
    status_code=201,
)
async def supervity_operator_result(
    payload: SupervityOperatorResultRequest,
    x_command_center_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    _verify_run_token(payload.command_center_run_id, x_command_center_secret)
    run = _require_run(db, payload.command_center_run_id)
    if run.incident_id != payload.incident_id:
        raise HTTPException(status_code=409, detail="Run and incident IDs do not match")
    if payload.operator_name not in KNOWN_OPERATOR_NAMES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown Operator name: {payload.operator_name!r}",
        )
    operator_run_id = payload.operator_run_id or payload.run_id
    existing = (
        db.query(OperatorResultRecord)
        .filter(
            OperatorResultRecord.workflow_run_id == payload.command_center_run_id,
            (
                (OperatorResultRecord.operator_run_id == operator_run_id)
                | (
                    (OperatorResultRecord.operator_name == payload.operator_name)
                    & (OperatorResultRecord.attempt == payload.attempt)
                )
            ),
        )
        .first()
    )
    if existing is not None:
        return existing
    record = OperatorResultRecord(
        result_id=f"OR-{uuid4().hex}",
        workflow_run_id=payload.command_center_run_id,
        operator_run_id=operator_run_id,
        schema_version=payload.schema_version,
        incident_id=payload.incident_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id or payload.incident_id,
        operator_name=payload.operator_name,
        operator_version=payload.operator_version,
        attempt=payload.attempt,
        status=payload.status,
        confidence=payload.confidence,
        facts=payload.facts,
        evidence=[_dump(item) for item in payload.evidence],
        assumptions=payload.assumptions,
        warnings=payload.warnings,
        errors=payload.errors,
        proposed_actions=payload.proposed_actions,
        started_at=payload.started_at,
        completed_at=payload.completed_at,
    )
    run.current_operator = payload.operator_name
    run.updated_at = utc_now()
    if payload.operator_name == "Recovery Planner Operator":
        run.plan_run_id = operator_run_id
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.patch("/runs/{run_id}", response_model=WorkflowRunRead)
async def update_run(
    run_id: str,
    payload: WorkflowRunUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    record = _require_run(db, run_id)
    target_status = WorkflowStatus(payload.status)
    try:
        transitioned = _workflow_domain(record).transition(
            target_status,
            updated_at=utc_now(),
            current_operator=payload.current_operator,
            output_payload=payload.output_payload,
            error=payload.error,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    record.status = transitioned.status.value
    record.updated_at = transitioned.updated_at
    record.current_operator = transitioned.current_operator
    record.output_payload = transitioned.output_payload
    record.error = transitioned.error
    if payload.auto_run_id is not None:
        record.auto_run_id = payload.auto_run_id
    if payload.plan_run_id is not None:
        record.plan_run_id = payload.plan_run_id
    if payload.severity is not None:
        record.severity = Severity(payload.severity).value
    if payload.cost_at_risk_myr is not None:
        record.cost_at_risk_myr = payload.cost_at_risk_myr
    if payload.cost_avoided_myr is not None:
        record.cost_avoided_myr = payload.cost_avoided_myr
    if payload.time_to_mitigation_hours is not None:
        record.time_to_mitigation_hours = payload.time_to_mitigation_hours
    db.commit()
    db.refresh(record)
    await audit.log(
        action="workflow.transition",
        description=f"Workflow moved to {record.status}",
        actor=user,
        category="workflow",
        resource_type="workflow_run",
        resource_id=record.run_id,
        request=request,
        metadata={"incident_id": record.incident_id, "status": record.status},
    )
    return record


@router.get(
    "/runs/{run_id}/operator-results",
    response_model=list[OperatorResultRead],
)
def list_operator_results(run_id: str, db: Session = Depends(get_db)):
    _require_run(db, run_id)
    return (
        db.query(OperatorResultRecord)
        .filter(OperatorResultRecord.workflow_run_id == run_id)
        .order_by(OperatorResultRecord.started_at)
        .all()
    )


@router.post(
    "/runs/{run_id}/operator-results",
    response_model=OperatorResultRead,
    status_code=201,
)
async def ingest_operator_result(
    run_id: str,
    payload: OperatorResultSchema,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    run = _require_run(db, run_id)
    if run.incident_id != payload.incident_id:
        raise HTTPException(status_code=409, detail="Run and incident IDs do not match")
    if payload.operator_name not in KNOWN_OPERATOR_NAMES:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown Operator name: {payload.operator_name!r}",
        )
    operator_run_id = payload.operator_run_id or payload.run_id
    existing = (
        db.query(OperatorResultRecord)
        .filter(
            OperatorResultRecord.workflow_run_id == run_id,
            (
                (OperatorResultRecord.operator_run_id == operator_run_id)
                | (
                    (OperatorResultRecord.operator_name == payload.operator_name)
                    & (OperatorResultRecord.attempt == payload.attempt)
                )
            ),
        )
        .first()
    )
    if existing is not None:
        return existing
    record = OperatorResultRecord(
        result_id=f"OR-{uuid4().hex}",
        workflow_run_id=run_id,
        operator_run_id=operator_run_id,
        schema_version=payload.schema_version,
        incident_id=payload.incident_id,
        subject_type=payload.subject_type,
        subject_id=payload.subject_id or payload.incident_id,
        operator_name=payload.operator_name,
        operator_version=payload.operator_version,
        attempt=payload.attempt,
        status=payload.status,
        confidence=payload.confidence,
        facts=payload.facts,
        evidence=[_dump(item) for item in payload.evidence],
        assumptions=payload.assumptions,
        warnings=payload.warnings,
        errors=payload.errors,
        proposed_actions=payload.proposed_actions,
        started_at=payload.started_at,
        completed_at=payload.completed_at,
    )
    run.current_operator = payload.operator_name
    run.updated_at = utc_now()
    if payload.operator_name == "Recovery Planner Operator":
        run.plan_run_id = operator_run_id
    db.add(record)
    db.commit()
    db.refresh(record)
    await audit.log(
        action="operator.result",
        description=f"Recorded {payload.operator_name} result",
        actor=user,
        category="workflow",
        resource_type="operator_result",
        resource_id=record.result_id,
        request=request,
        metadata={
            "workflow_run_id": run_id,
            "operator_run_id": operator_run_id,
            "schema_version": payload.schema_version,
            "attempt": payload.attempt,
            "status": str(payload.status),
            "confidence": payload.confidence,
        },
    )
    return record


@router.get("/policies", response_model=list[PolicyRead])
async def list_policies(
    include_history: bool = False,
    db: Session = Depends(get_db),
):
    try:
        policies = await _load_policy_definitions(
            db,
            include_history=include_history,
        )
    except (SupabaseConfigurationError, SupabaseAPIError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return [_policy_read(policy) for policy in policies]


@router.post("/policies", response_model=PolicyRead, status_code=201)
async def create_policy(
    payload: PolicyCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    data = _dump(payload)
    policy_id = data.pop("policy_id", None) or f"POL-{uuid4().hex[:16].upper()}"
    try:
        existing_policies = await _load_policy_definitions(
            db,
            include_history=True,
            policy_id=policy_id,
        )
    except (SupabaseConfigurationError, SupabaseAPIError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if existing_policies:
        raise HTTPException(status_code=409, detail="Policy ID already exists")
    now = utc_now()
    try:
        domain = PolicyDefinition(
            policy_id=policy_id,
            version=1,
            created_at=now,
            updated_at=now,
            conditions=tuple(
                PolicyCondition(
                    field_path=item["field_path"],
                    operator=PolicyOperator(item["operator"]),
                    value=item.get("value"),
                )
                for item in data["conditions"]
            ),
            match_mode=PolicyMatchMode(data["match_mode"]),
            decision=PolicyDecision(data["decision"]),
            **{
                key: value
                for key, value in data.items()
                if key not in {"conditions", "match_mode", "decision"}
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if _supabase_policy_store_enabled():
        try:
            published = await SupabaseGovernancePolicyStore.from_environment().publish(
                domain
            )
        except (SupabaseConfigurationError, SupabaseAPIError, RuntimeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        await audit.log(
            action="policy.create",
            description=f"Created policy {published.name} v{published.version}",
            actor=user,
            category="policy",
            resource_type="policy",
            resource_id=published.policy_id,
            request=request,
            metadata={
                "version": published.version,
                "decision": published.decision.value,
                "store": "supabase",
            },
        )
        return _policy_read(published)
    record = PolicyDefinitionRecord(
        policy_id=domain.policy_id,
        version=domain.version,
        is_current=True,
        name=domain.name,
        description=domain.description,
        priority=domain.priority,
        enabled=domain.enabled,
        match_mode=domain.match_mode.value,
        conditions=to_primitive(domain.conditions),
        decision=domain.decision.value,
        reason_template=domain.reason_template,
        approval_role=domain.approval_role,
        parameters=domain.parameters,
        required_facts=list(domain.required_facts),
        action_classes=list(domain.action_classes),
        owner=domain.owner,
        change_reason=domain.change_reason,
        effective_from=domain.effective_from,
        expires_at=domain.expires_at,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    await audit.log(
        action="policy.create",
        description=f"Created policy {record.name} v{record.version}",
        actor=user,
        category="policy",
        resource_type="policy",
        resource_id=record.policy_id,
        request=request,
        metadata={"version": record.version, "decision": record.decision},
    )
    return _policy_read(record)


@router.patch("/policies/{policy_id}", response_model=PolicyRead)
async def update_policy(
    policy_id: str,
    payload: PolicyUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    if _supabase_policy_store_enabled():
        try:
            policies = await _load_policy_definitions(db, policy_id=policy_id)
        except (SupabaseConfigurationError, SupabaseAPIError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        if len(policies) != 1:
            raise HTTPException(status_code=404, detail="Policy not found")
        current_policy = policies[0]
        update_data = _dump(payload, exclude_unset=True)
        merged = {
            "name": current_policy.name,
            "description": current_policy.description,
            "priority": current_policy.priority,
            "enabled": current_policy.enabled,
            "match_mode": current_policy.match_mode.value,
            "conditions": to_primitive(current_policy.conditions),
            "decision": current_policy.decision.value,
            "reason_template": current_policy.reason_template,
            "approval_role": current_policy.approval_role,
            "parameters": dict(current_policy.parameters),
            "required_facts": list(current_policy.required_facts),
            "action_classes": list(current_policy.action_classes),
            "owner": current_policy.owner,
            "change_reason": current_policy.change_reason,
            "effective_from": current_policy.effective_from,
            "expires_at": current_policy.expires_at,
            **update_data,
        }
        now = utc_now()
        try:
            domain = PolicyDefinition(
                policy_id=policy_id,
                version=current_policy.version + 1,
                created_at=current_policy.created_at,
                updated_at=now,
                conditions=tuple(
                    PolicyCondition(
                        field_path=item["field_path"],
                        operator=PolicyOperator(item["operator"]),
                        value=item.get("value"),
                    )
                    for item in merged["conditions"]
                ),
                match_mode=PolicyMatchMode(merged["match_mode"]),
                decision=PolicyDecision(merged["decision"]),
                **{
                    key: value
                    for key, value in merged.items()
                    if key not in {"conditions", "match_mode", "decision"}
                },
            )
            published = await SupabaseGovernancePolicyStore.from_environment().publish(
                domain
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except (SupabaseConfigurationError, SupabaseAPIError, RuntimeError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        await audit.log(
            action="policy.version",
            description=f"Published {published.name} v{published.version}",
            actor=user,
            category="policy",
            resource_type="policy",
            resource_id=published.policy_id,
            request=request,
            metadata={
                "previous_version": current_policy.version,
                "version": published.version,
                "store": "supabase",
            },
        )
        return _policy_read(published)

    current = (
        db.query(PolicyDefinitionRecord)
        .filter(
            PolicyDefinitionRecord.policy_id == policy_id,
            PolicyDefinitionRecord.is_current.is_(True),
        )
        .with_for_update()
        .first()
    )
    if current is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    update_data = _dump(payload, exclude_unset=True)
    merged = {
        "name": current.name,
        "description": current.description,
        "priority": current.priority,
        "enabled": current.enabled,
        "match_mode": current.match_mode,
        "conditions": current.conditions,
        "decision": current.decision,
        "reason_template": current.reason_template,
        "approval_role": current.approval_role,
        "parameters": current.parameters or {},
        "required_facts": current.required_facts or [],
        "action_classes": current.action_classes or [],
        "owner": current.owner or "command_center",
        "change_reason": current.change_reason or "",
        "effective_from": current.effective_from,
        "expires_at": current.expires_at,
        **update_data,
    }
    now = utc_now()
    try:
        domain = PolicyDefinition(
            policy_id=policy_id,
            version=current.version + 1,
            created_at=_aware(current.created_at),
            updated_at=now,
            conditions=tuple(
                PolicyCondition(
                    field_path=item["field_path"],
                    operator=PolicyOperator(item["operator"]),
                    value=item.get("value"),
                )
                for item in merged["conditions"]
            ),
            match_mode=PolicyMatchMode(merged["match_mode"]),
            decision=PolicyDecision(merged["decision"]),
            **{
                key: value
                for key, value in merged.items()
                if key not in {"conditions", "match_mode", "decision"}
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    current.is_current = False
    record = PolicyDefinitionRecord(
        policy_id=domain.policy_id,
        version=domain.version,
        is_current=True,
        name=domain.name,
        description=domain.description,
        priority=domain.priority,
        enabled=domain.enabled,
        match_mode=domain.match_mode.value,
        conditions=to_primitive(domain.conditions),
        decision=domain.decision.value,
        reason_template=domain.reason_template,
        approval_role=domain.approval_role,
        parameters=domain.parameters,
        required_facts=list(domain.required_facts),
        action_classes=list(domain.action_classes),
        owner=domain.owner,
        change_reason=domain.change_reason,
        effective_from=domain.effective_from,
        expires_at=domain.expires_at,
        created_at=domain.created_at,
        updated_at=domain.updated_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    await audit.log(
        action="policy.version",
        description=f"Published {record.name} v{record.version}",
        actor=user,
        category="policy",
        resource_type="policy",
        resource_id=record.policy_id,
        request=request,
        metadata={"previous_version": current.version, "version": record.version},
    )
    return _policy_read(record)


@router.post("/policies/evaluate", response_model=PolicyEvaluateResponse)
async def evaluate_current_policies(
    payload: PolicyEvaluateRequest,
    request: Request,
    x_command_center_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    _verify_run_token(payload.run_id, x_command_center_secret)
    run = _require_run(db, payload.run_id)
    if run.incident_id != payload.incident_id:
        raise HTTPException(status_code=409, detail="Run and incident IDs do not match")
    facts = dict(payload.facts)
    if payload.operator_run_ids is not None:
        try:
            facts = await SupabasePolicyFactsLoader.from_environment().load(
                incident_id=payload.incident_id,
                operator_run_ids=_dump(payload.operator_run_ids),
                proposed_action=(
                    payload.facts.get("proposed_action")
                    if isinstance(payload.facts.get("proposed_action"), Mapping)
                    else None
                ),
                base_facts=payload.facts,
            )
        except PolicyFactsError as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Exact Operator lineage could not be assembled",
                    "reason": str(exc),
                    "decision": "review",
                },
            ) from exc
        except (SupabaseConfigurationError, SupabaseAPIError) as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "message": "Operator evidence is unavailable; execution is not authorized",
                    "reason": str(exc),
                    "decision": "review",
                },
            ) from exc
    try:
        policy_definitions = await _load_policy_definitions(db)
    except (SupabaseConfigurationError, SupabaseAPIError) as exc:
        return _policy_store_failure_response(
            db,
            run=run,
            facts=facts,
            reason=(
                "Governance policy store is unavailable; execution is not "
                f"authorized: {exc}"
            ),
        )
    if not policy_definitions:
        raise HTTPException(status_code=409, detail="No policies are configured")
    evaluations = evaluate_policies(
        policy_definitions,
        run_id=payload.run_id,
        incident_id=payload.incident_id,
        facts=facts,
    )
    for evaluation in evaluations:
        db.add(
            PolicyEvaluationRecord(
                evaluation_id=evaluation.evaluation_id,
                policy_id=evaluation.policy_id,
                policy_version=evaluation.policy_version,
                run_id=evaluation.run_id,
                incident_id=evaluation.incident_id,
                matched=evaluation.matched,
                decision=evaluation.decision.value,
                reason=evaluation.reason,
                reason_code=evaluation.reason_code,
                facts=evaluation.facts,
                input_hash=evaluation.input_hash,
                candidate_action_id=evaluation.candidate_action_id,
                matched_conditions=list(evaluation.matched_conditions),
                missing_facts=list(evaluation.missing_facts),
                approval_role=evaluation.approval_role,
                evaluated_at=evaluation.evaluated_at,
            )
        )
    if _supabase_policy_store_enabled():
        try:
            await SupabaseGovernancePolicyStore.from_environment().record_evaluations(
                evaluations
            )
        except (SupabaseConfigurationError, SupabaseAPIError) as exc:
            db.rollback()
            run = _require_run(db, payload.run_id)
            return _policy_store_failure_response(
                db,
                run=run,
                facts=facts,
                reason=(
                    "Policy audit persistence failed; execution is not "
                    f"authorized: {exc}"
                ),
            )
    decision = effective_decision(evaluations)
    workbench_record = None
    if decision in {PolicyDecision.REVIEW, PolicyDecision.BLOCK}:
        target_status = (
            WorkflowStatus.AWAITING_APPROVAL
            if decision is PolicyDecision.REVIEW
            else WorkflowStatus.NEEDS_REVIEW
        )
        try:
            transitioned = _workflow_domain(run).transition(
                target_status, updated_at=utc_now()
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        run.status = transitioned.status.value
        run.updated_at = transitioned.updated_at
        existing = (
            db.query(WorkbenchItemRecord)
            .filter(
                WorkbenchItemRecord.run_id == run.run_id,
                WorkbenchItemRecord.status == WorkbenchStatus.OPEN.value,
            )
            .first()
        )
        if existing is None:
            raw_severity = facts.get("severity", Severity.UNKNOWN.value)
            try:
                severity = Severity(raw_severity).value
            except ValueError:
                severity = Severity.UNKNOWN.value
            matched_reasons = [item.reason for item in evaluations if item.matched]
            workbench_record = WorkbenchItemRecord(
                item_id=f"WB-{uuid4().hex}",
                run_id=run.run_id,
                incident_id=run.incident_id,
                title=(
                    "Policy approval required"
                    if decision is PolicyDecision.REVIEW
                    else "Policy blocked the proposed action"
                ),
                summary="; ".join(matched_reasons) or "Governed action requires review",
                severity=severity,
                proposed_action=facts.get("proposed_action", {}),
                alternatives=facts.get("alternatives", []),
                policy_evaluation_ids=[item.evaluation_id for item in evaluations],
                evidence=facts.get("evidence", []),
                assigned_to=next(
                    (item.approval_role for item in evaluations if item.approval_role),
                    None,
                ),
                status=WorkbenchStatus.OPEN.value,
                version=1,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            db.add(workbench_record)
        else:
            workbench_record = existing
    db.commit()
    await audit.log(
        action="policy.evaluate",
        description=f"Evaluated {len(evaluations)} policies: {decision.value}",
        actor=user,
        category="policy",
        resource_type="workflow_run",
        resource_id=run.run_id,
        request=request,
        metadata={
            "incident_id": run.incident_id,
            "decision": decision.value,
            "evaluation_ids": [item.evaluation_id for item in evaluations],
        },
    )
    roles = sorted({item.approval_role for item in evaluations if item.approval_role})
    return PolicyEvaluateResponse(
        effective_decision=decision,
        approval_roles=roles,
        evaluations=[
            PolicyEvaluationRead(**to_primitive(item)) for item in evaluations
        ],
        workbench_item_id=(workbench_record.item_id if workbench_record else None),
    )


@router.get("/notifications", response_model=list[NotificationRead])
def list_notifications(
    run_id: str | None = None,
    notification_type: str | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(NotificationRecord)
    if run_id:
        query = query.filter(NotificationRecord.run_id == run_id)
    if notification_type:
        query = query.filter(NotificationRecord.notification_type == notification_type)
    records = query.order_by(NotificationRecord.occurred_at.desc()).limit(limit).all()
    return [_notification_read(record) for record in records]


@router.get("/workbench", response_model=list[WorkbenchItemRead])
def list_workbench_items(
    status: WorkbenchStatus | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(WorkbenchItemRecord)
    if status is not None:
        query = query.filter(
            WorkbenchItemRecord.status == WorkbenchStatus(status).value
        )
    records = query.order_by(WorkbenchItemRecord.created_at.desc()).limit(limit).all()
    return [_workbench_read(record) for record in records]


@router.post("/workbench/sync-supervity", response_model=SupervityFormSyncRead)
async def sync_supervity_user_forms(
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    try:
        client = SupervityClient.from_environment()
        forms = await _list_all_supervity_user_forms(client)
    except SupervityConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SupervityAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    form_status_counts = {
        "pending": 0,
        "approved": 0,
        "modified": 0,
        "rejected": 0,
        "expired": 0,
        "other": 0,
    }

    matched_runs = 0
    items_created = 0
    items_updated = 0
    forms_skipped = 0
    run_payloads: dict[str, Mapping[str, Any] | None] = {}
    actionable_pending_auto_run_ids: set[str] = set()
    remote_form_ids: set[str] = set()
    for form in forms:
        form_id = _remote_text(form, "id", "formId", "form_id")
        auto_run_id = _remote_text(form, "workflowRunId", "workflow_run_id", "runId")
        activity_run_id = _remote_text(form, "activityRunId", "activity_run_id")
        if not form_id or not auto_run_id or not activity_run_id:
            forms_skipped += 1
            continue
        remote_form_ids.add(form_id)
        form_status = (_remote_text(form, "status") or "pending").strip().lower()
        if auto_run_id not in run_payloads:
            try:
                run_payloads[auto_run_id] = await client.status(auto_run_id)
            except SupervityAPIError:
                run_payloads[auto_run_id] = None
        remote_run_payload = run_payloads[auto_run_id]
        remote_run = (
            _supervity_run_payload(remote_run_payload)
            if remote_run_payload is not None
            else {}
        )
        remote_run_status = _remote_text(remote_run, "status") or ""
        activity = (
            _supervity_form_activity(remote_run_payload, activity_run_id)
            if remote_run_payload is not None
            else None
        )
        activity_status = _remote_text(activity or {}, "status") or ""
        values: dict[str, Any] = {}
        approved: bool | None = None
        reviewed_at: datetime | None = None
        if remote_run_payload is not None:
            values, approved, reviewed_at = _supervity_form_submission(
                remote_run_payload,
                activity_run_id,
            )
        remote_decision = _remote_form_decision(form_status, values, approved)
        is_pending = form_status == "pending" and remote_decision is None
        expired_reason: str | None = None
        if is_pending and remote_run_payload is None:
            form_status_counts["other"] += 1
            forms_skipped += 1
            continue
        if is_pending and _workflow_status_from_supervity(remote_run_status) in {
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        }:
            expired_reason = (
                "Supervity workflow is "
                f"{remote_run_status.strip().lower() or 'terminal'}; "
                "the pending form is no longer actionable"
            )
            is_pending = False
        elif is_pending and activity is None:
            form_status_counts["other"] += 1
            forms_skipped += 1
            continue
        elif is_pending and activity_status.strip().lower() not in {
            "",
            "waiting",
            "paused",
            "pending",
            "awaiting_approval",
        }:
            expired_reason = (
                "Supervity form activity is "
                f"{activity_status.strip().lower()}; the form is no longer actionable"
            )
            is_pending = False

        if is_pending:
            form_status_counts["pending"] += 1
            actionable_pending_auto_run_ids.add(auto_run_id)
        elif remote_decision is WorkbenchDecision.APPROVE:
            form_status_counts["approved"] += 1
        elif remote_decision is WorkbenchDecision.MODIFY:
            form_status_counts["modified"] += 1
        elif remote_decision is WorkbenchDecision.REJECT:
            form_status_counts["rejected"] += 1
        elif expired_reason is not None:
            form_status_counts["expired"] += 1
        else:
            form_status_counts["other"] += 1
        existing = (
            db.query(WorkbenchItemRecord)
            .filter(WorkbenchItemRecord.supervity_form_id == form_id)
            .first()
        )
        run = (
            db.query(WorkflowRunRecord)
            .filter(WorkflowRunRecord.auto_run_id == auto_run_id)
            .first()
        )
        if run is None and existing is not None:
            run = (
                db.query(WorkflowRunRecord)
                .filter(WorkflowRunRecord.run_id == existing.run_id)
                .first()
            )
        if run is None and not is_pending:
            forms_skipped += 1
            continue

        form_model: dict[str, Any] | None = None
        parsed_form = parse_supervity_user_form({})
        if is_pending:
            try:
                form_model = parse_supervity_user_form(
                    await client.get_user_form(form_id)
                )
            except SupervityAPIError:
                form_model = None
            parsed_form = form_model or parsed_form
        form_severity = _parsed_form_severity(parsed_form)

        if run is None:
            incident_id = next(
                (
                    item["value"]
                    for item in parsed_form["context"]
                    if item["label"].strip().lower() == "incident id" and item["value"]
                ),
                f"AUTO-{auto_run_id[:32]}",
            )
            run = WorkflowRunRecord(
                run_id=(
                    "RUN-SUPERVITY-"
                    f"{hashlib.sha256(auto_run_id.encode()).hexdigest()[:24].upper()}"
                ),
                incident_id=incident_id,
                status=WorkflowStatus.AWAITING_APPROVAL.value,
                severity=form_severity.value,
                source="supervity_user_form",
                source_ref=auto_run_id,
                input_payload={
                    "source": "supervity_user_form",
                    "workflow_id": _remote_text(form, "workflowId", "workflow_id"),
                    "workflow_name": _remote_text(
                        form, "workflowName", "workflow_name"
                    ),
                    "workflow_description": _remote_text(
                        form, "workflowDescription", "workflow_description"
                    ),
                },
                output_payload=None,
                requested_by=None,
                auto_run_id=auto_run_id,
                current_operator=_remote_text(
                    form, "workflowStepName", "workflow_step_name"
                ),
                plan_run_id=None,
                error=None,
                cost_at_risk_myr=Decimal("0"),
                cost_avoided_myr=Decimal("0"),
                time_to_mitigation_hours=None,
                created_at=_remote_datetime(form.get("createdAt")),
                updated_at=utc_now(),
            )
            db.add(run)
            db.flush()
        elif is_pending:
            run.severity = form_severity.value
        matched_runs += 1

        if not is_pending:
            if remote_run_status and (
                auto_run_id not in actionable_pending_auto_run_ids
            ):
                run.status = _workflow_status_from_supervity(remote_run_status).value
                run.updated_at = _remote_datetime(
                    remote_run.get("updatedAt") or remote_run.get("updated_at")
                )
                run.error = _remote_text(
                    remote_run,
                    "errorDetails",
                    "error_details",
                    "error",
                )
            if existing is not None:
                existing.supervity_activity_run_id = activity_run_id
                if expired_reason is not None:
                    _expire_remote_form(existing, reason=expired_reason)
                else:
                    existing.supervity_form_status = form_status
                    _apply_remote_form_resolution(
                        existing,
                        form=form,
                        form_status=form_status,
                        values=values,
                        approved=approved,
                        reviewed_at=reviewed_at,
                    )
                existing.updated_at = utc_now()
                items_updated += 1
            continue

        workflow_name = _remote_text(form, "workflowName", "workflow_name")
        step_name = _remote_text(form, "workflowStepName", "workflow_step_name")
        step_description = _remote_text(
            form,
            "workflowStepDescription",
            "workflow_step_description",
            "workflowDescription",
            "workflow_description",
        )
        title = (
            parsed_form["title"] or f"{step_name or 'Auto workflow'} approval required"
        )
        summary = (
            parsed_form["description"]
            or step_description
            or f"{workflow_name or 'Auto'} is waiting for a human decision."
        )
        proposed_action = {
            "source": "supervity_user_form",
            "workflow_name": workflow_name,
            "workflow_step": step_name,
            "user_form": parsed_form,
        }
        if existing is None:
            existing = (
                db.query(WorkbenchItemRecord)
                .filter(
                    WorkbenchItemRecord.run_id == run.run_id,
                    WorkbenchItemRecord.status == WorkbenchStatus.OPEN.value,
                )
                .order_by(WorkbenchItemRecord.created_at.desc())
                .first()
            )
        if existing is not None:
            existing.supervity_form_id = form_id
            existing.supervity_activity_run_id = activity_run_id
            existing.supervity_form_status = form_status
            existing.severity = form_severity.value
            if existing.status != WorkbenchStatus.OPEN.value:
                existing.status = WorkbenchStatus.OPEN.value
                existing.decision = None
                existing.decision_by = None
                existing.decision_reason = None
                existing.decision_payload = None
                existing.decision_source = None
                existing.decision_external_ref = None
                existing.decided_at = None
                existing.version += 1
            if form_model is not None:
                existing.title = title
                existing.summary = summary
                existing.proposed_action = proposed_action
            existing.updated_at = utc_now()
            items_updated += 1
        elif form_status == "pending":
            now = utc_now()
            db.add(
                WorkbenchItemRecord(
                    item_id=f"WB-{uuid4().hex}",
                    run_id=run.run_id,
                    incident_id=run.incident_id,
                    title=title,
                    summary=summary,
                    severity=run.severity,
                    proposed_action=proposed_action,
                    alternatives=[],
                    policy_evaluation_ids=[],
                    evidence=[],
                    assigned_to=None,
                    supervity_form_id=form_id,
                    supervity_activity_run_id=activity_run_id,
                    supervity_form_status=form_status,
                    status=WorkbenchStatus.OPEN.value,
                    version=1,
                    created_at=_remote_datetime(form.get("createdAt"), default=now),
                    updated_at=now,
                )
            )
            items_created += 1
        if run.status not in {
            WorkflowStatus.COMPLETED.value,
            WorkflowStatus.FAILED.value,
            WorkflowStatus.CANCELLED.value,
        }:
            run.status = WorkflowStatus.AWAITING_APPROVAL.value
            run.updated_at = utc_now()
            run.error = None

    stale_query = db.query(WorkbenchItemRecord).filter(
        WorkbenchItemRecord.status == WorkbenchStatus.OPEN.value,
        WorkbenchItemRecord.supervity_form_id.isnot(None),
    )
    if remote_form_ids:
        stale_query = stale_query.filter(
            ~WorkbenchItemRecord.supervity_form_id.in_(remote_form_ids)
        )
    for stale_item in stale_query.all():
        if _expire_remote_form(
            stale_item,
            reason=(
                "Supervity no longer returns this form in the authoritative "
                "user-form inventory"
            ),
        ):
            items_updated += 1

    db.commit()
    await audit.log(
        action="workbench.sync",
        description="Reconciled Supervity user forms from the API",
        actor=user,
        category="workbench",
        resource_type="user_form",
        resource_id="supervity",
        request=request,
        metadata={
            "forms_seen": len(forms),
            "form_status_counts": form_status_counts,
            "matched_runs": matched_runs,
            "items_created": items_created,
            "items_updated": items_updated,
            "forms_skipped": forms_skipped,
        },
    )
    return SupervityFormSyncRead(
        forms_seen=len(forms),
        pending_forms=form_status_counts["pending"],
        approved_forms=form_status_counts["approved"],
        modified_forms=form_status_counts["modified"],
        rejected_forms=form_status_counts["rejected"],
        expired_forms=form_status_counts["expired"],
        other_forms=form_status_counts["other"],
        matched_runs=matched_runs,
        items_created=items_created,
        items_updated=items_updated,
        forms_skipped=forms_skipped,
    )


@router.post("/workbench", response_model=WorkbenchItemRead, status_code=201)
async def create_workbench_item(
    payload: WorkbenchItemCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    run = _require_run(db, payload.run_id)
    if run.incident_id != payload.incident_id:
        raise HTTPException(status_code=409, detail="Run and incident IDs do not match")
    now = utc_now()
    record = WorkbenchItemRecord(
        item_id=f"WB-{uuid4().hex}",
        run_id=payload.run_id,
        incident_id=payload.incident_id,
        title=payload.title,
        summary=payload.summary,
        severity=Severity(payload.severity).value,
        proposed_action=payload.proposed_action,
        alternatives=payload.alternatives,
        policy_evaluation_ids=payload.policy_evaluation_ids,
        evidence=[_dump(item) for item in payload.evidence],
        assigned_to=payload.assigned_to,
        status=WorkbenchStatus.OPEN.value,
        version=1,
        created_at=now,
        updated_at=now,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    await audit.log(
        action="workbench.create",
        description=f"Created Workbench decision for {record.incident_id}",
        actor=user,
        category="workbench",
        resource_type="workbench_item",
        resource_id=record.item_id,
        request=request,
        metadata={"run_id": record.run_id, "severity": record.severity},
    )
    return _workbench_read(record)


@router.post("/workbench/{item_id}/decision", response_model=WorkbenchItemRead)
async def decide_workbench_item(
    item_id: str,
    payload: WorkbenchDecisionRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    record = (
        db.query(WorkbenchItemRecord)
        .filter(WorkbenchItemRecord.item_id == item_id)
        .with_for_update()
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Workbench item not found")
    if record.version != payload.expected_version:
        raise HTTPException(
            status_code=409, detail="Workbench item changed; refresh and retry"
        )
    decision = WorkbenchDecision(payload.decision)
    try:
        resolved = _workbench_domain(record).resolve(
            decision=decision,
            decided_by=_actor_label(user),
            reason=payload.reason,
            payload=payload.payload,
            decided_at=utc_now(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    run = _require_run(db, record.run_id)
    if (
        run.status == WorkflowStatus.NEEDS_REVIEW.value
        and decision is WorkbenchDecision.APPROVE
    ):
        raise HTTPException(
            status_code=409,
            detail="A policy-blocked action must be modified or rejected, not approved",
        )

    if (
        record.supervity_form_id
        and record.supervity_activity_run_id
        and run.auto_run_id
        and decision is not WorkbenchDecision.ESCALATE
    ):
        try:
            client = SupervityClient.from_environment()
            latest_notification = (
                db.query(NotificationRecord)
                .filter(
                    NotificationRecord.run_id == record.run_id,
                    NotificationRecord.notification_type == "review_required",
                    NotificationRecord.status.in_(("delivered", "updated")),
                )
                .order_by(NotificationRecord.occurred_at.desc())
                .first()
            )
            decision_fields = {
                "workbench_item_id": record.item_id,
                "command_center_run_id": record.run_id,
                "incident_id": record.incident_id,
                "decision_source": "command_center",
                "action": decision.value.title(),
                "decision": decision.value,
                "reason": resolved.decision_reason,
                "payload": resolved.decision_payload,
                "decision_by": resolved.decision_by,
            }
            stored_form = (record.proposed_action or {}).get("user_form")
            stored_fields = (
                stored_form.get("fields") if isinstance(stored_form, Mapping) else None
            )
            if isinstance(stored_fields, list) and isinstance(
                resolved.decision_payload, Mapping
            ):
                allowed_names = {
                    field.get("name")
                    for field in stored_fields
                    if isinstance(field, Mapping) and isinstance(field.get("name"), str)
                }
                decision_fields.update(
                    {
                        name: resolved.decision_payload[name]
                        for name in allowed_names
                        if name in resolved.decision_payload
                    }
                )
            if latest_notification is not None:
                decision_fields.update(
                    {
                        "slack_channel_id": latest_notification.destination,
                        "slack_message_ts": latest_notification.external_ref,
                        "slack_thread_ts": latest_notification.thread_ref,
                    }
                )
            await client.submit_user_form(
                activity_run_id=record.supervity_activity_run_id,
                status=(
                    "reject" if decision is WorkbenchDecision.REJECT else "approve"
                ),
                fields=decision_fields,
            )
            (
                confirmed_form,
                confirmed_status,
                remote_run_payload,
                values,
                approved,
                reviewed_at,
            ) = await _confirm_supervity_form_decision(
                client,
                form_id=record.supervity_form_id,
                activity_run_id=record.supervity_activity_run_id,
                auto_run_id=run.auto_run_id,
                expected_decision=decision,
            )
            record.supervity_form_status = confirmed_status
            if not _apply_remote_form_resolution(
                record,
                form=confirmed_form,
                form_status=confirmed_status,
                values=values,
                approved=approved,
                reviewed_at=reviewed_at,
            ):
                raise SupervityAPIError(
                    "Supervity form confirmation could not resolve the Workbench item"
                )
            record.decision_source = "command_center"
            remote_run = _supervity_run_payload(remote_run_payload)
            remote_run_status = _remote_text(remote_run, "status")
            if remote_run_status:
                run.status = _workflow_status_from_supervity(remote_run_status).value
                run.updated_at = _remote_datetime(
                    remote_run.get("updatedAt") or remote_run.get("updated_at")
                )
                run.error = _remote_text(
                    remote_run,
                    "errorDetails",
                    "error_details",
                    "error",
                )
            _set_integration_health(
                db,
                integration_id="supervity-auto",
                name="Supervity Auto",
                category="agent_platform",
                status="healthy",
            )
            db.commit()
            db.refresh(record)
        except (SupervityConfigurationError, SupervityAPIError) as exc:
            db.rollback()
            failed_run = _require_run(db, record.run_id)
            if failed_run.status == WorkflowStatus.AWAITING_APPROVAL.value:
                failed_run.status = WorkflowStatus.NEEDS_REVIEW.value
            failed_run.error = str(exc)
            _set_integration_health(
                db,
                integration_id="supervity-auto",
                name="Supervity Auto",
                category="agent_platform",
                status="degraded",
                last_error=str(exc),
            )
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        await audit.log(
            action=f"workbench.{decision.value}",
            description=f"{decision.value.title()} decision for {record.incident_id}",
            actor=user,
            category="workbench",
            resource_type="workbench_item",
            resource_id=record.item_id,
            request=request,
            metadata={
                "run_id": record.run_id,
                "decision": record.decision,
                "reason": record.decision_reason,
                "version": record.version,
                "remote_form_status": record.supervity_form_status,
            },
        )
        return _workbench_read(record)

    record.status = resolved.status.value
    record.decision = resolved.decision.value
    record.decision_by = resolved.decision_by
    record.decision_reason = resolved.decision_reason
    record.decision_payload = resolved.decision_payload
    record.decision_source = "command_center"
    record.decision_external_ref = None
    record.decided_at = resolved.decided_at
    record.updated_at = resolved.updated_at
    record.version = resolved.version
    db.commit()
    db.refresh(record)
    resume_error = None
    if decision is WorkbenchDecision.ESCALATE:
        transitioned = _workflow_domain(run).transition(
            WorkflowStatus.NEEDS_REVIEW,
            updated_at=utc_now(),
        )
        run.status = transitioned.status.value
        run.updated_at = transitioned.updated_at
        run.error = None
    else:
        if not run.auto_run_id:
            resume_error = "Cannot resume workflow because no Auto run ID is recorded"
        else:
            try:
                client = SupervityClient.from_environment()
                latest_notification = (
                    db.query(NotificationRecord)
                    .filter(
                        NotificationRecord.run_id == record.run_id,
                        NotificationRecord.notification_type == "review_required",
                        NotificationRecord.status.in_(("delivered", "updated")),
                    )
                    .order_by(NotificationRecord.occurred_at.desc())
                    .first()
                )
                decision_fields = {
                    "workbench_item_id": record.item_id,
                    "command_center_run_id": record.run_id,
                    "incident_id": record.incident_id,
                    "decision_source": record.decision_source,
                    "action": decision.value.title(),
                    "decision": decision.value,
                    "reason": record.decision_reason,
                    "payload": record.decision_payload,
                    "decision_by": record.decision_by,
                }
                stored_form = (record.proposed_action or {}).get("user_form")
                stored_fields = (
                    stored_form.get("fields")
                    if isinstance(stored_form, Mapping)
                    else None
                )
                if isinstance(stored_fields, list) and isinstance(
                    record.decision_payload, Mapping
                ):
                    allowed_names = {
                        field.get("name")
                        for field in stored_fields
                        if isinstance(field, Mapping)
                        and isinstance(field.get("name"), str)
                    }
                    decision_fields.update(
                        {
                            name: record.decision_payload[name]
                            for name in allowed_names
                            if name in record.decision_payload
                        }
                    )
                if latest_notification is not None:
                    decision_fields.update(
                        {
                            "slack_channel_id": latest_notification.destination,
                            "slack_message_ts": latest_notification.external_ref,
                            "slack_thread_ts": latest_notification.thread_ref,
                        }
                    )
                if record.supervity_activity_run_id:
                    form_decision = (
                        "reject" if decision is WorkbenchDecision.REJECT else "approve"
                    )
                    await client.submit_user_form(
                        activity_run_id=record.supervity_activity_run_id,
                        status=form_decision,
                        fields=decision_fields,
                    )
                    record.supervity_form_status = (
                        "rejected" if form_decision == "reject" else "approved"
                    )
                else:
                    await client.resume(
                        run_id=run.auto_run_id,
                        decision=decision_fields,
                    )
            except (SupervityConfigurationError, SupervityAPIError) as exc:
                resume_error = str(exc)
        if resume_error:
            if run.status == WorkflowStatus.AWAITING_APPROVAL.value:
                run.status = WorkflowStatus.NEEDS_REVIEW.value
            run.error = resume_error
            _set_integration_health(
                db,
                integration_id="supervity-auto",
                name="Supervity Auto",
                category="agent_platform",
                status="degraded",
                last_error=resume_error,
            )
        else:
            if decision is WorkbenchDecision.REJECT:
                target_status = WorkflowStatus.CANCELLED
            elif run.status == WorkflowStatus.NEEDS_REVIEW.value:
                target_status = WorkflowStatus.RUNNING
            else:
                target_status = WorkflowStatus.EXECUTING
            try:
                transitioned = _workflow_domain(run).transition(
                    target_status,
                    updated_at=utc_now(),
                )
            except ValueError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            run.status = transitioned.status.value
            run.updated_at = transitioned.updated_at
            run.error = None
            _set_integration_health(
                db,
                integration_id="supervity-auto",
                name="Supervity Auto",
                category="agent_platform",
                status="healthy",
            )
    db.commit()
    await audit.log(
        action=f"workbench.{decision.value}",
        description=f"{decision.value.title()} decision for {record.incident_id}",
        actor=user,
        category="workbench",
        resource_type="workbench_item",
        resource_id=record.item_id,
        request=request,
        metadata={
            "run_id": record.run_id,
            "decision": decision.value,
            "reason": record.decision_reason,
            "version": record.version,
            "resume_error": resume_error,
        },
    )
    return _workbench_read(record)


@router.get(
    "/supervity/integrations",
    response_model=SupervityIntegrationInventoryRead,
)
async def supervity_integration_inventory():
    try:
        payload = await SupervityClient.from_environment().integration_inventory()
    except SupervityConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SupervityAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    actions: list[SupervityIntegrationActionRead] = []
    action_counts: dict[str, int] = {}
    for item in _remote_list(payload, "userActions", "user_actions", "actions"):
        action = item.get("action") if isinstance(item.get("action"), Mapping) else item
        group = item.get("group") if isinstance(item.get("group"), Mapping) else {}
        integration = (
            _remote_text(group, "displayName", "name")
            or _remote_text(item, "integrationSlug", "integration_slug")
            or "Unknown"
        )
        name = _remote_text(action, "displayName", "name") or "Unnamed action"
        description = _remote_text(action, "description")
        actions.append(
            SupervityIntegrationActionRead(
                name=name,
                integration=integration,
                description=description,
            )
        )
        count_key = _integration_key(_remote_text(group, "name") or integration)
        action_counts[count_key] = action_counts.get(count_key, 0) + 1

    accounts: list[SupervityConnectedAccountRead] = []
    for item in _remote_list(
        payload, "integrations", "connectedIntegrations", "connected_accounts"
    ):
        slug = _remote_text(item, "integrationSlug", "integration_slug", "slug")
        if not slug:
            slug = "unknown"
        accounts.append(
            SupervityConnectedAccountRead(
                name=_remote_text(item, "accountIdentifier", "account_identifier")
                or "Connected account",
                integration=slug,
                status="connected",
                actions_count=action_counts.get(_integration_key(slug), 0),
            )
        )
    return SupervityIntegrationInventoryRead(
        connected_accounts=accounts,
        actions=actions,
    )


@router.get("/supervity/schedules", response_model=list[SupervityScheduleRead])
async def supervity_schedules():
    try:
        schedules = await SupervityClient.from_environment().list_schedules(limit=100)
    except SupervityConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SupervityAPIError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    normalized: list[SupervityScheduleRead] = []
    for item in schedules:
        schedule_id = _remote_text(item, "id", "scheduleId", "schedule_id")
        if not schedule_id:
            continue
        definition = (
            item.get("definition")
            if isinstance(item.get("definition"), Mapping)
            else {}
        )
        expression_parts: list[str] = []
        if isinstance(definition.get("intervals"), list):
            expression_parts.append(
                f"intervals: {json.dumps(definition['intervals'], default=str)}"
            )
        if isinstance(definition.get("calendars"), list):
            expression_parts.append(
                f"calendars: {json.dumps(definition['calendars'], default=str)}"
            )
        workflow_name = _remote_text(item, "workflowName", "workflow_name")
        name = (
            _remote_text(item, "description") or workflow_name or "Scheduled workflow"
        )
        normalized.append(
            SupervityScheduleRead(
                schedule_id=schedule_id,
                name=name,
                workflow_name=workflow_name,
                status="paused" if item.get("isPaused") is True else "active",
                timezone=_remote_text(definition, "timezone"),
                expression="; ".join(expression_parts) or None,
                next_run_at=None,
                parameters=_sanitize_remote(definition),
            )
        )
    return normalized


@router.get("/integrations", response_model=list[IntegrationHealthRead])
async def list_integrations(db: Session = Depends(get_db)):
    await reconcile_supervity_integration_health(db)
    records = (
        db.query(IntegrationHealthRecord)
        .order_by(IntegrationHealthRecord.category, IntegrationHealthRecord.name)
        .all()
    )
    return [
        IntegrationHealthRead(
            integration_id=record.integration_id,
            name=record.name,
            category=record.category,
            status=record.status,
            checked_at=record.checked_at,
            last_success_at=record.last_success_at,
            last_error=record.last_error,
            records_seen=record.records_seen,
            metadata=_integration_metadata(record),
        )
        for record in records
    ]


@router.put("/integrations/{integration_id}", response_model=IntegrationHealthRead)
async def upsert_integration(
    integration_id: str,
    payload: IntegrationHealthUpsert,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    record = (
        db.query(IntegrationHealthRecord)
        .filter(IntegrationHealthRecord.integration_id == integration_id)
        .first()
    )
    if record is None:
        record = IntegrationHealthRecord(integration_id=integration_id)
        db.add(record)
    record.name = payload.name
    record.category = payload.category
    record.status = payload.status
    record.checked_at = payload.checked_at
    record.last_success_at = payload.last_success_at
    record.last_error = payload.last_error
    record.records_seen = payload.records_seen
    record.metadata_json = payload.metadata
    db.commit()
    db.refresh(record)
    await audit.log(
        action="integration.health",
        description=f"{record.name} is {record.status}",
        actor=user,
        category="integration",
        resource_type="integration",
        resource_id=integration_id,
        request=request,
        metadata={"status": record.status, "records_seen": record.records_seen},
    )
    return IntegrationHealthRead(
        integration_id=record.integration_id,
        name=record.name,
        category=record.category,
        status=record.status,
        checked_at=record.checked_at,
        last_success_at=record.last_success_at,
        last_error=record.last_error,
        records_seen=record.records_seen,
        metadata=_integration_metadata(record),
    )


@router.post(
    "/integrations/{integration_id}/test", response_model=IntegrationHealthRead
)
async def test_integration(
    integration_id: str,
    db: Session = Depends(get_db),
):
    if integration_id == "outlook":
        try:
            payload = await SupervityClient.from_environment().integration_inventory()
            accounts = _remote_list(
                payload,
                "integrations",
                "connectedIntegrations",
                "connected_accounts",
            )
            account = next(
                (
                    item
                    for item in accounts
                    if _integration_key(
                        _remote_text(
                            item,
                            "integrationSlug",
                            "integration_slug",
                            "slug",
                        )
                    )
                    == "outlook"
                ),
                None,
            )
            action_count = sum(
                1
                for item in _remote_list(
                    payload, "userActions", "user_actions", "actions"
                )
                if _integration_key(
                    _remote_text(
                        (
                            item.get("group")
                            if isinstance(item.get("group"), Mapping)
                            else item
                        ),
                        "name",
                        "displayName",
                        "integrationSlug",
                        "integration_slug",
                    )
                )
                == "outlook"
            )
            connected = account is not None
            record = _set_integration_health(
                db,
                integration_id="outlook",
                name="Outlook",
                category="channel",
                status="healthy" if connected else "disconnected",
                last_error=(
                    None if connected else "Outlook is not connected in Supervity"
                ),
            )
            metadata = dict(record.metadata_json or {})
            metadata.update(
                {
                    "status_source": "supervity_integrations_api",
                    "auto_account": (
                        _masked_account_label(
                            _remote_text(
                                account,
                                "accountIdentifier",
                                "account_identifier",
                            )
                        )
                        if account
                        else None
                    ),
                    "actions_count": action_count,
                }
            )
            record.metadata_json = metadata
        except SupervityConfigurationError as exc:
            record = _set_integration_health(
                db,
                integration_id="outlook",
                name="Outlook",
                category="channel",
                status="disconnected",
                last_error=str(exc),
            )
            db.commit()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except SupervityAPIError as exc:
            record = _set_integration_health(
                db,
                integration_id="outlook",
                name="Outlook",
                category="channel",
                status="degraded",
                last_error=str(exc),
            )
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    elif integration_id == "supabase":
        try:
            client = SupabaseClient.from_environment()
            table_counts = await client.count_tables(ORGANIZER_INPUT_TABLES)
            count = sum(table_counts.values())
            record = _set_integration_health(
                db,
                integration_id="supabase",
                name="Supabase",
                category="system_of_record",
                status="healthy",
                records_seen=count,
            )
        except SupabaseConfigurationError as exc:
            record = _set_integration_health(
                db,
                integration_id="supabase",
                name="Supabase",
                category="system_of_record",
                status="disconnected",
                last_error=str(exc),
            )
            db.commit()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except SupabaseAPIError as exc:
            record = _set_integration_health(
                db,
                integration_id="supabase",
                name="Supabase",
                category="system_of_record",
                status="degraded",
                last_error=str(exc),
            )
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
    elif integration_id == "supervity-auto":
        try:
            payload = await SupervityClient.from_environment().integration_inventory()
        except SupervityConfigurationError as exc:
            record = _set_integration_health(
                db,
                integration_id="supervity-auto",
                name="Supervity Auto",
                category="agent_platform",
                status="disconnected",
                last_error=str(exc),
            )
            db.commit()
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except SupervityAPIError as exc:
            record = _set_integration_health(
                db,
                integration_id="supervity-auto",
                name="Supervity Auto",
                category="agent_platform",
                status="degraded",
                last_error=str(exc),
            )
            db.commit()
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        current = (
            db.query(IntegrationHealthRecord)
            .filter(IntegrationHealthRecord.integration_id == integration_id)
            .first()
        )
        record = _set_integration_health(
            db,
            integration_id="supervity-auto",
            name="Supervity Auto",
            category="agent_platform",
            status="healthy",
            records_seen=(current.records_seen if current else None),
        )
        record.metadata_json = {
            **dict(record.metadata_json or {}),
            "status_source": "supervity_integrations_api",
            "actions_count": len(
                _remote_list(payload, "userActions", "user_actions", "actions")
            ),
        }
    else:
        raise HTTPException(
            status_code=409,
            detail="This integration is verified by its Auto smoke workflow and health callback",
        )
    db.commit()
    db.refresh(record)
    return IntegrationHealthRead(
        integration_id=record.integration_id,
        name=record.name,
        category=record.category,
        status=record.status,
        checked_at=record.checked_at,
        last_success_at=record.last_success_at,
        last_error=record.last_error,
        records_seen=record.records_seen,
        metadata=_integration_metadata(record),
    )


@router.post(
    "/outlook/oauth/start",
    response_model=OutlookAuthorizationStartRead,
)
def start_outlook_authorization(db: Session = Depends(get_db)):
    """Start a server-side delegated OAuth flow for the Outlook mailbox."""
    try:
        manager = OutlookTokenManager.from_environment(db)
        authorization_url = manager.start_authorization()
        db.commit()
    except (OutlookOAuthConfigurationError, OutlookAuthorizationError) as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return OutlookAuthorizationStartRead(authorization_url=authorization_url)


@router.get("/outlook/oauth/callback", include_in_schema=False)
def complete_outlook_authorization(
    request: Request,
    db: Session = Depends(get_db),
):
    """Complete Microsoft OAuth and store the encrypted MSAL token cache."""
    frontend_url = os.getenv("FRONTEND_URL", "").strip() or "http://localhost:3001"
    try:
        manager = OutlookTokenManager.from_environment(db)
        manager.complete_authorization(dict(request.query_params))
        metadata = {
            "purpose": "Inbound disruption notices",
            **outlook_oauth_configuration(),
            **manager.account_metadata(),
        }
        health = _set_integration_health(
            db,
            integration_id="outlook",
            name="Outlook",
            category="channel",
            status="unknown",
        )
        health.metadata_json = metadata
        db.commit()
    except (
        OutlookOAuthConfigurationError,
        OutlookAuthorizationError,
    ) as exc:
        db.rollback()
        health = _set_integration_health(
            db,
            integration_id="outlook",
            name="Outlook",
            category="channel",
            status="disconnected",
            last_error=str(exc),
        )
        health.metadata_json = {
            "purpose": "Inbound disruption notices",
            **outlook_oauth_configuration(),
        }
        db.commit()
        return RedirectResponse(
            f"{frontend_url.rstrip('/')}/data-manager"
            f"?outlook=error&detail={quote(str(exc), safe='')}",
            status_code=303,
        )
    return RedirectResponse(
        f"{frontend_url.rstrip('/')}/data-manager?outlook=connected",
        status_code=303,
    )


@router.post("/outlook/poll", response_model=OutlookPollRead)
async def poll_outlook(
    background_tasks: BackgroundTasks,
    request: Request,
    x_outlook_poll_secret: str | None = Header(
        default=None,
        alias="X-Outlook-Poll-Secret",
    ),
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    """Poll Inbox changes, create exactly-once runs, and dispatch them to Auto."""
    _authorize_outlook_poll(x_outlook_poll_secret, user)
    health = (
        db.query(IntegrationHealthRecord)
        .filter(IntegrationHealthRecord.integration_id == "outlook")
        .with_for_update()
        .first()
    )
    if health is None:
        health = _set_integration_health(
            db,
            integration_id="outlook",
            name="Outlook",
            category="channel",
            status="unknown",
        )
        health.metadata_json = {"purpose": "Inbound disruption notices"}
        db.flush()

    metadata = dict(health.metadata_json or {})
    cursor_value = metadata.get(OUTLOOK_DELTA_LINK_KEY)
    cursor = (
        cursor_value.strip()
        if isinstance(cursor_value, str) and cursor_value.strip()
        else None
    )
    polled_at = utc_now()
    baseline_established = cursor is None
    cursor_reset = False
    try:
        client = OutlookClient.from_environment(db=db)
        try:
            delta = await client.collect_inbox_delta(
                delta_link=cursor,
                max_pages=_outlook_poll_max_pages(),
            )
        except OutlookAPIError as exc:
            if cursor and exc.status_code == 410:
                delta = await client.collect_inbox_delta(
                    max_pages=_outlook_poll_max_pages(),
                )
                baseline_established = True
                cursor_reset = True
            else:
                raise
        inbox = await client.inbox_status()

        run_ids: list[str] = []
        duplicates_skipped = 0
        removed_skipped = 0
        if not baseline_established:
            for message in delta.messages:
                if isinstance(message.get("@removed"), Mapping):
                    removed_skipped += 1
                    continue
                message_id = message.get("id")
                if not isinstance(message_id, str) or not message_id.strip():
                    raise OutlookAPIError(
                        "Microsoft Graph delta message had no identifier"
                    )
                source_ref = _outlook_source_ref(message)
                existing = (
                    db.query(WorkflowRunRecord)
                    .filter(
                        WorkflowRunRecord.source == "outlook",
                        WorkflowRunRecord.source_ref == source_ref,
                    )
                    .first()
                )
                if existing is not None:
                    duplicates_skipped += 1
                    continue

                details = await client.message_details(message_id.strip())
                source_ref = _outlook_source_ref(details)
                existing = (
                    db.query(WorkflowRunRecord)
                    .filter(
                        WorkflowRunRecord.source == "outlook",
                        WorkflowRunRecord.source_ref == source_ref,
                    )
                    .first()
                )
                if existing is not None:
                    duplicates_skipped += 1
                    continue

                subject_value = details.get("subject")
                subject = (
                    subject_value.strip()
                    if isinstance(subject_value, str) and subject_value.strip()
                    else "Outlook disruption notice"
                )
                body = _outlook_body(details)
                received_value = details.get("receivedDateTime")
                received_at = (
                    received_value.strip()
                    if isinstance(received_value, str) and received_value.strip()
                    else polled_at.isoformat()
                )
                body_container = details.get("body")
                content_type = (
                    body_container.get("contentType")
                    if isinstance(body_container, Mapping)
                    else None
                )
                incident_id = _outlook_incident_id(subject, body, source_ref)
                now = utc_now()
                run = WorkflowRunRecord(
                    run_id=f"RUN-{uuid4().hex}",
                    incident_id=incident_id,
                    status=WorkflowStatus.RUNNING.value,
                    severity=Severity.UNKNOWN.value,
                    source="outlook",
                    source_ref=source_ref,
                    duplicate_trigger_count=0,
                    input_payload={
                        "source": "outlook",
                        "source_ref": source_ref,
                        "message_id": details.get("id") or message_id,
                        "internet_message_id": details.get("internetMessageId"),
                        "subject": subject,
                        "sender_email": _outlook_sender(details),
                        "received_at_raw": received_at,
                        "body": body,
                        "body_content_type": content_type,
                        "has_attachments": details.get("hasAttachments") is True,
                        "web_link": details.get("webLink"),
                    },
                    requested_by="outlook-poller",
                    current_operator="Exception Commander Orchestrator",
                    created_at=now,
                    updated_at=now,
                )
                db.add(run)
                db.flush()
                run_ids.append(run.run_id)

        total_items = inbox.get("totalItemCount")
        records_seen = total_items if isinstance(total_items, int) else None
        polling_metadata = {
            "initialized": True,
            "last_poll_at": polled_at.isoformat(),
            "last_messages_seen": len(delta.messages),
            "last_runs_created": len(run_ids),
            "last_runs_started": len(run_ids),
            "baseline_messages": (len(delta.messages) if baseline_established else 0),
            "cursor_reset": cursor_reset,
        }
        metadata[OUTLOOK_DELTA_LINK_KEY] = delta.delta_link
        metadata["polling"] = polling_metadata
        health = _set_integration_health(
            db,
            integration_id="outlook",
            name="Outlook",
            category="channel",
            status="healthy",
            records_seen=records_seen,
        )
        metadata.update(client.auth_metadata())
        health.metadata_json = metadata
        db.commit()
    except (OutlookConfigurationError, OutlookAPIError) as exc:
        db.rollback()
        status = (
            "disconnected"
            if isinstance(exc, OutlookConfigurationError)
            or getattr(exc, "status_code", None) in {401, 403}
            else "degraded"
        )
        health = _set_integration_health(
            db,
            integration_id="outlook",
            name="Outlook",
            category="channel",
            status=status,
            last_error=str(exc),
        )
        metadata.update(outlook_oauth_configuration())
        health.metadata_json = metadata
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    for run_id in run_ids:
        background_tasks.add_task(_consume_supervity_stream, run_id)

    await audit.log(
        action="outlook.poll",
        description=(
            "Established the Outlook Inbox baseline"
            if baseline_established
            else f"Processed {len(delta.messages)} Outlook Inbox changes"
        ),
        actor=user,
        category="workflow",
        resource_type="integration",
        resource_id="outlook",
        request=request,
        metadata={
            "baseline_established": baseline_established,
            "cursor_reset": cursor_reset,
            "messages_seen": len(delta.messages),
            "runs_created": len(run_ids),
            "duplicates_skipped": duplicates_skipped,
            "removed_skipped": removed_skipped,
            "pages_seen": delta.pages_seen,
        },
    )
    return OutlookPollRead(
        baseline_established=baseline_established,
        cursor_reset=cursor_reset,
        messages_seen=len(delta.messages),
        baseline_messages=(len(delta.messages) if baseline_established else 0),
        runs_created=len(run_ids),
        runs_started=len(run_ids),
        duplicates_skipped=duplicates_skipped,
        removed_skipped=removed_skipped,
        pages_seen=delta.pages_seen,
        run_ids=run_ids,
        polled_at=polled_at,
    )


@router.get("/insights", response_model=list[InsightRead])
def list_insights(
    limit: int = Query(default=100, ge=1, le=200), db: Session = Depends(get_db)
):
    return (
        db.query(InsightRecord)
        .order_by(InsightRecord.created_at.desc())
        .limit(limit)
        .all()
    )


@router.post("/insights", response_model=InsightRead, status_code=201)
async def create_insight(
    payload: InsightCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    record = InsightRecord(
        insight_id=f"INS-{uuid4().hex}",
        kind=payload.kind,
        severity=payload.severity,
        title=payload.title,
        summary=payload.summary,
        recommendation=payload.recommendation,
        evidence=[_dump(item) for item in payload.evidence],
        affected_entity_ids=payload.affected_entity_ids,
        action_type=payload.action_type,
        action_payload=payload.action_payload,
        created_at=utc_now(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    await audit.log(
        action="insight.create",
        description=f"Created {record.kind} insight: {record.title}",
        actor=user,
        category="insight",
        resource_type="insight",
        resource_id=record.insight_id,
        request=request,
        metadata={"severity": record.severity, "affected": record.affected_entity_ids},
    )
    return record


@router.post("/insights/generate", response_model=list[InsightRead])
async def generate_insights(
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    try:
        client = SupabaseClient.from_environment()
        insights = await ProcurementInsightService(client).generate()
        notice_count = await client.count("disruption_notices")
        source_record_count = sum(
            (await client.count_tables(ORGANIZER_INPUT_TABLES)).values()
        )
    except SupabaseConfigurationError as exc:
        _set_integration_health(
            db,
            integration_id="supabase",
            name="Supabase",
            category="system_of_record",
            status="disconnected",
            last_error=str(exc),
        )
        db.commit()
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except SupabaseAPIError as exc:
        _set_integration_health(
            db,
            integration_id="supabase",
            name="Supabase",
            category="system_of_record",
            status="degraded",
            last_error=str(exc),
        )
        db.commit()
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    insight_ids = [item.insight_id for item in insights]
    if insight_ids:
        db.query(InsightRecord).filter(
            InsightRecord.insight_id.in_(insight_ids)
        ).delete(synchronize_session=False)
    records = []
    for insight in insights:
        record = InsightRecord(
            insight_id=insight.insight_id,
            kind=insight.kind.value,
            severity=insight.severity.value,
            title=insight.title,
            summary=insight.summary,
            recommendation=insight.recommendation,
            evidence=to_primitive(insight.evidence),
            affected_entity_ids=list(insight.affected_entity_ids),
            action_type=insight.action_type,
            action_payload=insight.action_payload,
            created_at=insight.created_at,
        )
        db.add(record)
        records.append(record)
    _set_integration_health(
        db,
        integration_id="supabase",
        name="Supabase",
        category="system_of_record",
        status="healthy",
        records_seen=source_record_count,
    )
    db.commit()
    for record in records:
        db.refresh(record)
    await audit.log(
        action="insight.generate",
        description=f"Generated {len(records)} evidence-backed procurement insights",
        actor=user,
        category="insight",
        resource_type="insight_batch",
        resource_id=f"batch-{uuid4().hex}",
        request=request,
        metadata={
            "insight_ids": insight_ids,
            "source_notice_count": notice_count,
            "source_record_count": source_record_count,
        },
    )
    return records


@router.get("/runs/{run_id}/reservations", response_model=list[ResourceReservationRead])
def list_reservations(run_id: str, db: Session = Depends(get_db)):
    _require_run(db, run_id)
    return (
        db.query(ResourceReservationRecord)
        .filter(ResourceReservationRecord.run_id == run_id)
        .order_by(ResourceReservationRecord.created_at)
        .all()
    )


@router.post(
    "/runs/{run_id}/reservations",
    response_model=ResourceReservationRead,
    status_code=201,
)
async def reserve_resource(
    run_id: str,
    payload: ResourceReservationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    run = _require_run(db, run_id)
    if run.incident_id != payload.incident_id:
        raise HTTPException(status_code=409, detail="Run and incident IDs do not match")
    existing_key = (
        db.query(ResourceReservationRecord)
        .filter(ResourceReservationRecord.idempotency_key == payload.idempotency_key)
        .first()
    )
    if existing_key is not None:
        return existing_key
    lock_key = f"{payload.resource_type}:{payload.resource_id}"
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": lock_key}
        )
    active = (
        db.query(ResourceReservationRecord)
        .filter(
            ResourceReservationRecord.resource_type == payload.resource_type,
            ResourceReservationRecord.resource_id == payload.resource_id,
            ResourceReservationRecord.status == "active",
        )
        .with_for_update()
        .all()
    )
    reserved = sum((record.quantity for record in active), Decimal("0"))
    if payload.available_quantity is None and active:
        raise HTTPException(status_code=409, detail="Resource is already reserved")
    if (
        payload.available_quantity is not None
        and reserved + payload.quantity > payload.available_quantity
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Insufficient unreserved capacity",
                "available_quantity": str(payload.available_quantity),
                "already_reserved": str(reserved),
                "requested": str(payload.quantity),
            },
        )
    record = ResourceReservationRecord(
        reservation_id=f"RES-{uuid4().hex}",
        run_id=run_id,
        incident_id=payload.incident_id,
        resource_type=payload.resource_type,
        resource_id=payload.resource_id,
        quantity=payload.quantity,
        unit=payload.unit,
        idempotency_key=payload.idempotency_key,
        status="active",
        created_at=utc_now(),
        expires_at=payload.expires_at,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    await audit.log(
        action="resource.reserve",
        description=f"Reserved {payload.resource_type} {payload.resource_id}",
        actor=user,
        category="workflow",
        resource_type="resource_reservation",
        resource_id=record.reservation_id,
        request=request,
        metadata={
            "run_id": run_id,
            "quantity": str(record.quantity),
            "unit": record.unit,
            "idempotency_key": record.idempotency_key,
        },
    )
    return record


@router.post(
    "/reservations/{reservation_id}/release",
    response_model=ResourceReservationRead,
)
async def release_reservation(
    reservation_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    record = (
        db.query(ResourceReservationRecord)
        .filter(ResourceReservationRecord.reservation_id == reservation_id)
        .with_for_update()
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    if record.status == "active":
        record.status = "released"
        record.released_at = utc_now()
        db.commit()
        db.refresh(record)
    await audit.log(
        action="resource.release",
        description=f"Released reservation {record.reservation_id}",
        actor=user,
        category="workflow",
        resource_type="resource_reservation",
        resource_id=record.reservation_id,
        request=request,
        metadata={"run_id": record.run_id},
    )
    return record


@router.get("/runs/{run_id}/actions", response_model=list[ActionRead])
def list_actions(run_id: str, db: Session = Depends(get_db)):
    _require_run(db, run_id)
    return (
        db.query(ActionRecord)
        .filter(ActionRecord.run_id == run_id)
        .order_by(ActionRecord.requested_at)
        .all()
    )


@router.post(
    "/runs/{run_id}/actions",
    response_model=ActionRead,
    status_code=201,
)
async def request_action(
    run_id: str,
    payload: ActionCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    """Write the idempotency ledger before an Executor performs a side effect."""

    run = _require_run(db, run_id)
    if run.incident_id != payload.incident_id:
        raise HTTPException(status_code=409, detail="Run and incident IDs do not match")

    requested_evaluation_ids = set(payload.policy_evaluation_ids)
    evaluations = (
        db.query(PolicyEvaluationRecord)
        .filter(
            PolicyEvaluationRecord.run_id == run_id,
            PolicyEvaluationRecord.evaluation_id.in_(requested_evaluation_ids),
        )
        .all()
    )
    if len(evaluations) != len(requested_evaluation_ids):
        raise HTTPException(
            status_code=409,
            detail="One or more policy evaluations are missing or belong to another run",
        )

    try:
        current_policies = [
            policy for policy in await _load_policy_definitions(db) if policy.enabled
        ]
    except (SupabaseConfigurationError, SupabaseAPIError) as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "message": "Governance policy store is unavailable; action is blocked",
                "reason": str(exc),
            },
        ) from exc
    evaluation_by_policy = {item.policy_id: item for item in evaluations}
    missing_policies = [
        policy.policy_id
        for policy in current_policies
        if policy.policy_id not in evaluation_by_policy
    ]
    if missing_policies:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Every enabled policy must be evaluated before execution",
                "missing_policy_ids": sorted(missing_policies),
            },
        )
    stale_policies = [
        policy.policy_id
        for policy in current_policies
        if evaluation_by_policy[policy.policy_id].policy_version != policy.version
    ]
    if stale_policies:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Policy evaluations are stale; evaluate the action again",
                "stale_policy_ids": sorted(stale_policies),
            },
        )
    blocked = [
        item.policy_id
        for item in evaluations
        if item.decision == PolicyDecision.BLOCK.value
    ]
    if blocked:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "The action is blocked by the supplied policy snapshot",
                "blocked_policy_ids": sorted(blocked),
            },
        )
    reviewed_evaluation_ids = {
        item.evaluation_id
        for item in evaluations
        if item.decision == PolicyDecision.REVIEW.value
    }
    if reviewed_evaluation_ids:
        resolved_items = (
            db.query(WorkbenchItemRecord)
            .filter(
                WorkbenchItemRecord.run_id == run_id,
                WorkbenchItemRecord.status.in_(
                    [
                        WorkbenchStatus.APPROVED.value,
                        WorkbenchStatus.MODIFIED.value,
                    ]
                ),
            )
            .all()
        )
        authorized_evaluation_ids = {
            evaluation_id
            for item in resolved_items
            for evaluation_id in (item.policy_evaluation_ids or [])
        }
        unauthorized = reviewed_evaluation_ids - authorized_evaluation_ids
        if unauthorized:
            raise HTTPException(
                status_code=409,
                detail={
                    "message": "Policy review has not been approved for this action",
                    "pending_policy_evaluation_ids": sorted(unauthorized),
                },
            )
    input_hashes = {item.input_hash for item in evaluations}
    if len(input_hashes) != 1:
        raise HTTPException(
            status_code=409,
            detail="Policy evaluations do not share one input snapshot",
        )
    candidate_action_ids = {item.candidate_action_id for item in evaluations}
    if candidate_action_ids != {payload.candidate_action_id}:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Policy evaluations belong to a different candidate action",
                "candidate_action_id": payload.candidate_action_id,
                "evaluated_candidate_action_ids": sorted(
                    str(item) for item in candidate_action_ids
                ),
            },
        )

    request_hash = _canonical_hash(payload.request_payload)
    idempotency_key = _canonical_hash(
        {
            "run_id": run_id,
            "action_type": payload.action_type,
            "candidate_action_id": payload.candidate_action_id,
            "target": payload.target,
            "request_hash": request_hash,
        }
    )
    existing = (
        db.query(ActionRecord)
        .filter(ActionRecord.idempotency_key == idempotency_key)
        .first()
    )
    if existing is not None:
        return existing

    record = ActionRecord(
        action_id=f"ACT-{uuid4().hex}",
        run_id=run_id,
        incident_id=payload.incident_id,
        candidate_action_id=payload.candidate_action_id,
        action_type=payload.action_type,
        external_system=payload.external_system,
        target=payload.target,
        request_payload=payload.request_payload,
        request_hash=request_hash,
        idempotency_key=idempotency_key,
        policy_evaluation_ids=sorted(requested_evaluation_ids),
        status="requested",
        requested_at=utc_now(),
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return (
            db.query(ActionRecord)
            .filter(ActionRecord.idempotency_key == idempotency_key)
            .one()
        )
    db.refresh(record)
    await audit.log(
        action="external_action.request",
        description=f"Recorded {record.action_type} before external execution",
        actor=user,
        category="workflow",
        resource_type="external_action",
        resource_id=record.action_id,
        request=request,
        metadata={
            "run_id": run_id,
            "external_system": record.external_system,
            "candidate_action_id": record.candidate_action_id,
            "target": record.target,
            "idempotency_key": record.idempotency_key,
            "policy_evaluation_ids": record.policy_evaluation_ids,
        },
    )
    return record


@router.post(
    "/supervity/action-authorization",
    response_model=ActionRead,
    status_code=201,
)
async def authorize_supervity_action(
    payload: SupervityActionAuthorizationRequest,
    request: Request,
    x_command_center_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Authorize one Executor action through the Command Center ledger."""

    _verify_run_token(payload.command_center_run_id, x_command_center_secret)
    action_values = _dump(payload)
    action_values.pop("command_center_run_id", None)
    return await request_action(
        payload.command_center_run_id,
        ActionCreate(**action_values),
        request,
        db,
        {"sub": "supervity", "email": "supervity"},
    )


@router.post("/actions/{action_id}/complete", response_model=ActionRead)
async def complete_action(
    action_id: str,
    payload: ActionComplete,
    request: Request,
    db: Session = Depends(get_db),
    user: dict | None = Depends(get_current_user),
):
    record = (
        db.query(ActionRecord)
        .filter(ActionRecord.action_id == action_id)
        .with_for_update()
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if record.status in {"completed", "failed"}:
        return record
    if payload.status == "completed" and not payload.external_ref:
        raise HTTPException(
            status_code=422,
            detail="Completed actions require an external reference",
        )
    if payload.status == "failed" and not payload.error:
        raise HTTPException(status_code=422, detail="Failed actions require an error")

    record.status = payload.status
    record.external_ref = payload.external_ref
    record.verification = payload.verification
    record.error = payload.error
    record.completed_at = utc_now()
    db.commit()
    db.refresh(record)
    await audit.log(
        action=f"external_action.{record.status}",
        description=f"External action {record.action_id} {record.status}",
        actor=user,
        category="workflow",
        resource_type="external_action",
        resource_id=record.action_id,
        request=request,
        metadata={
            "run_id": record.run_id,
            "external_system": record.external_system,
            "external_ref": record.external_ref,
        },
    )
    return record


@router.post(
    "/supervity/action-completion",
    response_model=ActionRead,
)
async def complete_supervity_action(
    payload: SupervityActionCompletionRequest,
    request: Request,
    x_command_center_secret: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    """Close a previously authorized action with a verified Executor result."""

    _verify_run_token(payload.command_center_run_id, x_command_center_secret)
    action = (
        db.query(ActionRecord)
        .filter(ActionRecord.action_id == payload.action_id)
        .first()
    )
    if action is None:
        raise HTTPException(status_code=404, detail="Action not found")
    if action.run_id != payload.command_center_run_id:
        raise HTTPException(status_code=409, detail="Action belongs to another run")
    completion_values = _dump(payload)
    completion_values.pop("command_center_run_id", None)
    completion_values.pop("action_id", None)
    return await complete_action(
        payload.action_id,
        ActionComplete(**completion_values),
        request,
        db,
        {"sub": "supervity", "email": "supervity"},
    )
