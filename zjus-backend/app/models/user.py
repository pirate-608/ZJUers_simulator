"""SQLAlchemy user model and account restriction fields.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The user row stores invite-code identity, long-lived student credentials, and
moderation/restriction metadata.
"""

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """Player identity row keyed by normalized username and student token."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)

    highest_gpa: Mapped[str] = mapped_column(String, default="0.0")
    token: Mapped[str | None] = mapped_column(
        String, unique=True, index=True, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
