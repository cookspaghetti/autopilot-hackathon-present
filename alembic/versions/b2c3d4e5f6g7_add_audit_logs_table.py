"""Add audit_logs table

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-14 14:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6g7"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        # Primary key
        sa.Column("id", sa.Integer(), nullable=False),
        # When
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        # Who
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("actor_ip", sa.String(length=45), nullable=True),
        sa.Column("actor_user_agent", sa.Text(), nullable=True),
        # What
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column(
            "severity", sa.String(length=20), nullable=False, server_default="info"
        ),
        # On What
        sa.Column("resource_type", sa.String(length=100), nullable=True),
        sa.Column("resource_id", sa.String(length=255), nullable=True),
        sa.Column("resource_name", sa.String(length=255), nullable=True),
        # Details
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("extra_data", sa.JSON(), nullable=True),
        # Result
        sa.Column(
            "success", sa.String(length=10), nullable=False, server_default="true"
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        # Context
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("endpoint", sa.String(length=255), nullable=True),
        # Primary key constraint
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes for common query patterns
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"], unique=False)
    op.create_index(
        "ix_audit_logs_timestamp", "audit_logs", ["timestamp"], unique=False
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"], unique=False)
    op.create_index(
        "ix_audit_logs_actor_email", "audit_logs", ["actor_email"], unique=False
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"], unique=False)
    op.create_index("ix_audit_logs_category", "audit_logs", ["category"], unique=False)
    op.create_index(
        "ix_audit_logs_resource_type", "audit_logs", ["resource_type"], unique=False
    )
    op.create_index(
        "ix_audit_logs_resource_id", "audit_logs", ["resource_id"], unique=False
    )

    # Composite index for common filters
    op.create_index(
        "ix_audit_logs_category_timestamp",
        "audit_logs",
        ["category", "timestamp"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_category_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_resource_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_category", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_email", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_id", table_name="audit_logs")
    op.drop_table("audit_logs")
