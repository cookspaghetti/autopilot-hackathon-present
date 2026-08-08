"""Add Supervity-managed notification and decision correlation.

Revision ID: g7h8i9j0k1l2
Revises: f6g7h8i9j0k1
Create Date: 2026-08-08
"""

import sqlalchemy as sa

from alembic import op

revision = "g7h8i9j0k1l2"
down_revision = "f6g7h8i9j0k1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("command_workbench_items") as batch:
        batch.add_column(sa.Column("decision_source", sa.String(40), nullable=True))
        batch.add_column(
            sa.Column("decision_external_ref", sa.String(255), nullable=True)
        )
        batch.create_index(
            "ix_command_workbench_items_decision_source", ["decision_source"]
        )
        batch.create_index(
            "ix_command_workbench_items_decision_external_ref",
            ["decision_external_ref"],
        )
        batch.create_unique_constraint(
            "uq_command_workbench_items_decision_external_ref",
            ["decision_external_ref"],
        )

    op.create_table(
        "command_notifications",
        sa.Column("notification_id", sa.String(80), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(80),
            sa.ForeignKey("command_workflow_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("incident_id", sa.String(100), nullable=False),
        sa.Column(
            "workbench_item_id",
            sa.String(80),
            sa.ForeignKey("command_workbench_items.item_id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(40), nullable=False, server_default="slack"),
        sa.Column(
            "managed_by", sa.String(40), nullable=False, server_default="supervity"
        ),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("destination", sa.String(255), nullable=True),
        sa.Column("external_ref", sa.String(255), nullable=True),
        sa.Column("thread_ref", sa.String(255), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="requested"),
        sa.Column("payload", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    for column in (
        "run_id",
        "incident_id",
        "workbench_item_id",
        "provider",
        "managed_by",
        "notification_type",
        "external_ref",
        "status",
        "occurred_at",
        "created_at",
    ):
        op.create_index(
            f"ix_command_notifications_{column}",
            "command_notifications",
            [column],
        )
    op.create_index(
        "ix_command_notifications_idempotency_key",
        "command_notifications",
        ["idempotency_key"],
        unique=True,
    )
    op.execute(
        sa.text(
            "UPDATE command_integration_health "
            "SET integration_id = 'slack-via-supervity', "
            "name = 'Slack via Supervity', category = 'notification' "
            "WHERE integration_id = 'slack' "
            "AND NOT EXISTS ("
            "SELECT 1 FROM command_integration_health existing "
            "WHERE existing.integration_id = 'slack-via-supervity'"
            ")"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE command_integration_health "
            "SET integration_id = 'slack', name = 'Slack', category = 'channel' "
            "WHERE integration_id = 'slack-via-supervity' "
            "AND NOT EXISTS ("
            "SELECT 1 FROM command_integration_health existing "
            "WHERE existing.integration_id = 'slack'"
            ")"
        )
    )
    op.drop_table("command_notifications")

    with op.batch_alter_table("command_workbench_items") as batch:
        batch.drop_constraint(
            "uq_command_workbench_items_decision_external_ref", type_="unique"
        )
        batch.drop_index("ix_command_workbench_items_decision_external_ref")
        batch.drop_index("ix_command_workbench_items_decision_source")
        batch.drop_column("decision_external_ref")
        batch.drop_column("decision_source")
