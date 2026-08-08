"""Control-plane persistence models for Procurement Exception Commander."""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)

from ..core.database import Base


class WorkflowRunRecord(Base):
    __tablename__ = "command_workflow_runs"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "source_ref",
            name="uq_command_workflow_runs_source_identity",
        ),
    )

    run_id = Column(String(80), primary_key=True)
    incident_id = Column(String(100), nullable=False, index=True)
    status = Column(String(40), nullable=False, index=True)
    severity = Column(String(20), nullable=False, default="unknown", index=True)
    source = Column(String(80), nullable=False, index=True)
    source_ref = Column(String(255), nullable=True, index=True)
    duplicate_trigger_count = Column(Integer, nullable=False, default=0)
    input_payload = Column(JSON, nullable=False)
    output_payload = Column(JSON, nullable=True)
    requested_by = Column(String(255), nullable=True)
    auto_run_id = Column(String(255), nullable=True, unique=True, index=True)
    current_operator = Column(String(255), nullable=True)
    plan_run_id = Column(String(255), nullable=True)
    error = Column(Text, nullable=True)
    cost_at_risk_myr = Column(Numeric(18, 2), nullable=False, default=0)
    cost_avoided_myr = Column(Numeric(18, 2), nullable=False, default=0)
    time_to_mitigation_hours = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OperatorResultRecord(Base):
    __tablename__ = "command_operator_results"
    __table_args__ = (
        UniqueConstraint(
            "workflow_run_id",
            "operator_run_id",
            name="uq_command_operator_result_run",
        ),
        UniqueConstraint(
            "workflow_run_id",
            "operator_name",
            "attempt",
            name="uq_command_operator_result_attempt",
        ),
    )

    result_id = Column(String(80), primary_key=True)
    workflow_run_id = Column(
        String(80),
        ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    operator_run_id = Column(String(255), nullable=False)
    schema_version = Column(String(20), nullable=False, default="2.0")
    incident_id = Column(String(100), nullable=False, index=True)
    subject_type = Column(String(40), nullable=False, default="incident")
    subject_id = Column(String(100), nullable=False)
    operator_name = Column(String(255), nullable=False, index=True)
    operator_version = Column(String(100), nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    status = Column(String(40), nullable=False, index=True)
    confidence = Column(Float, nullable=False)
    facts = Column(JSON, nullable=False, default=dict)
    evidence = Column(JSON, nullable=False, default=list)
    assumptions = Column(JSON, nullable=False, default=list)
    warnings = Column(JSON, nullable=False, default=list)
    errors = Column(JSON, nullable=False, default=list)
    proposed_actions = Column(JSON, nullable=False, default=list)
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    @property
    def run_id(self) -> str:
        """Expose the public contract name used by OperatorResultRead."""

        return self.operator_run_id


class PolicyDefinitionRecord(Base):
    __tablename__ = "command_policy_definitions"

    policy_id = Column(String(100), primary_key=True)
    version = Column(Integer, primary_key=True)
    is_current = Column(Boolean, nullable=False, default=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(Integer, nullable=False, default=100, index=True)
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    match_mode = Column(String(10), nullable=False)
    conditions = Column(JSON, nullable=False)
    decision = Column(String(20), nullable=False, index=True)
    reason_template = Column(Text, nullable=False)
    approval_role = Column(String(100), nullable=True)
    parameters = Column(JSON, nullable=False, default=dict)
    required_facts = Column(JSON, nullable=False, default=list)
    action_classes = Column(JSON, nullable=False, default=list)
    owner = Column(String(255), nullable=False, default="command_center")
    change_reason = Column(Text, nullable=False, default="")
    effective_from = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class PolicyEvaluationRecord(Base):
    __tablename__ = "command_policy_evaluations"

    evaluation_id = Column(String(80), primary_key=True)
    policy_id = Column(String(100), nullable=False, index=True)
    policy_version = Column(Integer, nullable=False)
    run_id = Column(
        String(80),
        ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    incident_id = Column(String(100), nullable=False, index=True)
    matched = Column(Boolean, nullable=False)
    decision = Column(String(20), nullable=False, index=True)
    reason = Column(Text, nullable=False)
    reason_code = Column(String(100), nullable=True, index=True)
    facts = Column(JSON, nullable=False)
    input_hash = Column(String(80), nullable=False, index=True)
    candidate_action_id = Column(String(100), nullable=True, index=True)
    matched_conditions = Column(JSON, nullable=False, default=list)
    missing_facts = Column(JSON, nullable=False, default=list)
    approval_role = Column(String(100), nullable=True)
    evaluated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class WorkbenchItemRecord(Base):
    __tablename__ = "command_workbench_items"

    item_id = Column(String(80), primary_key=True)
    run_id = Column(
        String(80),
        ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    incident_id = Column(String(100), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    proposed_action = Column(JSON, nullable=False)
    alternatives = Column(JSON, nullable=False, default=list)
    policy_evaluation_ids = Column(JSON, nullable=False, default=list)
    evidence = Column(JSON, nullable=False, default=list)
    assigned_to = Column(String(255), nullable=True, index=True)
    supervity_form_id = Column(String(255), nullable=True, unique=True, index=True)
    supervity_activity_run_id = Column(String(255), nullable=True, index=True)
    supervity_form_status = Column(String(30), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="open", index=True)
    decision = Column(String(20), nullable=True)
    decision_by = Column(String(255), nullable=True)
    decision_reason = Column(Text, nullable=True)
    decision_payload = Column(JSON, nullable=True)
    decision_source = Column(String(40), nullable=True, index=True)
    decision_external_ref = Column(String(255), nullable=True, unique=True, index=True)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class NotificationRecord(Base):
    """Durable receipt for notifications managed and delivered by Supervity."""

    __tablename__ = "command_notifications"

    notification_id = Column(String(80), primary_key=True)
    run_id = Column(
        String(80),
        ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    incident_id = Column(String(100), nullable=False, index=True)
    workbench_item_id = Column(
        String(80),
        ForeignKey("command_workbench_items.item_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider = Column(String(40), nullable=False, default="slack", index=True)
    managed_by = Column(String(40), nullable=False, default="supervity", index=True)
    notification_type = Column(String(50), nullable=False, index=True)
    destination = Column(String(255), nullable=True)
    external_ref = Column(String(255), nullable=True, index=True)
    thread_ref = Column(String(255), nullable=True)
    status = Column(String(30), nullable=False, default="requested", index=True)
    payload = Column(JSON, nullable=False, default=dict)
    idempotency_key = Column(String(255), nullable=False, unique=True, index=True)
    last_error = Column(Text, nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    occurred_at = Column(DateTime(timezone=True), nullable=False, index=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class IntegrationHealthRecord(Base):
    __tablename__ = "command_integration_health"

    integration_id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    status = Column(String(30), nullable=False, index=True)
    checked_at = Column(DateTime(timezone=True), nullable=False)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    records_seen = Column(Integer, nullable=True)
    metadata_json = Column("metadata", JSON, nullable=False, default=dict)


class IntegrationCredentialRecord(Base):
    """Encrypted server-side credentials for a managed integration."""

    __tablename__ = "command_integration_credentials"

    integration_id = Column(String(100), primary_key=True)
    encrypted_payload = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SlackInsightEventRecord(Base):
    """Idempotency and delivery ledger for inbound Slack insight mentions."""

    __tablename__ = "command_slack_insight_events"

    event_id = Column(String(120), primary_key=True)
    channel_id = Column(String(80), nullable=False, index=True)
    message_ts = Column(String(80), nullable=False)
    thread_ts = Column(String(80), nullable=False)
    user_id = Column(String(80), nullable=False, index=True)
    message_text = Column(Text, nullable=False)
    event_type = Column(String(30), nullable=False, default="app_mention")
    conversation_id = Column(String(64), nullable=True, index=True)
    intent = Column(String(50), nullable=True, index=True)
    interaction_mode = Column(String(50), nullable=True)
    status = Column(String(30), nullable=False, default="received", index=True)
    auto_run_id = Column(String(100), nullable=True, index=True)
    last_error = Column(Text, nullable=True)
    received_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class SlackInsightThreadSession(Base):
    """Durable conversational context for one authorized Slack thread."""

    __tablename__ = "command_slack_insight_threads"
    __table_args__ = (
        UniqueConstraint(
            "workspace_key",
            "channel_id",
            "thread_ts",
            name="uq_command_slack_insight_thread_route",
        ),
    )

    conversation_id = Column(String(64), primary_key=True)
    workspace_key = Column(String(80), nullable=False, index=True)
    channel_id = Column(String(80), nullable=False, index=True)
    thread_ts = Column(String(80), nullable=False)
    root_user_id = Column(String(80), nullable=False, index=True)
    current_intent = Column(String(50), nullable=True, index=True)
    interaction_mode = Column(String(50), nullable=True)
    turn_count = Column(Integer, nullable=False, default=0)
    recent_messages = Column(JSON, nullable=False, default=list)
    last_event_id = Column(String(120), nullable=True)
    last_auto_run_id = Column(String(100), nullable=True, index=True)
    status = Column(String(30), nullable=False, default="active", index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class InsightRecord(Base):
    __tablename__ = "command_insights"

    insight_id = Column(String(80), primary_key=True)
    kind = Column(String(30), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    summary = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    evidence = Column(JSON, nullable=False)
    affected_entity_ids = Column(JSON, nullable=False, default=list)
    action_type = Column(String(100), nullable=True)
    action_payload = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class ResourceReservationRecord(Base):
    __tablename__ = "command_resource_reservations"

    reservation_id = Column(String(80), primary_key=True)
    run_id = Column(
        String(80),
        ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    incident_id = Column(String(100), nullable=False, index=True)
    resource_type = Column(String(80), nullable=False, index=True)
    resource_id = Column(String(255), nullable=False, index=True)
    quantity = Column(Numeric(18, 4), nullable=False)
    unit = Column(String(50), nullable=False)
    idempotency_key = Column(String(255), nullable=False, unique=True, index=True)
    status = Column(String(30), nullable=False, default="active", index=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)


class ActionRecord(Base):
    """Write-ahead, idempotent ledger for every external side effect."""

    __tablename__ = "command_actions"

    action_id = Column(String(80), primary_key=True)
    run_id = Column(
        String(80),
        ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    incident_id = Column(String(100), nullable=False, index=True)
    candidate_action_id = Column(String(100), nullable=False, index=True)
    action_type = Column(String(100), nullable=False, index=True)
    external_system = Column(String(100), nullable=False, index=True)
    target = Column(String(255), nullable=False)
    request_payload = Column(JSON, nullable=False)
    request_hash = Column(String(80), nullable=False)
    idempotency_key = Column(String(80), nullable=False, unique=True, index=True)
    policy_evaluation_ids = Column(JSON, nullable=False, default=list)
    status = Column(String(30), nullable=False, default="requested", index=True)
    external_ref = Column(String(255), nullable=True)
    verification = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    requested_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    completed_at = Column(DateTime(timezone=True), nullable=True)
