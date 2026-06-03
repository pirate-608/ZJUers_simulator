"""
角色 Embedding 模型 — 用于 pgvector 向量相似度检索

存储 characters.json 中每个角色的 bge-m3 embedding，
运行时通过余弦距离选取最匹配当前玩家状态的角色。
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# bge-m3 输出维度为 1024
EMBEDDING_DIM = 1024


class CharacterEmbedding(Base):
    __tablename__ = "character_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # 角色名，对应 characters.json 中的 name 字段
    char_name: Mapped[str] = mapped_column(String(128), index=True)
    # 角色的 role 标签 (counselor / roommate / crush / ...)
    char_role: Mapped[str] = mapped_column(String(64), index=True)
    # 用于生成 embedding 的原文摘要
    source_text: Mapped[str] = mapped_column(Text)
    # bge-m3 embedding 向量
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM))
    # 角色的完整 JSON（方便检索后直接使用，无需再查 characters.json）
    char_json: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<CharacterEmbedding {self.char_name} ({self.char_role})>"
