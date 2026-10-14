"""Game lifecycle orchestration service.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
`GameService` prepares new/loaded contexts, initializes majors, and advances
semesters while coordinating Redis state and PostgreSQL persistence.
"""

import json
import logging
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.input_safety import safe_username_for_prompt
from app.game.items import items
from app.game.stat_definitions import stat_definitions
from app.repositories.redis_repo import RedisRepository
from app.schemas.game_state import PlayerStats
from app.schemas.holiday import HolidayState
from app.services.save_service import SaveService
from app.services.world_service import WorldService

logger = logging.getLogger(__name__)


class GameService:
    """Coordinate game lifecycle operations outside the real-time engine."""

    def __init__(self, user_id: str, repo: RedisRepository, world: WorldService):
        self.user_id = user_id
        self.repo = repo
        self.world = world

    @staticmethod
    def recover_energy_for_new_semester(current_energy: Any) -> int:
        """Recover halfway from current energy toward the configured baseline."""
        energy_stat = stat_definitions.by_id["energy"]
        baseline = energy_stat.default
        try:
            energy = int(current_energy)
        except (TypeError, ValueError):
            return baseline
        if energy >= baseline:
            return energy
        energy = max(energy_stat.min, energy)
        return min(baseline, (baseline + energy + 1) // 2)

    async def prepare_game_context(
        self,
        username: str,
        db: AsyncSession = None,  # type: ignore
        save_slot: int = 1,
        force_load_save: bool = False,
    ) -> Dict[str, Any]:
        """Load an existing active/save-slot context or report a new game.

        Args:
            username: Current player's prompt-safe username.
            db: Optional database session used to restore persistent saves.
            save_slot: Save slot to load when PostgreSQL persistence is used.
            force_load_save: Select this slot, reusing only matching active Redis.

        Returns:
            A status/data pair consumed by the WebSocket startup route.
        """
        if force_load_save and db:
            if (
                await self.repo.exists()
                and await self.repo.get_active_save_slot() == save_slot
            ):
                return {
                    "data": await self.repo.get_all_game_data(),
                    "status": "existing",
                }
            await SaveService.wait_for_pending(self.user_id, save_slot)
            loaded = await SaveService.load_from_db(
                self.user_id, self.repo, db, save_slot=save_slot
            )
            if loaded:
                return {
                    "data": await self.repo.get_all_game_data(),
                    "status": "loaded",
                }
            return {"data": None, "status": "missing_save"}

        if await self.repo.exists():
            return {
                "data": await self.repo.get_all_game_data(),
                "status": "existing",
            }

        if db:
            await SaveService.wait_for_pending(self.user_id, save_slot)
            loaded = await SaveService.load_from_db(
                self.user_id, self.repo, db, save_slot=save_slot
            )
            if loaded:
                return {
                    "data": await self.repo.get_all_game_data(),
                    "status": "loaded",
                }

        return {"data": None, "status": "new"}

    async def assign_major_and_init(
        self,
        major_abbr: str,
        stat_overrides: Optional[Dict[str, int]] = None,
        username: str = "",
    ) -> Dict[str, Any]:
        """Initialize a new game with a major and registry-validated stats."""
        assignment = await self.world.get_major_by_abbr(major_abbr)
        if not assignment:
            raise ValueError(f"专业 {major_abbr} 不存在")

        major_info = assignment["major_info"]
        overrides = stat_definitions.normalize_initial_allocations(
            stat_overrides or {},
            allow_missing=True,
        )

        safe_username = safe_username_for_prompt(username)
        stat_defaults = stat_definitions.default_stats()
        initial_stats = PlayerStats.build_initial(username=safe_username).model_dump()
        allocated_fields = {stat_id: value for stat_id, value in overrides.items()}
        allocated_fields.update(
            {f"initial_{stat_id}": value for stat_id, value in overrides.items()}
        )
        if "iq" in overrides:
            allocated_fields["iq"] = overrides["iq"] + major_info.get("iq_buff", 0)

        update_fields = {
            "elapsed_game_time": 0,
            "major": major_info["name"],
            "major_abbr": major_info["abbr"],
            "initial_major_abbr": major_info["abbr"],
            "stress": major_info.get("stress_base", 0),
            "energy": stat_defaults["energy"],
            "sanity": stat_defaults["sanity"],
            "gpa": "0.0",
            "highest_gpa": "0.0",
            "gpa_points_total": "0.0",
            "gpa_credits_total": "0.0",
            "reputation": stat_defaults["reputation"],
            "gold": items.initial_gold,
            "semester": "大一秋冬",
            "semester_idx": 1,
            "course_plan_json": json.dumps(
                assignment["course_plan"], ensure_ascii=False
            ),
            "course_info_json": json.dumps(
                assignment["initial_courses"], ensure_ascii=False
            ),
        }
        update_fields.update(allocated_fields)
        initial_stats.update(update_fields)

        courses_mastery = {str(c["id"]): 0 for c in assignment["initial_courses"]}
        course_states = {str(c["id"]): 1 for c in assignment["initial_courses"]}

        await self.repo.set_game_data(
            stats=initial_stats,
            courses=courses_mastery,
            states=course_states,
            achievements=[],
        )

        return {
            "major": major_info["name"],
            "major_abbr": major_info["abbr"],
            "courses": assignment["initial_courses"],
        }

    async def reset_courses_for_new_semester(self, semester_idx: int):
        """Replace course state and recover energy for a newly entered semester."""
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump() or {}
        fields, courses, states, recovery = await self._prepare_semester_data(
            stats, semester_idx
        )
        await self.repo.update_courses_and_states(
            stats_update=fields, courses=courses, states=states
        )
        return {"semester": fields["semester"], "energy_recovery": recovery}

    async def _prepare_semester_data(self, stats: dict, semester_idx: int):
        """Build a complete term before touching any active Redis state."""
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

        energy_default = stat_definitions.by_id["energy"].default
        try:
            current_energy = int(stats.get("energy", energy_default))
        except (TypeError, ValueError):
            current_energy = energy_default
        recovered_energy = self.recover_energy_for_new_semester(current_energy)
        update_fields = {
            "semester_idx": semester_idx,
            "semester": term_name,
            "elapsed_game_time": 0,
            "exam_completed": 0,
            "energy": recovered_energy,
            "course_info_json": json.dumps(my_courses, ensure_ascii=False),
        }

        courses_mastery = {str(c["id"]): 0 for c in my_courses}
        course_states = {str(c["id"]): 1 for c in my_courses}

        return (
            update_fields,
            courses_mastery,
            course_states,
            {
                "before": current_energy,
                "after": recovered_energy,
            },
        )

    async def process_semester_transition(
        self,
        expected_semester_idx: int | None = None,
    ) -> Dict[str, Any]:
        """Commit a term atomically, without waiting for SQL or content generation."""
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        previous_idx = int(stats.get("semester_idx") or 1)
        if previous_idx >= 9 or int(stats.get("exam_completed") or 0) != 1:
            raise ValueError("期末结算完成后才能进入下学期")
        if expected_semester_idx is not None and expected_semester_idx != previous_idx:
            raise ValueError("学期状态已变化，请同步后重试")

        current_semester_idx = previous_idx + 1
        graduated = current_semester_idx > 8
        recovery: dict[str, int] = {}
        if graduated:
            fields, courses, states = {"semester_idx": current_semester_idx}, None, None
            holiday = HolidayState()
        else:
            fields, courses, states, recovery = await self._prepare_semester_data(
                stats, current_semester_idx
            )
            holiday = HolidayState.pending(current_semester_idx)
        if not await self.repo.commit_semester_transition(
            previous_idx, fields, courses, states, holiday
        ):
            raise ValueError("学期已切换或考试状态已变化，请同步后重试")

        current = await self.repo.get_snapshot()
        current_stats = current.stats.model_dump()
        if graduated:
            current_stats["achievements"] = list(current.achievements)
        return {
            "status": "graduated" if graduated else "continued",
            "semester_idx": current_semester_idx,
            "stats": current_stats,
            "snapshot": current,
            "energy_recovery": recovery,
        }
