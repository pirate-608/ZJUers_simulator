"""World-data loader for majors, courses, achievements, and static content.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
All gameplay world JSON/Markdown data is read through this service so runtime
code does not need to know whether it is running locally or in Docker.
"""

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WorldService:
    """Load static world data from the mounted or local world directory."""

    _static_cache: Dict[str, Any] = {}
    _cache_lock = asyncio.Lock()

    def __init__(self):
        """Resolve world-data paths for both local runs and Docker images."""
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.world_dir = self.base_dir / "world"
        if not self.world_dir.exists() and Path("/app/world").exists():
            self.world_dir = Path("/app/world")

        self.majors_path = self.world_dir / "majors.json"
        self.courses_dir = self.world_dir / "courses"
        self.achievements_path = self.world_dir / "achievements.json"

    async def _load_json(self, path: Path) -> Any:
        """Load a JSON file with a process-wide async cache."""
        path_str = str(path)
        async with self._cache_lock:
            if path_str in self._static_cache:
                return self._static_cache[path_str]

            if not path.exists():
                logger.error(f"World data missing: {path}")
                return {}

            loop = asyncio.get_running_loop()
            try:
                content = await loop.run_in_executor(None, path.read_text, "utf-8")
                data = json.loads(content)
                self._static_cache[path_str] = data
                return data
            except Exception as e:
                logger.error(f"Failed to parse {path}: {e}")
                return {}

    async def get_all_majors(self) -> List[Dict[str, Any]]:
        """Return all majors as a flat list, regardless of tier grouping."""
        majors_config = await self._load_json(self.majors_path)
        result: List[Dict[str, Any]] = []
        for tier_majors in majors_config.values():
            if isinstance(tier_majors, list):
                result.extend(tier_majors)
        return result

    async def get_major_by_abbr(self, abbr: str) -> Optional[Dict[str, Any]]:
        """Find one major and its first-semester courses by abbreviation."""
        all_majors = await self.get_all_majors()
        for m in all_majors:
            if m.get("abbr") == abbr:
                course_plan = await self._load_json(
                    self.courses_dir / f"{abbr}.json"
                )
                plan_data = course_plan.get("semesters") or course_plan.get("plan", [])
                initial_courses = plan_data[0].get("courses", []) if plan_data else []
                return {
                    "major_info": m,
                    "course_plan": course_plan,
                    "initial_courses": initial_courses,
                }
        return None

    async def get_semester_courses(
        self, major_abbr: str, semester_idx: int
    ) -> List[Dict]:
        """Return the course list for a major and semester index."""
        plan = await self._load_json(self.courses_dir / f"{major_abbr}.json")
        plan_data = plan.get("semesters") or plan.get("plan", [])
        if 0 < semester_idx <= len(plan_data):
            return plan_data[semester_idx - 1].get("courses", [])
        return []
