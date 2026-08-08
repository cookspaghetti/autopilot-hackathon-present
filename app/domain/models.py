"""Dependency-free domain dataclasses.

These types are the canonical contracts between the Command Center, Supervity
Auto, policies, the Workbench, and persistence adapters. They are frozen so a
record cannot be silently mutated after it has entered the audit trail.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Mapping, Sequence


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _required(value: str, name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    return normalized


def _aware(value: datetime, name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _decimal(value: Decimal | int | float | str, name: str) -> Decimal:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a valid decimal") from exc
    if not parsed.is_finite():
        raise ValueError(f"{name} must be finite")
    return parsed


class Severity(str, Enum):
    UNKNOWN = "unknown"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class WorkflowStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    EXECUTING = "executing"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OperatorRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    NO_MATCH = "no_match"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"
    SKIPPED = "skipped"


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    REVIEW = "review"
    BLOCK = "block"


class PolicyOperator(str, Enum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    EXISTS = "exists"


class PolicyMatchMode(str, Enum):
    ALL = "all"
    ANY = "any"


class WorkbenchStatus(str, Enum):
    OPEN = "open"
    APPROVED = "approved"
    MODIFIED = "modified"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class WorkbenchDecision(str, Enum):
    APPROVE = "approve"
    MODIFY = "modify"
    REJECT = "reject"
    ESCALATE = "escalate"


class IntegrationStatus(str, Enum):
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    DISCONNECTED = "disconnected"


class InsightKind(str, Enum):
    PATTERN = "pattern"
    ANOMALY = "anomaly"
    RECOMMENDATION = "recommendation"


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = "MYR"

    def __post_init__(self) -> None:
        object.__setattr__(self, "amount", _decimal(self.amount, "amount"))
        currency = _required(self.currency, "currency").upper()
        if len(currency) != 3 or not currency.isalpha():
            raise ValueError("currency must be a three-letter ISO code")
        object.__setattr__(self, "currency", currency)

    @classmethod
    def zero(cls, currency: str = "MYR") -> Money:
        return cls(amount=Decimal("0"), currency=currency)


@dataclass(frozen=True, slots=True)
class EvidenceReference:
    system: str
    entity_type: str
    entity_id: str
    observed_at: datetime
    fields: tuple[str, ...] = ()
    observed_values: Mapping[str, Any] = field(default_factory=dict)
    uri: str | None = None
    checksum: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "system", _required(self.system, "system"))
        object.__setattr__(
            self, "entity_type", _required(self.entity_type, "entity_type")
        )
        object.__setattr__(self, "entity_id", _required(self.entity_id, "entity_id"))
        object.__setattr__(self, "observed_at", _aware(self.observed_at, "observed_at"))
        object.__setattr__(
            self,
            "fields",
            tuple(_required(name, "evidence field") for name in self.fields),
        )
        object.__setattr__(self, "observed_values", dict(self.observed_values))


@dataclass(frozen=True, slots=True)
class OperatorResultEnvelope:
    incident_id: str
    run_id: str
    operator_name: str
    status: OperatorRunStatus
    confidence: float
    started_at: datetime
    completed_at: datetime | None = None
    facts: Mapping[str, Any] = field(default_factory=dict)
    evidence: tuple[EvidenceReference, ...] = ()
    assumptions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    schema_version: str = "2.0"
    operator_run_id: str | None = None
    subject_type: str = "incident"
    subject_id: str | None = None
    operator_version: str | None = None
    attempt: int = 1
    proposed_actions: tuple[Mapping[str, Any], ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "incident_id", _required(self.incident_id, "incident_id")
        )
        object.__setattr__(self, "run_id", _required(self.run_id, "run_id"))
        object.__setattr__(
            self,
            "schema_version",
            _required(self.schema_version, "schema_version"),
        )
        object.__setattr__(
            self,
            "operator_run_id",
            _required(self.operator_run_id or self.run_id, "operator_run_id"),
        )
        object.__setattr__(
            self, "subject_type", _required(self.subject_type, "subject_type")
        )
        object.__setattr__(
            self,
            "subject_id",
            _required(self.subject_id or self.incident_id, "subject_id"),
        )
        object.__setattr__(
            self, "operator_name", _required(self.operator_name, "operator_name")
        )
        if self.operator_version is not None:
            object.__setattr__(
                self,
                "operator_version",
                _required(self.operator_version, "operator_version"),
            )
        if self.attempt < 1:
            raise ValueError("attempt must be at least 1")
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "started_at", _aware(self.started_at, "started_at"))
        if self.completed_at is not None:
            completed = _aware(self.completed_at, "completed_at")
            if completed < self.started_at:
                raise ValueError("completed_at cannot be earlier than started_at")
            object.__setattr__(self, "completed_at", completed)
        object.__setattr__(self, "facts", dict(self.facts))
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "assumptions", tuple(self.assumptions))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "errors", tuple(self.errors))
        object.__setattr__(
            self,
            "proposed_actions",
            tuple(dict(action) for action in self.proposed_actions),
        )


@dataclass(frozen=True, slots=True)
class RecoveryOption:
    option_id: str
    option_type: str
    summary: str
    incremental_cost: Money
    residual_exposure: Money
    recovery_hours: Decimal
    penalties: Money = field(default_factory=Money.zero)
    supplier_id: str | None = None
    source_location: str | None = None
    destination_location: str | None = None
    requires_approval: bool = True
    constraints: tuple[str, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "option_id", _required(self.option_id, "option_id"))
        object.__setattr__(
            self, "option_type", _required(self.option_type, "option_type")
        )
        object.__setattr__(self, "summary", _required(self.summary, "summary"))
        hours = _decimal(self.recovery_hours, "recovery_hours")
        if hours < 0:
            raise ValueError("recovery_hours cannot be negative")
        object.__setattr__(self, "recovery_hours", hours)
        currencies = {
            self.incremental_cost.currency,
            self.residual_exposure.currency,
            self.penalties.currency,
        }
        if len(currencies) != 1:
            raise ValueError("all recovery option money values must share a currency")
        object.__setattr__(self, "constraints", tuple(self.constraints))
        object.__setattr__(self, "evidence", tuple(self.evidence))

    @property
    def governed_cost(self) -> Money:
        return Money(
            amount=self.incremental_cost.amount + self.penalties.amount,
            currency=self.incremental_cost.currency,
        )


@dataclass(frozen=True, slots=True)
class ResourceReservation:
    reservation_id: str
    run_id: str
    incident_id: str
    resource_type: str
    resource_id: str
    quantity: Decimal
    unit: str
    created_at: datetime
    expires_at: datetime | None = None
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        for name in (
            "reservation_id",
            "run_id",
            "incident_id",
            "resource_type",
            "resource_id",
            "unit",
            "idempotency_key",
        ):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        quantity = _decimal(self.quantity, "quantity")
        if quantity <= 0:
            raise ValueError("quantity must be greater than zero")
        object.__setattr__(self, "quantity", quantity)
        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        if self.expires_at is not None:
            expires = _aware(self.expires_at, "expires_at")
            if expires <= self.created_at:
                raise ValueError("expires_at must be later than created_at")
            object.__setattr__(self, "expires_at", expires)


@dataclass(frozen=True, slots=True)
class WorkflowRun:
    run_id: str
    incident_id: str
    status: WorkflowStatus
    source: str
    input_payload: Mapping[str, Any]
    created_at: datetime
    updated_at: datetime
    requested_by: str | None = None
    auto_run_id: str | None = None
    current_operator: str | None = None
    plan_run_id: str | None = None
    output_payload: Mapping[str, Any] | None = None
    error: str | None = None
    severity: Severity = Severity.UNKNOWN
    cost_at_risk: Money = field(default_factory=Money.zero)
    cost_avoided: Money = field(default_factory=Money.zero)
    time_to_mitigation_hours: float | None = None

    def __post_init__(self) -> None:
        for name in ("run_id", "incident_id", "source"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        created = _aware(self.created_at, "created_at")
        updated = _aware(self.updated_at, "updated_at")
        if updated < created:
            raise ValueError("updated_at cannot be earlier than created_at")
        object.__setattr__(self, "created_at", created)
        object.__setattr__(self, "updated_at", updated)
        object.__setattr__(self, "input_payload", dict(self.input_payload))
        if self.output_payload is not None:
            object.__setattr__(self, "output_payload", dict(self.output_payload))
        if self.cost_at_risk.currency != self.cost_avoided.currency:
            raise ValueError("workflow cost metrics must share a currency")
        if (
            self.time_to_mitigation_hours is not None
            and self.time_to_mitigation_hours < 0
        ):
            raise ValueError("time_to_mitigation_hours cannot be negative")

    def transition(
        self,
        status: WorkflowStatus,
        *,
        updated_at: datetime,
        current_operator: str | None = None,
        output_payload: Mapping[str, Any] | None = None,
        error: str | None = None,
    ) -> WorkflowRun:
        """Return a copy after enforcing the workflow lifecycle."""

        allowed: dict[WorkflowStatus, set[WorkflowStatus]] = {
            WorkflowStatus.QUEUED: {
                WorkflowStatus.RUNNING,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            },
            WorkflowStatus.RUNNING: {
                WorkflowStatus.AWAITING_APPROVAL,
                WorkflowStatus.EXECUTING,
                WorkflowStatus.COMPLETED,
                WorkflowStatus.NEEDS_REVIEW,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELLED,
            },
            WorkflowStatus.AWAITING_APPROVAL: {
                WorkflowStatus.EXECUTING,
                WorkflowStatus.NEEDS_REVIEW,
                WorkflowStatus.CANCELLED,
            },
            WorkflowStatus.EXECUTING: {
                WorkflowStatus.COMPLETED,
                WorkflowStatus.NEEDS_REVIEW,
                WorkflowStatus.FAILED,
            },
            WorkflowStatus.NEEDS_REVIEW: {
                WorkflowStatus.RUNNING,
                WorkflowStatus.AWAITING_APPROVAL,
                WorkflowStatus.CANCELLED,
            },
            WorkflowStatus.COMPLETED: set(),
            WorkflowStatus.FAILED: set(),
            WorkflowStatus.CANCELLED: set(),
        }
        if status is not self.status and status not in allowed[self.status]:
            raise ValueError(
                f"invalid workflow transition: {self.status.value} -> {status.value}"
            )
        timestamp = _aware(updated_at, "updated_at")
        if timestamp < self.updated_at:
            raise ValueError("updated_at cannot move backwards")
        return replace(
            self,
            status=status,
            updated_at=timestamp,
            current_operator=current_operator,
            output_payload=(
                dict(output_payload)
                if output_payload is not None
                else self.output_payload
            ),
            error=error,
        )


@dataclass(frozen=True, slots=True)
class PolicyCondition:
    field_path: str
    operator: PolicyOperator
    value: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "field_path", _required(self.field_path, "field_path"))
        if self.operator in {
            PolicyOperator.IN,
            PolicyOperator.NOT_IN,
        } and not isinstance(self.value, (list, tuple, set, frozenset)):
            raise ValueError(f"{self.operator.value} requires a collection value")


@dataclass(frozen=True, slots=True)
class PolicyDefinition:
    policy_id: str
    name: str
    description: str
    version: int
    priority: int
    enabled: bool
    match_mode: PolicyMatchMode
    conditions: tuple[PolicyCondition, ...]
    decision: PolicyDecision
    reason_template: str
    created_at: datetime
    updated_at: datetime
    approval_role: str | None = None
    parameters: Mapping[str, Any] = field(default_factory=dict)
    required_facts: tuple[str, ...] = ()
    action_classes: tuple[str, ...] = ()
    owner: str = "command_center"
    change_reason: str = ""
    effective_from: datetime | None = None
    expires_at: datetime | None = None

    def __post_init__(self) -> None:
        for name in ("policy_id", "name", "description", "reason_template"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if self.version < 1:
            raise ValueError("version must be at least 1")
        if self.priority < 0:
            raise ValueError("priority cannot be negative")
        if not self.conditions:
            raise ValueError("a policy must contain at least one condition")
        if self.decision is PolicyDecision.REVIEW and not self.approval_role:
            raise ValueError("review policies require an approval_role")
        created = _aware(self.created_at, "created_at")
        updated = _aware(self.updated_at, "updated_at")
        if updated < created:
            raise ValueError("updated_at cannot be earlier than created_at")
        object.__setattr__(self, "conditions", tuple(self.conditions))
        object.__setattr__(self, "parameters", dict(self.parameters))
        object.__setattr__(
            self,
            "required_facts",
            tuple(_required(item, "required_fact") for item in self.required_facts),
        )
        object.__setattr__(
            self,
            "action_classes",
            tuple(_required(item, "action_class") for item in self.action_classes),
        )
        object.__setattr__(self, "owner", _required(self.owner, "owner"))
        effective = _aware(self.effective_from or created, "effective_from")
        object.__setattr__(self, "effective_from", effective)
        if self.expires_at is not None:
            expires = _aware(self.expires_at, "expires_at")
            if expires <= effective:
                raise ValueError("expires_at must be later than effective_from")
            object.__setattr__(self, "expires_at", expires)


@dataclass(frozen=True, slots=True)
class PolicyEvaluation:
    evaluation_id: str
    policy_id: str
    policy_version: int
    run_id: str
    incident_id: str
    decision: PolicyDecision
    reason: str
    facts: Mapping[str, Any]
    input_hash: str
    evaluated_at: datetime
    matched: bool = True
    matched_conditions: tuple[str, ...] = ()
    approval_role: str | None = None
    reason_code: str | None = None
    candidate_action_id: str | None = None
    missing_facts: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "evaluation_id",
            "policy_id",
            "run_id",
            "incident_id",
            "reason",
            "input_hash",
        ):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if self.policy_version < 1:
            raise ValueError("policy_version must be at least 1")
        if self.decision is PolicyDecision.REVIEW and not self.approval_role:
            raise ValueError("review evaluations require an approval_role")
        object.__setattr__(
            self, "evaluated_at", _aware(self.evaluated_at, "evaluated_at")
        )
        object.__setattr__(self, "facts", dict(self.facts))
        object.__setattr__(self, "matched_conditions", tuple(self.matched_conditions))
        object.__setattr__(self, "missing_facts", tuple(self.missing_facts))
        if self.reason_code is not None:
            object.__setattr__(
                self, "reason_code", _required(self.reason_code, "reason_code")
            )
        if self.candidate_action_id is not None:
            object.__setattr__(
                self,
                "candidate_action_id",
                _required(self.candidate_action_id, "candidate_action_id"),
            )


@dataclass(frozen=True, slots=True)
class WorkbenchItem:
    item_id: str
    run_id: str
    incident_id: str
    title: str
    summary: str
    severity: Severity
    proposed_action: Mapping[str, Any]
    status: WorkbenchStatus
    created_at: datetime
    updated_at: datetime
    alternatives: tuple[Mapping[str, Any], ...] = ()
    policy_evaluation_ids: tuple[str, ...] = ()
    evidence: tuple[EvidenceReference, ...] = ()
    assigned_to: str | None = None
    decision: WorkbenchDecision | None = None
    decision_by: str | None = None
    decision_reason: str | None = None
    decision_payload: Mapping[str, Any] | None = None
    decided_at: datetime | None = None
    version: int = 1

    def __post_init__(self) -> None:
        for name in ("item_id", "run_id", "incident_id", "title", "summary"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if self.version < 1:
            raise ValueError("version must be at least 1")
        created = _aware(self.created_at, "created_at")
        updated = _aware(self.updated_at, "updated_at")
        if updated < created:
            raise ValueError("updated_at cannot be earlier than created_at")
        object.__setattr__(self, "proposed_action", dict(self.proposed_action))
        object.__setattr__(
            self, "alternatives", tuple(dict(option) for option in self.alternatives)
        )
        object.__setattr__(
            self, "policy_evaluation_ids", tuple(self.policy_evaluation_ids)
        )
        object.__setattr__(self, "evidence", tuple(self.evidence))
        if self.decided_at is not None:
            object.__setattr__(
                self, "decided_at", _aware(self.decided_at, "decided_at")
            )
        if self.status is WorkbenchStatus.OPEN:
            if any((self.decision, self.decision_by, self.decided_at)):
                raise ValueError("open Workbench items cannot contain a decision")
        elif self.status is not WorkbenchStatus.EXPIRED:
            if not all((self.decision, self.decision_by, self.decided_at)):
                raise ValueError("resolved Workbench items require decision metadata")

    def resolve(
        self,
        *,
        decision: WorkbenchDecision,
        decided_by: str,
        reason: str,
        decided_at: datetime,
        payload: Mapping[str, Any] | None = None,
    ) -> WorkbenchItem:
        """Return a resolved copy while enforcing one-way Workbench transitions."""

        if self.status is not WorkbenchStatus.OPEN:
            raise ValueError("only open Workbench items can be resolved")
        status_by_decision = {
            WorkbenchDecision.APPROVE: WorkbenchStatus.APPROVED,
            WorkbenchDecision.MODIFY: WorkbenchStatus.MODIFIED,
            WorkbenchDecision.REJECT: WorkbenchStatus.REJECTED,
            WorkbenchDecision.ESCALATE: WorkbenchStatus.ESCALATED,
        }
        timestamp = _aware(decided_at, "decided_at")
        if timestamp < self.created_at:
            raise ValueError("decided_at cannot be earlier than created_at")
        return replace(
            self,
            status=status_by_decision[decision],
            decision=decision,
            decision_by=_required(decided_by, "decided_by"),
            decision_reason=_required(reason, "reason"),
            decision_payload=dict(payload) if payload is not None else None,
            decided_at=timestamp,
            updated_at=timestamp,
            version=self.version + 1,
        )


@dataclass(frozen=True, slots=True)
class IntegrationHealth:
    integration_id: str
    name: str
    category: str
    status: IntegrationStatus
    checked_at: datetime
    last_success_at: datetime | None = None
    last_error: str | None = None
    records_seen: int | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("integration_id", "name", "category"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        object.__setattr__(self, "checked_at", _aware(self.checked_at, "checked_at"))
        if self.last_success_at is not None:
            object.__setattr__(
                self,
                "last_success_at",
                _aware(self.last_success_at, "last_success_at"),
            )
        if self.records_seen is not None and self.records_seen < 0:
            raise ValueError("records_seen cannot be negative")
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class Insight:
    insight_id: str
    kind: InsightKind
    severity: Severity
    title: str
    summary: str
    recommendation: str
    evidence: tuple[EvidenceReference, ...]
    created_at: datetime
    affected_entity_ids: tuple[str, ...] = ()
    action_type: str | None = None
    action_payload: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name in ("insight_id", "title", "summary", "recommendation"):
            object.__setattr__(self, name, _required(getattr(self, name), name))
        if not self.evidence:
            raise ValueError("an insight must contain at least one evidence reference")
        object.__setattr__(self, "evidence", tuple(self.evidence))
        object.__setattr__(self, "affected_entity_ids", tuple(self.affected_entity_ids))
        object.__setattr__(self, "created_at", _aware(self.created_at, "created_at"))
        if self.action_payload is not None:
            object.__setattr__(self, "action_payload", dict(self.action_payload))


def to_primitive(value: Any) -> Any:
    """Convert domain values into JSON-compatible primitives."""

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return to_primitive(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): to_primitive(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_primitive(item) for item in value]
    return value
