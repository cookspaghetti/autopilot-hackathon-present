"""Add encrypted integration credential storage.

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-08-08
"""

import sqlalchemy as sa

from alembic import op

revision = "h8i9j0k1l2m3"
down_revision = "g7h8i9j0k1l2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "command_integration_credentials",
        sa.Column("integration_id", sa.String(100), primary_key=True),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
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


def downgrade() -> None:
    op.drop_table("command_integration_credentials")
