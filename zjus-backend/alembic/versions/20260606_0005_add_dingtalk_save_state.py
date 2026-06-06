"""add dingtalk save state

Revision ID: 20260606_0005
Revises: 20260529_0004
Create Date: 2026-06-06
"""

import sqlalchemy as sa

from alembic import op

revision = "20260606_0005"
down_revision = "20260529_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("game_saves", sa.Column("dingtalk_data", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("game_saves", "dingtalk_data")
