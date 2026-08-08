"""Link Workbench decisions to Supervity user forms.

Revision ID: f6g7h8i9j0k1
Revises: e5f6g7h8i9j0
Create Date: 2026-08-07
"""

import sqlalchemy as sa

from alembic import op

revision = "f6g7h8i9j0k1"
down_revision = "e5f6g7h8i9j0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("command_workbench_items") as batch:
        batch.add_column(sa.Column("supervity_form_id", sa.String(255), nullable=True))
        batch.add_column(
            sa.Column("supervity_activity_run_id", sa.String(255), nullable=True)
        )
        batch.add_column(
            sa.Column("supervity_form_status", sa.String(30), nullable=True)
        )
        batch.create_unique_constraint(
            "uq_command_workbench_items_supervity_form_id", ["supervity_form_id"]
        )
        batch.create_index(
            "ix_command_workbench_items_supervity_form_id", ["supervity_form_id"]
        )
        batch.create_index(
            "ix_command_workbench_items_supervity_activity_run_id",
            ["supervity_activity_run_id"],
        )
        batch.create_index(
            "ix_command_workbench_items_supervity_form_status",
            ["supervity_form_status"],
        )


def downgrade() -> None:
    with op.batch_alter_table("command_workbench_items") as batch:
        batch.drop_index("ix_command_workbench_items_supervity_form_status")
        batch.drop_index("ix_command_workbench_items_supervity_activity_run_id")
        batch.drop_index("ix_command_workbench_items_supervity_form_id")
        batch.drop_constraint(
            "uq_command_workbench_items_supervity_form_id", type_="unique"
        )
        batch.drop_column("supervity_form_status")
        batch.drop_column("supervity_activity_run_id")
        batch.drop_column("supervity_form_id")
