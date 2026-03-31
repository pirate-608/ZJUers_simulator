"""add pgvector extension and character_embeddings table

Revision ID: 20260331_0002
Revises: 20260209_0001
Create Date: 2026-03-31
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers
revision = "20260331_0002"
down_revision = "20260209_0001"
branch_labels = None
depends_on = None

EMBEDDING_DIM = 1024


def upgrade() -> None:
    # 1. 启用 pgvector 扩展
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # 2. 创建 character_embeddings 表
    op.create_table(
        "character_embeddings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("char_name", sa.String(128), nullable=False, index=True),
        sa.Column("char_role", sa.String(64), nullable=False, index=True),
        sa.Column("source_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("char_json", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    # 3. 创建 HNSW 索引加速余弦距离检索
    op.execute(
        """
        CREATE INDEX ix_character_embeddings_cosine
        ON character_embeddings
        USING hnsw (embedding vector_cosine_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_character_embeddings_cosine")
    op.drop_table("character_embeddings")
    # 注意：不 DROP EXTENSION，因为其他表可能也在用
