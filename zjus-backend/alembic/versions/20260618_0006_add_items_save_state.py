"""add items save state

Revision ID: 20260618_0006
Revises: 20260606_0005
Create Date: 2026-06-18
"""

import sqlalchemy as sa

from alembic import op

revision = "20260618_0006"
down_revision = "20260606_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("game_saves", sa.Column("items_data", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("game_saves", "items_data")
