"""Account restriction checks shared by auth and WebSocket entry points.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The service evaluates bans, blacklist records, and expiry windows without
duplicating moderation logic in route handlers.
"""

import datetime
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import UserBlacklist, UserRestriction


class RestrictionService:
    """Read-only moderation checks for login and WebSocket startup."""

    @staticmethod
    async def get_active_restriction(
        db: AsyncSession, user_id: int
    ) -> Optional[UserRestriction]:
        """Return the currently active restriction for a user, if any."""
        now = datetime.datetime.now(datetime.timezone.utc)
        stmt = select(UserRestriction).where(
            UserRestriction.user_id == int(user_id),
            UserRestriction.is_active.is_(True),
            or_(UserRestriction.expires_at.is_(None), UserRestriction.expires_at > now),
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    @staticmethod
    async def is_blacklisted(
        db: AsyncSession, identifier: str, identifier_type: str
    ) -> bool:
        """Return whether an identifier is currently blacklisted."""
        if not identifier:
            return False
        stmt = select(UserBlacklist).where(
            UserBlacklist.identifier == identifier,
            UserBlacklist.identifier_type == identifier_type,
            UserBlacklist.is_active.is_(True),
        )
        result = await db.execute(stmt)
        return result.scalars().first() is not None
