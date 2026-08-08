"""Add inbound Slack insight event ledger.

Revision ID: i9j0k1l2m3n4
Revises: h8i9j0k1l2m3
Create Date: 2026-08-08
"""

import sqlalchemy as sa

from alembic import op

revision = "i9j0k1l2m3n4"
down_revision = "h8i9j0k1l2m3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "command_slack_insight_events",
        sa.Column("event_id", sa.String(120), primary_key=True),
        sa.Column("channel_id", sa.String(80), nullable=False),
        sa.Column("message_ts", sa.String(80), nullable=False),
        sa.Column("thread_ts", sa.String(80), nullable=False),
        sa.Column("user_id", sa.String(80), nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="received",
        ),
        sa.Column("auto_run_id", sa.String(100), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "received_at",
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
    op.create_index(
        "ix_command_slack_insight_events_channel_id",
        "command_slack_insight_events",
        ["channel_id"],
    )
    op.create_index(
        "ix_command_slack_insight_events_user_id",
        "command_slack_insight_events",
        ["user_id"],
    )
    op.create_index(
        "ix_command_slack_insight_events_status",
        "command_slack_insight_events",
        ["status"],
    )
    op.create_index(
        "ix_command_slack_insight_events_auto_run_id",
        "command_slack_insight_events",
        ["auto_run_id"],
    )
    op.create_index(
        "ix_command_slack_insight_events_received_at",
        "command_slack_insight_events",
        ["received_at"],
    )


def downgrade() -> None:
    op.drop_table("command_slack_insight_events")
