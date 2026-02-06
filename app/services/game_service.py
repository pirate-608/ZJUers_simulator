# app/services/game_service.py
import json
import logging
import random
import time
from typing import Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.repositories.redis_repo import RedisRepository
from app.services.save_service import SaveService
from app.services.world_service import WorldService
from app.game.state import RedisState  # 暂时保留用于复杂内部逻辑

logger = logging.getLogger(__name__)


class GameService:
    """负责游戏生命周期的核心逻辑编排"""

    def __init__(self, user_id: str, repo: RedisRepository, world: WorldService):
        self.user_id = user_id
        self.repo = repo
        self.world = world

    async def prepare_game_context(
        self, username: str, tier: str, db: AsyncSession = None
    ) -> Dict[str, Any]:
        """初始化或恢复游戏上下文"""
        # 1. 检查 Redis
        if await self.repo.exists():
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()
            await self._ensure_base_fields(stats, username)
            repaired = False
            if (
                not stats.get("course_info_json")
                or stats.get("course_info_json") == "[]"
            ):
                logger.warning(f"Repairing save for {username}")
                await self._repair_save(tier)
                repaired = True
            return {
                "data": await self.repo.get_all_game_data(),
                "status": "repaired" if repaired else "existing",
            }

        # 2. 尝试从 DB 加载
        if db:
            loaded = await SaveService.load_from_db(self.user_id, self.repo, db)
            if loaded:
                snapshot = await self.repo.get_snapshot()
                stats = snapshot.stats.model_dump()
                await self._ensure_base_fields(stats, username)
                repaired = False
                if (
                    not stats.get("course_info_json")
                    or stats.get("course_info_json") == "[]"
                ):
                    logger.warning(f"Repairing save for {username}")
                    await self._repair_save(tier)
                    repaired = True
                return {
                    "data": await self.repo.get_all_game_data(),
                    "status": "repaired" if repaired else "loaded",
                }

        # 3. 全新初始化
        logger.info(f"Creating new game for {username}")
        state_util = RedisState(self.user_id)
        await state_util.init_game(username, tier)
        await self.assign_major_and_init(tier)
        return {
            "data": await self.repo.get_all_game_data(),
            "status": "new",
        }

    async def _repair_save(self, tier: str):
        """坏档修复逻辑"""
        await self.assign_major_and_init(tier)

    async def assign_major_and_init(self, tier: str) -> Dict[str, Any]:
        """替代原 state.assign_major 方法"""
        assignment = await self.world.get_random_major_assignment(tier)
        major_info = assignment["major_info"]

        snapshot = await self.repo.get_snapshot()
        current_stats = snapshot.stats.model_dump() or {}
        try:
            current_iq = int(current_stats.get("iq"))
        except (TypeError, ValueError):
            current_iq = None
        if not current_iq or current_iq <= 0:
            current_iq = random.randint(80, 100)

        update_fields = {
            "major": major_info["name"],
            "major_abbr": major_info["abbr"],
            "stress": current_stats.get("stress", major_info.get("stress_base", 0)),
            "iq": current_iq + major_info.get("iq_buff", 0),
            "course_plan_json": json.dumps(
                assignment["course_plan"], ensure_ascii=False
            ),
            "course_info_json": json.dumps(
                assignment["initial_courses"], ensure_ascii=False
            ),
            "energy": current_stats.get("energy", 100),
            "sanity": current_stats.get("sanity", 80),
            "eq": current_stats.get("eq", random.randint(60, 90)),
            "luck": current_stats.get("luck", random.randint(0, 100)),
            "gpa": current_stats.get("gpa", "0.0"),
            "reputation": current_stats.get("reputation", 0),
        }

        courses_mastery = {str(c["id"]): 0 for c in assignment["initial_courses"]}
        course_states = {str(c["id"]): 1 for c in assignment["initial_courses"]}

        await self.repo.update_courses_and_states(
            stats_update=update_fields,
            courses=courses_mastery,
            states=course_states,
        )

        return {
            "major": major_info["name"],
            "major_abbr": major_info["abbr"],
            "courses": assignment["initial_courses"],
        }

    async def reset_courses_for_new_semester(self, semester_idx: int):
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump() or {}
        major_abbr = stats.get("major_abbr", "")
        my_courses = await self.world.get_semester_courses(major_abbr, semester_idx)

        sem_names = [
            "大一秋冬",
            "大一春夏",
            "大二秋冬",
            "大二春夏",
            "大三秋冬",
            "大三春夏",
            "大四秋冬",
            "大四春夏",
        ]
        term_name = (
            sem_names[semester_idx - 1]
            if 1 <= semester_idx <= 8
            else f"延毕学期 {semester_idx}"
        )

        update_fields = {
            "semester": term_name,
            "semester_start_time": int(time.time()),
            "course_info_json": json.dumps(my_courses, ensure_ascii=False),
        }

        courses_mastery = {str(c["id"]): 0 for c in my_courses}
        course_states = {str(c["id"]): 1 for c in my_courses}

        await self.repo.update_courses_and_states(
            stats_update=update_fields,
            courses=courses_mastery,
            states=course_states,
        )

    async def _ensure_base_fields(self, stats: Dict[str, Any], username: str):
        repair_fields = {}
        if not stats.get("username"):
            repair_fields["username"] = username
        if not stats.get("semester"):
            repair_fields["semester"] = "大一秋冬"
        if not stats.get("semester_idx"):
            repair_fields["semester_idx"] = 1
        if not stats.get("semester_start_time"):
            repair_fields["semester_start_time"] = int(time.time())
        try:
            current_iq = int(stats.get("iq"))
        except (TypeError, ValueError):
            current_iq = None
        if not current_iq or current_iq <= 0:
            repair_fields["iq"] = random.randint(80, 100)
        if repair_fields:
            await self.repo.update_courses_and_states(stats_update=repair_fields)
