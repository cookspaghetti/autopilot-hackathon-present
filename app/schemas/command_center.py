"""Shared API contracts for the Procurement Exception Command Center."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ..domain import (
    InsightKind,
    IntegrationStatus,
    OperatorRunStatus,
    PolicyDecision,
    PolicyMatchMode,
    PolicyOperator,
    Severity,
    WorkbenchDecision,
    WorkbenchStatus,
    WorkflowStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class EvidenceReferenceSchema(ORMModel):
    system: str
    entity_type: str
    entity_id: str
    observed_at: datetime
    fields: list[str] = Field(default_factory=list)
    observed_values: dict[str, Any] = Field(default_factory=dict)
    uri: str | None = None
    checksum: str | None = None


class MoneySchema(ORMModel):
    amount: Decimal
    currency: str = "MYR"


class OperatorResultSchema(ORMModel):
    incident_id: str
    run_id: str
    operator_name: str
    status: OperatorRunStatus
    confidence: float = Field(ge=0, le=1)
    started_at: datetime
    completed_at: datetime | None = None
    facts: dict[str, Any] = Field(default_factory=dict)
    evidence: list[EvidenceReferenceSchema] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    schema_version: str = Field(default="2.0", min_length=1)
    operator_run_id: str | None = Field(default=None, min_length=1)
    subject_type: str = Field(default="incident", min_length=1)
    subject_id: str | None = Field(default=None, min_length=1)
    operator_version: str | None = Field(default=None, min_length=1)
    attempt: int = Field(default=1, ge=1)
    proposed_actions: list[dict[str, Any]] = Field(default_factory=list)


class OperatorResultRead(OperatorResultSchema):
    result_id: str
    workflow_run_id: str


class SupervityOperatorResultRequest(OperatorResultSchema):
    command_center_run_id: str = Field(min_length=1)


class WorkflowRunCreate(ORMModel):
    incident_id: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_ref: str | None = Field(default=None, min_length=1)
    input_payload: dict[str, Any]
    requested_by: str | None = None


class WorkflowRunRead(ORMModel):
    run_id: str
    incident_id: str
    status: WorkflowStatus
    source: str
    source_ref: str | None = None
    duplicate_trigger_count: int = 0
    input_payload: dict[str, Any]
    output_payload: dict[str, Any] | None = None
    requested_by: str | None = None
    auto_run_id: str | None = None
    current_operator: str | None = None
    plan_run_id: str | None = None
    error: str | None = None
    severity: Severity
    cost_at_risk_myr: Decimal
    cost_avoided_myr: Decimal
    time_to_mitigation_hours: float | None = None
    created_at: datetime
    updated_at: datetime


class WorkflowRunUpdate(ORMModel):
    status: WorkflowStatus
    auto_run_id: str | None = None
    current_operator: str | None = None
    plan_run_id: str | None = None
    output_payload: dict[str, Any] | None = None
    error: str | None = None
    severity: Severity | None = None
    cost_at_risk_myr: Decimal | None = Field(default=None, ge=0)
    cost_avoided_myr: Decimal | None = None
    time_to_mitigation_hours: float | None = Field(default=None, ge=0)


class SupervityCallbackRequest(ORMModel):
    command_center_run_id: str = Field(min_length=1)
    auto_run_id: str | None = None
    status: WorkflowStatus
    current_operator: str | None = None
    plan_run_id: str | None = None
    output_payload: dict[str, Any] | None = None
    error: str | None = None
    severity: Severity | None = None
    cost_at_risk_myr: Decimal | None = Field(default=None, ge=0)
    cost_avoided_myr: Decimal | None = None
    time_to_mitigation_hours: float | None = Field(default=None, ge=0)


class PolicyConditionSchema(ORMModel):
    field_path: str = Field(min_length=1)
    operator: PolicyOperator
    value: Any = None


class PolicyCreate(ORMModel):
    policy_id: str | None = None
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    priority: int = Field(default=100, ge=0)
    enabled: bool = True
    match_mode: PolicyMatchMode = PolicyMatchMode.ALL
    conditions: list[PolicyConditionSchema] = Field(min_length=1)
    decision: PolicyDecision
    reason_template: str = Field(min_length=1)
    approval_role: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    required_facts: list[str] = Field(default_factory=list)
    action_classes: list[str] = Field(default_factory=list)
    owner: str = Field(default="command_center", min_length=1)
    change_reason: str = ""
    effective_from: datetime | None = None
    expires_at: datetime | None = None


class PolicyUpdate(ORMModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = Field(default=None, min_length=1)
    priority: int | None = Field(default=None, ge=0)
    enabled: bool | None = None
    match_mode: PolicyMatchMode | None = None
    conditions: list[PolicyConditionSchema] | None = None
    decision: PolicyDecision | None = None
    reason_template: str | None = Field(default=None, min_length=1)
    approval_role: str | None = None
    parameters: dict[str, Any] | None = None
    required_facts: list[str] | None = None
    action_classes: list[str] | None = None
    owner: str | None = Field(default=None, min_length=1)
    change_reason: str | None = None
    effective_from: datetime | None = None
    expires_at: datetime | None = None


class PolicyRead(PolicyCreate):
    policy_id: str
    version: int
    created_at: datetime
    updated_at: datetime


class PolicyEvaluationRead(ORMModel):
    evaluation_id: str
    policy_id: str
    policy_version: int
    run_id: str
    incident_id: str
    matched: bool
    decision: PolicyDecision
    reason: str
    reason_code: str | None = None
    facts: dict[str, Any]
    input_hash: str
    candidate_action_id: str | None = None
    matched_conditions: list[str] = Field(default_factory=list)
    missing_facts: list[str] = Field(default_factory=list)
    approval_role: str | None = None
    evaluated_at: datetime


class PolicyOperatorRunIds(ORMModel):
    guard: str = Field(min_length=1)
    portfolio: str = Field(min_length=1)
    planner: str = Field(min_length=1)


class PolicyEvaluateRequest(ORMModel):
    run_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    facts: dict[str, Any]
    operator_run_ids: PolicyOperatorRunIds | None = None


class PolicyEvaluateResponse(ORMModel):
    effective_decision: PolicyDecision
    approval_roles: list[str] = Field(default_factory=list)
    evaluations: list[PolicyEvaluationRead]
    workbench_item_id: str | None = None


class WorkbenchItemCreate(ORMModel):
    run_id: str = Field(min_length=1)
    incident_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    severity: Severity
    proposed_action: dict[str, Any]
    alternatives: list[dict[str, Any]] = Field(default_factory=list)
    policy_evaluation_ids: list[str] = Field(default_factory=list)
    evidence: list[EvidenceReferenceSchema] = Field(default_factory=list)
    assigned_to: str | None = None


class WorkbenchDecisionRequest(ORMModel):
    decision: WorkbenchDecision
    reason: str = Field(min_length=1)
    payload: dict[str, Any] | None = None
    expected_version: int = Field(ge=1)


class WorkbenchItemRead(WorkbenchItemCreate):
    item_id: str
    supervity_form_id: str | None = None
    supervity_activity_run_id: str | None = None
    supervity_form_status: str | None = None
    status: WorkbenchStatus
    decision: WorkbenchDecision | None = None
    decision_by: str | None = None
    decision_reason: str | None = None
    decision_payload: dict[str, Any] | None = None
    decision_source: str | None = None
    decision_external_ref: str | None = None
    decided_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    version: int


class SupervityDecisionCallbackRequest(ORMModel):
    command_center_run_id: str = Field(min_length=1)
    workbench_item_id: str | None = Field(default=None, min_length=1)
    supervity_form_id: str | None = Field(default=None, min_length=1)
    decision: WorkbenchDecision
    reason: str = Field(min_length=1)
    payload: dict[str, Any] | None = None
    decision_by: str = Field(min_length=1)
    decision_source: Literal["slack", "supervity_workbench"]
    external_interaction_id: str = Field(min_length=1)
    decided_at: datetime | None = None


class SupervityNotificationCallbackRequest(ORMModel):
    command_center_run_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    notification_type: Literal[
        "incident_report",
        "review_required",
        "decision_recorded",
        "inventory_updated",
        "management_insight",
        "workflow_completed",
        "workflow_failed",
    ]
    status: Literal["requested", "delivered", "updated", "failed"]
    provider: Literal["slack", "supervity_chat"] = "slack"
    route_key: str | None = Field(default=None, min_length=1)
    destination_id: str | None = Field(default=None, min_length=1)
    conversation_id: str | None = Field(default=None, min_length=1)
    message_id: str | None = Field(default=None, min_length=1)
    thread_id: str | None = Field(default=None, min_length=1)
    channel_id: str | None = Field(default=None, min_length=1)
    message_ts: str | None = Field(default=None, min_length=1)
    thread_ts: str | None = Field(default=None, min_length=1)
    workbench_item_id: str | None = Field(default=None, min_length=1)
    error: str | None = Field(default=None, min_length=1)
    attempt: int = Field(default=1, ge=1)
    occurred_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class NotificationRead(ORMModel):
    notification_id: str
    run_id: str
    incident_id: str
    workbench_item_id: str | None = None
    provider: str
    managed_by: str
    notification_type: str
    destination: str | None = None
    external_ref: str | None = None
    thread_ref: str | None = None
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str
    last_error: str | None = None
    attempt: int
    occurred_at: datetime
    delivered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class IntegrationHealthRead(ORMModel):
    integration_id: str
    name: str
    category: str
    status: IntegrationStatus
    checked_at: datetime
    last_success_at: datetime | None = None
    last_error: str | None = None
    records_seen: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IntegrationHealthUpsert(ORMModel):
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    status: IntegrationStatus
    checked_at: datetime
    last_success_at: datetime | None = None
    last_error: str | None = None
    records_seen: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OutlookPollRead(ORMModel):
    baseline_established: bool
    cursor_reset: bool = False
    messages_seen: int = Field(ge=0)
    baseline_messages: int = Field(ge=0)
    runs_created: int = Field(ge=0)
    runs_started: int = Field(ge=0)
    duplicates_skipped: int = Field(ge=0)
    removed_skipped: int = Field(ge=0)
    pages_seen: int = Field(ge=1)
    run_ids: list[str] = Field(default_factory=list)
    polled_at: datetime


class OutlookAuthorizationStartRead(ORMModel):
    authorization_url: str


class SupervityRunSyncRead(ORMModel):
    run_id: str
    auto_run_id: str
    remote_status: str
    local_status: WorkflowStatus
    activities_seen: int
    operator_results_added: int


class SupervityFormSyncRead(ORMModel):
    forms_seen: int
    pending_forms: int
    approved_forms: int
    modified_forms: int
    rejected_forms: int
    expired_forms: int
    other_forms: int
    matched_runs: int
    items_created: int
    items_updated: int
    forms_skipped: int


class SupervityConnectedAccountRead(ORMModel):
    name: str
    integration: str
    status: str
    actions_count: int = 0


class SupervityIntegrationActionRead(ORMModel):
    name: str
    integration: str
    description: str | None = None


class SupervityIntegrationInventoryRead(ORMModel):
    connected_accounts: list[SupervityConnectedAccountRead] = Field(
        default_factory=list
    )
    actions: list[SupervityIntegrationActionRead] = Field(default_factory=list)


class SupervityScheduleRead(ORMModel):
    schedule_id: str
    name: str
    workflow_name: str | None = None
    status: str
    timezone: str | None = None
    expression: str | None = None
    next_run_at: datetime | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class InsightRead(ORMModel):
    insight_id: str
    kind: InsightKind
    severity: Severity
    title: str
    summary: str
    recommendation: str
    evidence: list[EvidenceReferenceSchema]
    affected_entity_ids: list[str] = Field(default_factory=list)
    action_type: str | None = None
    action_payload: dict[str, Any] | None = None
    created_at: datetime


class InsightCreate(ORMModel):
    kind: InsightKind
    severity: Severity
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)
    evidence: list[EvidenceReferenceSchema] = Field(min_length=1)
    affected_entity_ids: list[str] = Field(default_factory=list)
    action_type: str | None = None
    action_payload: dict[str, Any] | None = None


class ResourceReservationCreate(ORMModel):
    incident_id: str = Field(min_length=1)
    resource_type: str = Field(min_length=1)
    resource_id: str = Field(min_length=1)
    quantity: Decimal = Field(gt=0)
    unit: str = Field(min_length=1)
    idempotency_key: str = Field(min_length=1)
    available_quantity: Decimal | None = Field(default=None, gt=0)
    expires_at: datetime | None = None


class ResourceReservationRead(ORMModel):
    reservation_id: str
    run_id: str
    incident_id: str
    resource_type: str
    resource_id: str
    quantity: Decimal
    unit: str
    idempotency_key: str
    status: str
    created_at: datetime
    expires_at: datetime | None = None
    released_at: datetime | None = None


class ActionCreate(ORMModel):
    incident_id: str = Field(min_length=1)
    candidate_action_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    external_system: str = Field(min_length=1)
    target: str = Field(min_length=1)
    request_payload: dict[str, Any]
    policy_evaluation_ids: list[str] = Field(min_length=1)


class SupervityActionAuthorizationRequest(ActionCreate):
    command_center_run_id: str = Field(min_length=1)


class ActionComplete(ORMModel):
    status: str = Field(pattern="^(completed|failed)$")
    external_ref: str | None = Field(default=None, min_length=1)
    verification: dict[str, Any] | None = None
    error: str | None = Field(default=None, min_length=1)


class SupervityActionCompletionRequest(ActionComplete):
    command_center_run_id: str = Field(min_length=1)
    action_id: str = Field(min_length=1)


class ActionRead(ORMModel):
    action_id: str
    run_id: str
    incident_id: str
    candidate_action_id: str
    action_type: str
    external_system: str
    target: str
    request_payload: dict[str, Any]
    request_hash: str
    idempotency_key: str
    policy_evaluation_ids: list[str]
    status: str
    external_ref: str | None = None
    verification: dict[str, Any] | None = None
    error: str | None = None
    requested_at: datetime
    completed_at: datetime | None = None


class DashboardSummary(ORMModel):
    open_disruptions: int
    critical_disruptions: int
    awaiting_decision: int
    completed_runs: int
    cost_at_risk_myr: Decimal
    cost_avoided_myr: Decimal
    average_time_to_mitigation_hours: float | None = None
    healthy_integrations: int
    total_integrations: int


class AIManagerRequest(ORMModel):
    message: str = Field(min_length=1, max_length=4000)
    history: list[dict[str, str]] = Field(default_factory=list)
    context: dict[str, Any] = Field(default_factory=dict)


class AIManagerToolCall(ORMModel):
    id: str
    name: str
    args: dict[str, Any]
    result: Any = None


class AIManagerResponse(ORMModel):
    response: str
    tool_calls: list[AIManagerToolCall] = Field(default_factory=list)
