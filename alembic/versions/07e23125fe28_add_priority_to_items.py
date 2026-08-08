"""add_priority_to_items

Revision ID: 07e23125fe28
Revises: 78594ac01b8d
Create Date: 2025-12-05 19:17:46.508398

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "07e23125fe28"
down_revision: Union[str, None] = "78594ac01b8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add priority column to items table
    op.add_column(
        "items", sa.Column("priority", sa.Integer(), nullable=True, server_default="0")
    )


def downgrade() -> None:
    op.drop_column("items", "priority")
