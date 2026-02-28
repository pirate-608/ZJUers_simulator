import datetime
from typing import Optional
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.admin import UserRestriction, UserBlacklist


class RestrictionService:
    @staticmethod
    async def get_active_restriction(
        db: AsyncSession, user_id: int
    ) -> Optional[UserRestriction]:
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
        if not identifier:
            return False
        stmt = select(UserBlacklist).where(
            UserBlacklist.identifier == identifier,
            UserBlacklist.identifier_type == identifier_type,
            UserBlacklist.is_active.is_(True),
        )
        result = await db.execute(stmt)
        return result.scalars().first() is not None
