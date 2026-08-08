"""Harden Command Center execution and evidence contracts.

Revision ID: e5f6g7h8i9j0
Revises: d4e5f6g7h8i9
Create Date: 2026-08-03
"""

import sqlalchemy as sa

from alembic import op

revision = "e5f6g7h8i9j0"
down_revision = "d4e5f6g7h8i9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("command_workflow_runs") as batch:
        batch.add_column(sa.Column("source_ref", sa.String(255), nullable=True))
        batch.add_column(
            sa.Column(
                "duplicate_trigger_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.create_unique_constraint(
            "uq_command_workflow_runs_source_identity", ["source", "source_ref"]
        )
        batch.create_index("ix_command_workflow_runs_source_ref", ["source_ref"])

    with op.batch_alter_table("command_operator_results") as batch:
        batch.add_column(
            sa.Column(
                "schema_version", sa.String(20), nullable=False, server_default="1.0"
            )
        )
        batch.add_column(
            sa.Column(
                "subject_type", sa.String(40), nullable=False, server_default="incident"
            )
        )
        batch.add_column(sa.Column("subject_id", sa.String(100), nullable=True))
        batch.add_column(sa.Column("operator_version", sa.String(100), nullable=True))
        batch.add_column(
            sa.Column("attempt", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(
            sa.Column("proposed_actions", sa.JSON(), nullable=False, server_default="[]")
        )

    op.execute(
        sa.text(
            "UPDATE command_operator_results "
            "SET subject_id = incident_id WHERE subject_id IS NULL"
        )
    )
    with op.batch_alter_table("command_operator_results") as batch:
        batch.alter_column("subject_id", existing_type=sa.String(100), nullable=False)
        batch.create_unique_constraint(
            "uq_command_operator_result_attempt",
            ["workflow_run_id", "operator_name", "attempt"],
        )

    with op.batch_alter_table("command_policy_evaluations") as batch:
        batch.add_column(sa.Column("reason_code", sa.String(100), nullable=True))
        batch.add_column(
            sa.Column(
                "input_hash",
                sa.String(80),
                nullable=False,
                server_default="sha256:legacy",
            )
        )
        batch.add_column(sa.Column("candidate_action_id", sa.String(100), nullable=True))
        batch.create_index("ix_command_policy_evaluations_reason_code", ["reason_code"])
        batch.create_index("ix_command_policy_evaluations_input_hash", ["input_hash"])
        batch.create_index(
            "ix_command_policy_evaluations_candidate_action_id",
            ["candidate_action_id"],
        )

    op.create_table(
        "command_actions",
        sa.Column("action_id", sa.String(80), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(80),
            sa.ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("incident_id", sa.String(100), nullable=False),
        sa.Column("candidate_action_id", sa.String(100), nullable=False),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("external_system", sa.String(100), nullable=False),
        sa.Column("target", sa.String(255), nullable=False),
        sa.Column("request_payload", sa.JSON(), nullable=False),
        sa.Column("request_hash", sa.String(80), nullable=False),
        sa.Column("idempotency_key", sa.String(80), nullable=False),
        sa.Column("policy_evaluation_ids", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="requested"),
        sa.Column("external_ref", sa.String(255), nullable=True),
        sa.Column("verification", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_command_actions_idempotency_key",
        "command_actions",
        ["idempotency_key"],
        unique=True,
    )
    for column in (
        "run_id",
        "incident_id",
        "candidate_action_id",
        "action_type",
        "external_system",
        "status",
        "requested_at",
    ):
        op.create_index(f"ix_command_actions_{column}", "command_actions", [column])


def downgrade() -> None:
    op.drop_table("command_actions")

    with op.batch_alter_table("command_policy_evaluations") as batch:
        batch.drop_index("ix_command_policy_evaluations_candidate_action_id")
        batch.drop_index("ix_command_policy_evaluations_input_hash")
        batch.drop_index("ix_command_policy_evaluations_reason_code")
        batch.drop_column("candidate_action_id")
        batch.drop_column("input_hash")
        batch.drop_column("reason_code")

    with op.batch_alter_table("command_operator_results") as batch:
        batch.drop_constraint("uq_command_operator_result_attempt", type_="unique")
        batch.drop_column("proposed_actions")
        batch.drop_column("attempt")
        batch.drop_column("operator_version")
        batch.drop_column("subject_id")
        batch.drop_column("subject_type")
        batch.drop_column("schema_version")

    with op.batch_alter_table("command_workflow_runs") as batch:
        batch.drop_index("ix_command_workflow_runs_source_ref")
        batch.drop_constraint(
            "uq_command_workflow_runs_source_identity", type_="unique"
        )
        batch.drop_column("duplicate_trigger_count")
        batch.drop_column("source_ref")
