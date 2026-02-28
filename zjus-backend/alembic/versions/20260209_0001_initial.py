"""initial schema

Revision ID: 20260209_0001
Revises:
Create Date: 2026-02-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260209_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("highest_gpa", sa.String(), nullable=True, server_default="0.0"),
        sa.Column("tier", sa.String(), nullable=True),
        sa.Column("exam_score", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("token", sa.String(), nullable=True),
        sa.Column("custom_llm_model", sa.String(), nullable=True),
        sa.Column("custom_llm_api_key", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_token", "users", ["token"], unique=True)

    op.create_table(
        "user_blacklist",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("identifier_type", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("admin_username", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=True),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("details", postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "user_restrictions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("restriction_type", sa.String(length=20), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "game_saves",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("save_slot", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stats_data", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "courses_data", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "course_states_data", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "achievements_data", postgresql.JSON(astext_type=sa.Text()), nullable=True
        ),
        sa.Column(
            "game_version", sa.String(length=20), nullable=True, server_default="1.0.0"
        ),
        sa.Column("semester_index", sa.Integer(), nullable=True),
        sa.Column("total_play_time", sa.Integer(), nullable=True, server_default="0"),
        sa.Column(
            "created_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=True
        ),
        sa.Column(
            "saved_at", sa.TIMESTAMP(), server_default=sa.func.now(), nullable=True
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "save_slot", name="uq_user_save_slot"),
    )


def downgrade() -> None:
    op.drop_table("game_saves")
    op.drop_table("user_restrictions")
    op.drop_table("admin_audit_logs")
    op.drop_table("user_blacklist")
    op.drop_index("ix_users_token", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")
