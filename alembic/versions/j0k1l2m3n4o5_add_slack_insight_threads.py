"""Add persisted Slack insight thread sessions.

Revision ID: j0k1l2m3n4o5
Revises: i9j0k1l2m3n4
Create Date: 2026-08-09
"""

import sqlalchemy as sa

from alembic import op

revision = "j0k1l2m3n4o5"
down_revision = "i9j0k1l2m3n4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "command_slack_insight_events",
        sa.Column(
            "event_type",
            sa.String(30),
            nullable=False,
            server_default="app_mention",
        ),
    )
    op.add_column(
        "command_slack_insight_events",
        sa.Column("conversation_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "command_slack_insight_events",
        sa.Column("intent", sa.String(50), nullable=True),
    )
    op.add_column(
        "command_slack_insight_events",
        sa.Column("interaction_mode", sa.String(50), nullable=True),
    )
    op.create_index(
        "ix_command_slack_insight_events_conversation_id",
        "command_slack_insight_events",
        ["conversation_id"],
    )
    op.create_index(
        "ix_command_slack_insight_events_intent",
        "command_slack_insight_events",
        ["intent"],
    )
    op.create_table(
        "command_slack_insight_threads",
        sa.Column("conversation_id", sa.String(64), primary_key=True),
        sa.Column("workspace_key", sa.String(80), nullable=False),
        sa.Column("channel_id", sa.String(80), nullable=False),
        sa.Column("thread_ts", sa.String(80), nullable=False),
        sa.Column("root_user_id", sa.String(80), nullable=False),
        sa.Column("current_intent", sa.String(50), nullable=True),
        sa.Column("interaction_mode", sa.String(50), nullable=True),
        sa.Column(
            "turn_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "recent_messages",
            sa.JSON(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("last_event_id", sa.String(120), nullable=True),
        sa.Column("last_auto_run_id", sa.String(100), nullable=True),
        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="active",
        ),
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
        sa.UniqueConstraint(
            "workspace_key",
            "channel_id",
            "thread_ts",
            name="uq_command_slack_insight_thread_route",
        ),
    )
    for column in (
        "workspace_key",
        "channel_id",
        "root_user_id",
        "current_intent",
        "last_auto_run_id",
        "status",
    ):
        op.create_index(
            f"ix_command_slack_insight_threads_{column}",
            "command_slack_insight_threads",
            [column],
        )


def downgrade() -> None:
    op.drop_table("command_slack_insight_threads")
    op.drop_index(
        "ix_command_slack_insight_events_intent",
        table_name="command_slack_insight_events",
    )
    op.drop_index(
        "ix_command_slack_insight_events_conversation_id",
        table_name="command_slack_insight_events",
    )
    op.drop_column("command_slack_insight_events", "interaction_mode")
    op.drop_column("command_slack_insight_events", "intent")
    op.drop_column("command_slack_insight_events", "conversation_id")
    op.drop_column("command_slack_insight_events", "event_type")
