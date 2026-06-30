"""SQLAlchemy models for admin authentication and audit trails.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The admin audit log records operational world-data changes and restore actions.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class UserRestriction(Base):
    """Temporary or permanent account-level play restriction."""

    __tablename__ = "user_restrictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    restriction_type: Mapped[str] = mapped_column(String(20))  # BAN, FREEZE
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserBlacklist(Base):
    """Identifier blacklist entry used before user lookup completes."""

    __tablename__ = "user_blacklist"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    identifier: Mapped[str] = mapped_column(String(255))  # username/token/ip
    identifier_type: Mapped[str] = mapped_column(String(20))  # username, token, ip
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AdminAuditLog(Base):
    """Append-only audit row for privileged admin actions."""

    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    admin_username: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    target_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
