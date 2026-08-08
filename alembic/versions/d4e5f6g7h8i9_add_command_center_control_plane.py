"""Add Procurement Exception Commander control-plane tables.

Revision ID: d4e5f6g7h8i9
Revises: c3d4e5f6g7h8
Create Date: 2026-08-01
"""

import sqlalchemy as sa

from alembic import op

revision = "d4e5f6g7h8i9"
down_revision = "c3d4e5f6g7h8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "command_workflow_runs",
        sa.Column("run_id", sa.String(80), primary_key=True),
        sa.Column("incident_id", sa.String(100), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("source", sa.String(80), nullable=False),
        sa.Column("input_payload", sa.JSON(), nullable=False),
        sa.Column("output_payload", sa.JSON(), nullable=True),
        sa.Column("requested_by", sa.String(255), nullable=True),
        sa.Column("auto_run_id", sa.String(255), nullable=True),
        sa.Column("current_operator", sa.String(255), nullable=True),
        sa.Column("plan_run_id", sa.String(255), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "cost_at_risk_myr", sa.Numeric(18, 2), nullable=False, server_default="0"
        ),
        sa.Column(
            "cost_avoided_myr", sa.Numeric(18, 2), nullable=False, server_default="0"
        ),
        sa.Column("time_to_mitigation_hours", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("auto_run_id", name="uq_command_workflow_runs_auto_run_id"),
    )
    for column in (
        "incident_id",
        "status",
        "severity",
        "source",
        "auto_run_id",
        "created_at",
    ):
        op.create_index(
            f"ix_command_workflow_runs_{column}", "command_workflow_runs", [column]
        )

    op.create_table(
        "command_operator_results",
        sa.Column("result_id", sa.String(80), primary_key=True),
        sa.Column(
            "workflow_run_id",
            sa.String(80),
            sa.ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("operator_run_id", sa.String(255), nullable=False),
        sa.Column("incident_id", sa.String(100), nullable=False),
        sa.Column("operator_name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("warnings", sa.JSON(), nullable=False),
        sa.Column("errors", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "workflow_run_id", "operator_run_id", name="uq_command_operator_result_run"
        ),
    )
    for column in ("workflow_run_id", "incident_id", "operator_name", "status"):
        op.create_index(
            f"ix_command_operator_results_{column}",
            "command_operator_results",
            [column],
        )

    op.create_table(
        "command_policy_definitions",
        sa.Column("policy_id", sa.String(100), primary_key=True),
        sa.Column("version", sa.Integer(), primary_key=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("match_mode", sa.String(10), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reason_template", sa.Text(), nullable=False),
        sa.Column("approval_role", sa.String(100), nullable=True),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    for column in ("is_current", "priority", "enabled", "decision"):
        op.create_index(
            f"ix_command_policy_definitions_{column}",
            "command_policy_definitions",
            [column],
        )

    op.create_table(
        "command_policy_evaluations",
        sa.Column("evaluation_id", sa.String(80), primary_key=True),
        sa.Column("policy_id", sa.String(100), nullable=False),
        sa.Column("policy_version", sa.Integer(), nullable=False),
        sa.Column(
            "run_id",
            sa.String(80),
            sa.ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("incident_id", sa.String(100), nullable=False),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("facts", sa.JSON(), nullable=False),
        sa.Column("matched_conditions", sa.JSON(), nullable=False),
        sa.Column("approval_role", sa.String(100), nullable=True),
        sa.Column(
            "evaluated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    for column in ("policy_id", "run_id", "incident_id", "decision", "evaluated_at"):
        op.create_index(
            f"ix_command_policy_evaluations_{column}",
            "command_policy_evaluations",
            [column],
        )

    op.create_table(
        "command_workbench_items",
        sa.Column("item_id", sa.String(80), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(80),
            sa.ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("incident_id", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("proposed_action", sa.JSON(), nullable=False),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("policy_evaluation_ids", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("assigned_to", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("decision", sa.String(20), nullable=True),
        sa.Column("decision_by", sa.String(255), nullable=True),
        sa.Column("decision_reason", sa.Text(), nullable=True),
        sa.Column("decision_payload", sa.JSON(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    for column in (
        "run_id",
        "incident_id",
        "severity",
        "assigned_to",
        "status",
        "created_at",
    ):
        op.create_index(
            f"ix_command_workbench_items_{column}", "command_workbench_items", [column]
        )

    op.create_table(
        "command_integration_health",
        sa.Column("integration_id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("records_seen", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_command_integration_health_category",
        "command_integration_health",
        ["category"],
    )
    op.create_index(
        "ix_command_integration_health_status", "command_integration_health", ["status"]
    )

    op.create_table(
        "command_insights",
        sa.Column("insight_id", sa.String(80), primary_key=True),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("affected_entity_ids", sa.JSON(), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=True),
        sa.Column("action_payload", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    for column in ("kind", "severity", "created_at"):
        op.create_index(f"ix_command_insights_{column}", "command_insights", [column])

    op.create_table(
        "command_resource_reservations",
        sa.Column("reservation_id", sa.String(80), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(80),
            sa.ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("incident_id", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False, unique=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in (
        "run_id",
        "incident_id",
        "resource_type",
        "resource_id",
        "idempotency_key",
        "status",
    ):
        op.create_index(
            f"ix_command_resource_reservations_{column}",
            "command_resource_reservations",
            [column],
        )


def downgrade() -> None:
    op.drop_table("command_resource_reservations")
    op.drop_table("command_insights")
    op.drop_table("command_integration_health")
    op.drop_table("command_workbench_items")
    op.drop_table("command_policy_evaluations")
    op.drop_table("command_policy_definitions")
    op.drop_table("command_operator_results")
    op.drop_table("command_workflow_runs")
