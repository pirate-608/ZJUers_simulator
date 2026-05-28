# app/services/world_service.py
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class WorldService:
    """处理游戏世界静态数据加载 (Majors, Courses, Achievements)"""

    _static_cache: Dict[str, Any] = {}
    _cache_lock = asyncio.Lock()

    def __init__(self):
        # 自动识别环境路径
        self.base_dir = Path(__file__).resolve().parent.parent.parent
        self.world_dir = self.base_dir / "world"
        if not self.world_dir.exists() and Path("/app/world").exists():
            self.world_dir = Path("/app/world")

        self.majors_path = self.world_dir / "majors.json"
        self.courses_dir = self.world_dir / "courses"
        self.achievements_path = self.world_dir / "achievements.json"

    async def _load_json(self, path: Path) -> Any:
        """异步带缓存的加载器"""
        path_str = str(path)
        async with self._cache_lock:
            if path_str in self._static_cache:
                return self._static_cache[path_str]

            if not path.exists():
                logger.error(f"World data missing: {path}")
                return {}

            loop = asyncio.get_running_loop()
            try:
                # 在线程池中执行阻塞 IO
                content = await loop.run_in_executor(None, path.read_text, "utf-8")
                data = json.loads(content)
                self._static_cache[path_str] = data
                return data
            except Exception as e:
                logger.error(f"Failed to parse {path}: {e}")
                return {}

    async def get_all_majors(self) -> List[Dict[str, Any]]:
        """返回所有专业（扁平列表，不按 tier 分组）"""
        majors_config = await self._load_json(self.majors_path)
        result: List[Dict[str, Any]] = []
        for tier_majors in majors_config.values():
            if isinstance(tier_majors, list):
                result.extend(tier_majors)
        return result

    async def get_major_by_abbr(self, abbr: str) -> Optional[Dict[str, Any]]:
        """按缩写查找单个专业并加载课程"""
        all_majors = await self.get_all_majors()
        for m in all_majors:
            if m.get("abbr") == abbr:
                # 加载对应专业的课程培养方案
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
        """获取特定学期的课程表"""
        plan = await self._load_json(self.courses_dir / f"{major_abbr}.json")
        plan_data = plan.get("semesters") or plan.get("plan", [])
        if 0 < semester_idx <= len(plan_data):
            return plan_data[semester_idx - 1].get("courses", [])
        return []
