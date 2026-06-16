"""remove entrance exam fields from users

Revision ID: 20260528_0003
Revises: 20260331_0002
Create Date: 2026-05-28
"""

import sqlalchemy as sa

from alembic import op

revision = "20260528_0003"
down_revision = "20260331_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "exam_score")
    op.drop_column("users", "tier")


def downgrade() -> None:
    op.add_column("users", sa.Column("tier", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column("exam_score", sa.Integer(), nullable=True, server_default="0"),
    )
