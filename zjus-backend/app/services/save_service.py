# app/services/save_service.py
import logging
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.game.items import items
from app.models.game_save import GameSave
from app.repositories.redis_repo import RedisRepository
from app.schemas.dingtalk import DingTalkState
from app.schemas.game_state import PlayerStats

logger = logging.getLogger(__name__)


class SaveService:
    """处理 Redis 与 PostgreSQL 之间的持久化同步"""

    @staticmethod
    async def persist_to_db(
        repo: RedisRepository, db: AsyncSession, save_slot: int = 1
    ) -> bool:
        """将 Redis 数据同步至数据库"""
        try:
            snapshot = await repo.get_snapshot()
            if not snapshot.stats:
                return False

            stats_dict = snapshot.stats.model_dump()
            dingtalk_state = await repo.get_dingtalk_state()
            items_state = items.normalize_state(await repo.get_items_state())

            save_values = {
                "user_id": int(repo.user_id),
                "save_slot": save_slot,
                "stats_data": stats_dict,
                "courses_data": snapshot.courses,
                "course_states_data": snapshot.course_states,
                "achievements_data": snapshot.achievements,
                "dingtalk_data": dingtalk_state.compact().model_dump(),
                "items_data": items_state,
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
        user_id: str, repo: RedisRepository, db: AsyncSession, save_slot: int = 1
    ) -> bool:
        """从数据库加载存档写回 Redis"""
        try:
            stmt = select(GameSave).where(
                GameSave.user_id == int(user_id), GameSave.save_slot == save_slot
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
                items_state=items.normalize_state(getattr(save, "items_data", None)),
            )
            await repo.set_dingtalk_state(
                DingTalkState.from_raw(getattr(save, "dingtalk_data", None))
            )
            return True
        except Exception as e:
            logger.error(f"Load failed: {e}")
            await db.rollback()
            return False

    @staticmethod
    async def list_saves(user_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
        """列出用户可加载的存档摘要，供前端选择。"""
        stmt = (
            select(GameSave)
            .where(GameSave.user_id == int(user_id))
            .order_by(GameSave.save_slot.asc())
        )
        result = await db.execute(stmt)
        saves = result.scalars().all()

        summaries: List[Dict[str, Any]] = []
        for save in saves:
            stats = save.stats_data or {}
            summaries.append(
                {
                    "save_slot": save.save_slot,
                    "major": stats.get("major") or "未分配专业",
                    "major_abbr": stats.get("major_abbr") or "",
                    "semester": stats.get("semester") or "未知学期",
                    "semester_idx": int(stats.get("semester_idx") or 1),
                    "gpa": str(stats.get("gpa") or "0.0"),
                    "saved_at": save.saved_at.isoformat() if save.saved_at else None,
                    "total_play_time": save.total_play_time or 0,
                }
            )
        return summaries
