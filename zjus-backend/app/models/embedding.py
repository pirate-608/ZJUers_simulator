"""SQLAlchemy model for character embeddings.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
Embeddings come from `characters.json` and are searched with pgvector cosine
distance to select roles matching the current player state.
"""

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

# bge-m3 emits 1024-dimensional vectors.
EMBEDDING_DIM = 1024


class CharacterEmbedding(Base):
    """Precomputed role embedding used by DingTalk character retrieval."""

    __tablename__ = "character_embeddings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Mirrors the `name` field in `characters.json`.
    char_name: Mapped[str] = mapped_column(String(128), index=True)
    # Role tag such as counselor, roommate, or crush.
    char_role: Mapped[str] = mapped_column(String(64), index=True)
    # Source text used to generate the embedding.
    source_text: Mapped[str] = mapped_column(Text)
    # bge-m3 embedding vector.
    embedding: Mapped[Any] = mapped_column(Vector(EMBEDDING_DIM))
    # Full character JSON avoids a second world-file lookup after retrieval.
    char_json: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<CharacterEmbedding {self.char_name} ({self.char_role})>"
