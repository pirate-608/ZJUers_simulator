# app/services/save_service.py
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from app.models.game_save import GameSave
from app.repositories.redis_repo import RedisRepository
from app.schemas.game_state import PlayerStats

logger = logging.getLogger(__name__)


class SaveService:
    """处理 Redis 与 PostgreSQL 之间的持久化同步"""

    @staticmethod
    async def persist_to_db(repo: RedisRepository, db: AsyncSession) -> bool:
        """将 Redis 数据同步至数据库"""
        try:
            snapshot = await repo.get_snapshot()
            if not snapshot.stats:
                return False

            stats_dict = snapshot.stats.model_dump()

            save_values = {
                "user_id": int(repo.user_id),
                "save_slot": 1,
                "stats_data": stats_dict,
                "courses_data": snapshot.courses,
                "course_states_data": snapshot.course_states,
                "achievements_data": snapshot.achievements,
                "semester_index": int(stats_dict.get("semester_idx", 1)),
            }

            stmt = pg_insert(GameSave).values(**save_values)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_user_save_slot",
                set_={
                    k: v
                    for k, v in save_values.items()
                    if k not in ["user_id", "save_slot"]
                },
            )
            await db.execute(stmt)
            await db.commit()
            return True
        except Exception as e:
            logger.error(f"Persistence failed: {e}")
            await db.rollback()
            return False

    @staticmethod
    async def load_from_db(
        user_id: str, repo: RedisRepository, db: AsyncSession
    ) -> bool:
        """从数据库加载存档写回 Redis"""
        try:
            from sqlalchemy import select

            stmt = select(GameSave).where(
                GameSave.user_id == int(user_id), GameSave.save_slot == 1
            )
            result = await db.execute(stmt)
            save = result.scalars().first()
            if not save:
                return False

            stats_dict = PlayerStats.from_redis(save.stats_data or {}).model_dump()

            await repo.set_game_data(
                stats=stats_dict,
                courses=save.courses_data or {},
                states=save.course_states_data or {},
                achievements=save.achievements_data or [],
            )
            return True
        except Exception as e:
            logger.error(f"Load failed: {e}")
            await db.rollback()
            return False
