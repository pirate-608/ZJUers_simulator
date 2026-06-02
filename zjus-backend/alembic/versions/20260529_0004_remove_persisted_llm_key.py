"""remove persisted custom llm credentials from users

Revision ID: 20260529_0004
Revises: 20260528_0003
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa


revision = "20260529_0004"
down_revision = "20260528_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "custom_llm_api_key")
    op.drop_column("users", "custom_llm_model")


def downgrade() -> None:
    op.add_column("users", sa.Column("custom_llm_model", sa.String(), nullable=True))
    op.add_column("users", sa.Column("custom_llm_api_key", sa.String(), nullable=True))
