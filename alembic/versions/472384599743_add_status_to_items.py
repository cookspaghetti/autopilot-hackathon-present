"""add_status_to_items

Revision ID: 472384599743
Revises: 07e23125fe28
Create Date: 2025-12-05 19:23:20.538584

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "472384599743"
down_revision: Union[str, None] = "07e23125fe28"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add status column to items table
    op.add_column(
        "items",
        sa.Column("status", sa.String(50), nullable=True, server_default="active"),
    )


def downgrade() -> None:
    op.drop_column("items", "status")
