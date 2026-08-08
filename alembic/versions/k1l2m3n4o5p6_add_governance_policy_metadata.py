"""Add governance policy metadata and missing-fact audit fields.

Revision ID: k1l2m3n4o5p6
Revises: j0k1l2m3n4o5
Create Date: 2026-08-09
"""

import sqlalchemy as sa

from alembic import op

revision = "k1l2m3n4o5p6"
down_revision = "j0k1l2m3n4o5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    tables = set(inspector.get_table_names())

    # The upstream Slack migration originally collided with the first local
    # governance revision ID. Reconcile databases that recorded that revision
    # before the Slack table existed, while remaining a no-op on clean installs.
    if "command_slack_insight_events" not in tables:
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
        for column in (
            "channel_id",
            "user_id",
            "status",
            "auto_run_id",
            "received_at",
        ):
            op.create_index(
                f"ix_command_slack_insight_events_{column}",
                "command_slack_insight_events",
                [column],
            )

    # Some local databases were stamped with the colliding revision for the
    # governance migration before the Slack-thread migration was added. Make
    # the Slack revision's schema whole before applying governance metadata.
    inspector = sa.inspect(op.get_bind())
    event_columns = {
        column["name"]
        for column in inspector.get_columns("command_slack_insight_events")
    }
    event_additions = {
        "event_type": sa.Column(
            "event_type",
            sa.String(30),
            nullable=False,
            server_default="app_mention",
        ),
        "conversation_id": sa.Column("conversation_id", sa.String(64), nullable=True),
        "intent": sa.Column("intent", sa.String(50), nullable=True),
        "interaction_mode": sa.Column("interaction_mode", sa.String(50), nullable=True),
    }
    for name, column in event_additions.items():
        if name not in event_columns:
            op.add_column("command_slack_insight_events", column)

    inspector = sa.inspect(op.get_bind())
    event_indexes = {
        index["name"] for index in inspector.get_indexes("command_slack_insight_events")
    }
    for column in ("conversation_id", "intent"):
        index_name = f"ix_command_slack_insight_events_{column}"
        if index_name not in event_indexes:
            op.create_index(
                index_name,
                "command_slack_insight_events",
                [column],
            )

    tables = set(inspector.get_table_names())
    if "command_slack_insight_threads" not in tables:
        op.create_table(
            "command_slack_insight_threads",
            sa.Column("conversation_id", sa.String(64), primary_key=True),
            sa.Column("workspace_key", sa.String(80), nullable=False),
            sa.Column("channel_id", sa.String(80), nullable=False),
            sa.Column("thread_ts", sa.String(80), nullable=False),
            sa.Column("root_user_id", sa.String(80), nullable=False),
            sa.Column("current_intent", sa.String(50), nullable=True),
            sa.Column("interaction_mode", sa.String(50), nullable=True),
            sa.Column("turn_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "recent_messages", sa.JSON(), nullable=False, server_default="[]"
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

    inspector = sa.inspect(op.get_bind())
    thread_indexes = {
        index["name"]
        for index in inspector.get_indexes("command_slack_insight_threads")
    }
    for column in (
        "workspace_key",
        "channel_id",
        "root_user_id",
        "current_intent",
        "last_auto_run_id",
        "status",
    ):
        index_name = f"ix_command_slack_insight_threads_{column}"
        if index_name not in thread_indexes:
            op.create_index(
                index_name,
                "command_slack_insight_threads",
                [column],
            )

    policy_columns = {
        column["name"] for column in inspector.get_columns("command_policy_definitions")
    }
    additions = {
        "required_facts": sa.Column(
            "required_facts", sa.JSON(), nullable=False, server_default="[]"
        ),
        "action_classes": sa.Column(
            "action_classes", sa.JSON(), nullable=False, server_default="[]"
        ),
        "owner": sa.Column(
            "owner",
            sa.String(255),
            nullable=False,
            server_default="command_center",
        ),
        "change_reason": sa.Column(
            "change_reason", sa.Text(), nullable=False, server_default=""
        ),
        "effective_from": sa.Column(
            "effective_from", sa.DateTime(timezone=True), nullable=True
        ),
        "expires_at": sa.Column(
            "expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    }
    with op.batch_alter_table("command_policy_definitions") as batch:
        for name, column in additions.items():
            if name not in policy_columns:
                batch.add_column(column)

    evaluation_columns = {
        column["name"] for column in inspector.get_columns("command_policy_evaluations")
    }
    if "missing_facts" not in evaluation_columns:
        with op.batch_alter_table("command_policy_evaluations") as batch:
            batch.add_column(
                sa.Column(
                    "missing_facts", sa.JSON(), nullable=False, server_default="[]"
                )
            )


def downgrade() -> None:
    with op.batch_alter_table("command_policy_evaluations") as batch:
        batch.drop_column("missing_facts")

    with op.batch_alter_table("command_policy_definitions") as batch:
        batch.drop_column("expires_at")
        batch.drop_column("effective_from")
        batch.drop_column("change_reason")
        batch.drop_column("owner")
        batch.drop_column("action_classes")
        batch.drop_column("required_facts")
