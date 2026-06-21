"""SQLAlchemy persisted save-slot model.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
`GameSave` stores PostgreSQL snapshots of Redis-backed player state, including
DingTalk and item inventory payloads.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, TIMESTAMP, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class GameSave(Base):
    """Persisted save-slot snapshot for one user."""

    __tablename__ = "game_saves"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    save_slot: Mapped[int] = mapped_column(default=1)

    # JSON state payloads mirror Redis hashes and auxiliary state keys.
    stats_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    courses_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    course_states_data: Mapped[dict[str, Any] | None] = mapped_column(
        JSON, nullable=True
    )
    achievements_data: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True)
    dingtalk_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    items_data: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Metadata is duplicated for fast save-selection summaries.
    game_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    semester_index: Mapped[int | None] = mapped_column(nullable=True)
    total_play_time: Mapped[int] = mapped_column(default=0)

    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.now())
    saved_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("user_id", "save_slot", name="uq_user_save_slot"),
    )
