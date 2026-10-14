"""Persistence bridge between Redis active state and PostgreSQL save slots.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
Save slots include stats, courses, actions, achievements, DingTalk contacts,
and item inventory data.
"""

import asyncio
import copy
import logging
from collections.abc import Callable
from typing import Any, Dict, List
from weakref import WeakValueDictionary

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.game.items import items
from app.models.game_save import GameSave
from app.repositories.redis_repo import RedisRepository
from app.schemas.dingtalk import DingTalkState
from app.schemas.game_state import PlayerStats
from app.schemas.holiday import HolidayState

logger = logging.getLogger(__name__)


class SaveService:
    """Synchronize active Redis sessions with PostgreSQL save slots."""

    SAVE_TIMEOUT_SECONDS = 12.0
    _pending: dict[tuple[str, int], asyncio.Task[bool]] = {}
    _capture_locks: WeakValueDictionary[tuple[str, int], asyncio.Lock] = (
        WeakValueDictionary()
    )

    @classmethod
    async def schedule_save(
        cls,
        repo: RedisRepository,
        db_factory: Callable[[], Any],
        save_slot: int = 1,
        snapshot: Any = None,
    ) -> asyncio.Task[bool]:
        """Order capture and enqueue together so older reads cannot overtake saves."""
        key = (str(repo.user_id), save_slot)
        lock = cls._capture_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            cls._capture_locks[key] = lock
        async with lock:
            values = await cls.capture_snapshot(repo, save_slot, snapshot)
            return cls.enqueue_snapshot(values, db_factory)

    @staticmethod
    async def capture_snapshot(
        repo: RedisRepository, save_slot: int = 1, snapshot: Any = None
    ) -> dict[str, Any]:
        """Capture base stats and internal metadata before background persistence."""
        snapshot = snapshot or await repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        holiday = await repo.get_holiday_state()
        stats["_holiday_state"] = holiday.model_dump()
        stats["_semester_summary"] = await repo.get_semester_summary()
        dingtalk = await repo.get_dingtalk_state()
        return copy.deepcopy(
            {
                "user_id": int(repo.user_id),
                "save_slot": save_slot,
                "stats_data": stats,
                "courses_data": snapshot.courses,
                "course_states_data": snapshot.course_states,
                "achievements_data": snapshot.achievements,
                "dingtalk_data": dingtalk.compact().model_dump(),
                "items_data": items.normalize_state(await repo.get_items_state()),
                "semester_index": int(stats.get("semester_idx", 1)),
            }
        )

    @classmethod
    def enqueue_snapshot(
        cls, values: dict[str, Any], db_factory: Callable[[], Any]
    ) -> asyncio.Task[bool]:
        """Queue immutable writes FIFO per user/slot, independently of sockets.

        Each request gets its own session and deadline. Waiting callers use
        shield so a disconnect cannot discard an already accepted autosave.
        """
        values = copy.deepcopy(values)
        key = (str(values["user_id"]), int(values["save_slot"]))
        previous = cls._pending.get(key)

        async def write() -> bool:
            if previous is not None:
                try:
                    await asyncio.shield(previous)
                except asyncio.CancelledError:
                    if not previous.cancelled():
                        raise
                except Exception:
                    logger.exception("Previous save failed for %s", key)
            try:
                async with asyncio.timeout(cls.SAVE_TIMEOUT_SECONDS):
                    async with db_factory() as db:
                        return await cls.persist_snapshot(values, db)
            except Exception:
                logger.exception("Queued save failed or timed out for %s", key)
                return False

        task = asyncio.create_task(write())
        cls._pending[key] = task

        def finished(done: asyncio.Task[bool]) -> None:
            if cls._pending.get(key) is done:
                cls._pending.pop(key, None)
            if not done.cancelled():
                done.exception()

        task.add_done_callback(finished)
        return task

    @classmethod
    async def wait_for_pending(cls, user_id: str, save_slot: int) -> bool:
        """Wait for queued writes before restoring a persistent slot."""
        task = cls._pending.get((str(user_id), save_slot))
        if task is None:
            return True
        return await asyncio.wait_for(
            asyncio.shield(task), timeout=cls.SAVE_TIMEOUT_SECONDS
        )

    @classmethod
    async def drain(cls) -> None:
        """Allow bounded outstanding writes to finish during app shutdown."""
        if cls._pending:
            await asyncio.wait_for(
                asyncio.gather(
                    *(asyncio.shield(task) for task in list(cls._pending.values()))
                ),
                timeout=cls.SAVE_TIMEOUT_SECONDS * 2,
            )

    @staticmethod
    async def persist_to_db(
        repo: RedisRepository, db: AsyncSession, save_slot: int = 1
    ) -> bool:
        """Persist the current Redis session into one save slot.

        Returns:
            True when the save write was committed, otherwise False after
            rollback and logging.
        """
        return await SaveService.persist_snapshot(
            await SaveService.capture_snapshot(repo, save_slot), db
        )

    @staticmethod
    async def persist_snapshot(save_values: dict[str, Any], db: AsyncSession) -> bool:
        """Write a previously captured snapshot without rereading live Redis."""
        try:
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
        """Load a save slot from PostgreSQL back into Redis.

        Returns:
            True when a save exists and was restored into active state.
        """
        try:
            stmt = select(GameSave).where(
                GameSave.user_id == int(user_id), GameSave.save_slot == save_slot
            )
            result = await db.execute(stmt)
            save = result.scalars().first()
            if not save:
                return False

            stats_dict = PlayerStats.from_redis(
                {
                    key: value
                    for key, value in (save.stats_data or {}).items()
                    if not key.startswith("_")
                }
            ).model_dump()

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
            await repo.set_holiday_state(
                HolidayState.from_raw((save.stats_data or {}).get("_holiday_state"))
            )
            await repo.set_active_save_slot(save_slot)
            await repo.set_semester_summary(
                (save.stats_data or {}).get("_semester_summary")
            )
            return True
        except Exception as e:
            logger.error(f"Load failed: {e}")
            await db.rollback()
            return False

    @staticmethod
    async def list_saves(user_id: str, db: AsyncSession) -> List[Dict[str, Any]]:
        """Return save-slot summaries shown by the frontend save selector."""
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
