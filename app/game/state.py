import json
import asyncio
import logging
import random
from typing import Optional, Dict, Any, Set, List
from pathlib import Path
from redis import asyncio as aioredis
from app.core.config import settings

logger = logging.getLogger(__name__)

# ==========================================
# 静态资源加载 (保持不变)
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent
MAJORS_DATA_PATH = Path("/app/world/majors.json") if Path("/app/world/majors.json").exists() else BASE_DIR / "world" / "majors.json"
COURSES_DIR = Path("/app/world/courses") if Path("/app/world/courses").exists() else BASE_DIR / "world" / "courses"

_STATIC_CACHE: Dict[str, Any] = {}
_CACHE_LOCK = asyncio.Lock()

async def _load_json_async(path: Path) -> Any:
    """异步非阻塞加载 JSON 文件，带内存缓存和并发锁"""
    path_str = str(path)
    async with _CACHE_LOCK:
        if path_str in _STATIC_CACHE:
            return _STATIC_CACHE[path_str]
        
        if not path.exists():
            logger.warning(f"File not found: {path}")
            return {}

        loop = asyncio.get_running_loop()
        try:
            content = await loop.run_in_executor(None, path.read_text, "utf-8")
            data = json.loads(content)
            _STATIC_CACHE[path_str] = data
            return data
        except Exception as e:
            logger.error(f"Error loading {path}: {e}")
            return {}

class RedisState:
    _connection_pool: Optional[aioredis.ConnectionPool] = None

    def __init__(self, user_id: str):
        self.user_id = user_id
        
        if RedisState._connection_pool is None:
            RedisState._connection_pool = aioredis.ConnectionPool.from_url(
                settings.REDIS_URL, 
                decode_responses=True,
                max_connections=100
            )
        
        self.redis = aioredis.Redis(connection_pool=RedisState._connection_pool)
        self.key = f"player:{user_id}:stats"
        self.course_key = f"player:{user_id}:courses"
        self.course_state_key = f"player:{user_id}:course_states"  # [新增] 存储课程状态
        self.action_key = f"player:{user_id}:actions"
        self.achievement_key = f"player:{user_id}:achievements"
        self.history_key = f"player:{user_id}:event_history" # [新增] 历史记录 Key
        self.cooldown_key = f"player:{user_id}:cooldowns"  # [新增] 冷却时间 Key

    async def clear_all(self):
        """清空玩家所有存档数据"""
        await self.redis.delete(self.key, self.course_key, self.course_state_key, self.action_key, self.achievement_key, self.history_key, self.cooldown_key)
    async def close(self):
        await self.redis.aclose()

    async def exists(self) -> bool:
        return await self.redis.exists(self.key) > 0

    # ==========================================
    # 2. 游戏初始化逻辑
    # ==========================================
    async def init_game(self, username: str, tier: str) -> Dict[str, Any]:
        # 只初始化基础信息，不分配专业
        initial_stats = {
            "username": username,
            "major": "",
            "major_abbr": "",
            "semester": "大一秋冬",
            "semester_idx": 1,
            "energy": 100,
            "sanity": 80,
            "stress": 0,
            "iq": 0,
            "eq": random.randint(60, 90),
            "luck": random.randint(0, 100),
            "gpa": "0.0",
            "reputation": 0,
            "course_plan_json": "",
            "course_info_json": ""
        }
        async with self.redis.pipeline() as pipe:
            pipe.delete(self.key, self.course_key, self.course_state_key, self.action_key, self.achievement_key, self.history_key)
            pipe.hset(self.key, mapping=initial_stats)
            await pipe.execute()
        return initial_stats

    async def assign_major(self, tier: str) -> Dict[str, Any]:
        majors_config = await _load_json_async(MAJORS_DATA_PATH)
        available_majors = majors_config.get(tier, majors_config.get("TIER_4", []))
        if not available_majors:
            available_majors = [{"name": "未知专业", "abbr": "UNK", "stress_base": 0, "iq_buff": 0}]
        major_info = random.choice(available_majors)
        major_abbr = major_info["abbr"]
        course_plan = await _load_json_async(COURSES_DIR / f"{major_abbr}.json")
        # 生成专业相关字段，保留 energy 不被覆盖
        stats = await self.redis.hgetall(self.key)
        update_fields = {
            "major": major_info["name"],
            "major_abbr": major_abbr,
            "stress": stats.get("stress", major_info.get("stress_base", 0)),
            "iq": stats.get("iq", random.randint(80, 100) + major_info.get("iq_buff", 0)),
            "course_plan_json": json.dumps(course_plan, ensure_ascii=False),
            "energy": stats.get("energy", 100),
            "sanity": stats.get("sanity", 80),
            "eq": stats.get("eq", random.randint(60, 90)),
            "luck": stats.get("luck", random.randint(0, 100)),
            "gpa": stats.get("gpa", "0.0"),
            "reputation": stats.get("reputation", 0)
        }
        # 初始化首学期课程
        semester_idx = 1
        plan_data = course_plan.get("semesters") or course_plan.get("plan", [])
        my_courses = []
        if plan_data and len(plan_data) >= semester_idx:
            my_courses = plan_data[semester_idx - 1].get("courses", [])
        update_fields["course_info_json"] = json.dumps(my_courses, ensure_ascii=False)
        async with self.redis.pipeline() as pipe:
            pipe.hset(self.key, mapping=update_fields)
            if my_courses:
                course_mastery = {str(c["id"]): 0 for c in my_courses}
                pipe.hset(self.course_key, mapping=course_mastery)
                course_states = {str(c["id"]): 1 for c in my_courses}
                pipe.hset(self.course_state_key, mapping=course_states)
            await pipe.execute()
        return {
            "major": major_info["name"],
            "major_abbr": major_abbr,
            "course_plan": course_plan,
            "courses": my_courses
        }

    # ==========================================
    # 3. 数值操作
    # ==========================================
    async def get_stats(self) -> Dict[str, str]:
        return await self.redis.hgetall(self.key)

    async def update_stat_safe(self, field: str, delta: int, min_val: int = 0, max_val: int = 200) -> int:
        script = """
        local current = tonumber(redis.call('HGET', KEYS[1], ARGV[1]) or 0)
        local delta = tonumber(ARGV[2])
        local new_val = current + delta
        if new_val < tonumber(ARGV[3]) then new_val = tonumber(ARGV[3]) end
        if new_val > tonumber(ARGV[4]) then new_val = tonumber(ARGV[4]) end
        redis.call('HSET', KEYS[1], ARGV[1], new_val)
        return new_val
        """
        result = await self.redis.eval(script, 1, self.key, field, delta, min_val, max_val)
        return int(result)

    async def update_stat(self, field: str, delta: int) -> int:
        return await self.redis.hincrby(self.key, field, delta)

    # ==========================================
    # 4. 课程状态与进度管理 (核心改动)
    # ==========================================
    async def get_courses_mastery(self) -> Dict[str, str]:
        return await self.redis.hgetall(self.course_key)

    async def update_course_mastery(self, course_id: str, delta: float) -> float:
        """单门课程更新 (保留用于特殊事件)"""
        return await self.redis.hincrbyfloat(self.course_key, course_id, delta)
    
    async def batch_update_course_mastery(self, updates: Dict[str, float]):
        """[新增] 批量更新课程擅长度 (Pipeline 优化)"""
        if not updates:
            return
        async with self.redis.pipeline() as pipe:
            for c_id, delta in updates.items():
                # 注意：hincrbyfloat 不支持边界检查，若需严格封顶100需用Lua
                # 但考虑到性能和engine循环频率，这里直接用原生命令，前端显示限制即可
                pipe.hincrbyfloat(self.course_key, c_id, delta)
            await pipe.execute()

    async def set_course_state(self, course_id: str, state_val: int):
        """[新增] 设置课程状态: 0=摆, 1=摸, 2=卷"""
        await self.redis.hset(self.course_state_key, course_id, state_val)

    async def get_all_course_states(self) -> Dict[str, str]:
        """[新增] 获取所有课程当前状态"""
        return await self.redis.hgetall(self.course_state_key)

    # ==========================================
    # 5. 动作与成就
    # ==========================================
    async def increment_action_count(self, action_type: str) -> int:
        return await self.redis.hincrby(self.action_key, action_type, 1)

    async def get_action_counts(self) -> Dict[str, str]:
        return await self.redis.hgetall(self.action_key)

    async def get_unlocked_achievements(self) -> Set[str]:
        res = await self.redis.smembers(self.achievement_key)
        return set(res) if res else set()

    async def unlock_achievement(self, code: str) -> int:
        return await self.redis.sadd(self.achievement_key, code)
    
    # ==========================================
    # 5.5. 冷却系统 (CD System)
    # ==========================================
    
    async def check_cooldown(self, action_type: str) -> int:
        """检查冷却时间，返回剩余秒数（0=可用）"""
        import time
        from app.game.balance import balance
        
        last_use = await self.redis.hget(self.cooldown_key, action_type)
        if not last_use:
            return 0
        
        elapsed = time.time() - float(last_use)
        # 从配置文件读取冷却时间
        cd_time = balance.get_cooldown(action_type)
        remaining = max(0, cd_time - elapsed)
        return int(remaining)
    
    async def set_cooldown(self, action_type: str):
        """记录动作使用时间"""
        import time
        await self.redis.hset(self.cooldown_key, action_type, time.time())
    
    # ==========================================
    # 6. 事件历史记录 (新增)
    # ==========================================
    
    async def get_event_history(self) -> List[str]:
        """获取最近 10 个事件的标题"""
        # 获取 Redis 列表中所有的标题
        return await self.redis.lrange(self.history_key, 0, -1)

    async def add_event_to_history(self, title: str):
        """记录新发生的事件，并保持队列长度为 10"""
        async with self.redis.pipeline() as pipe:
            # 1. 将新标题推入列表左侧
            pipe.lpush(self.history_key, title)
            # 2. 只保留最近的 10 条记录
            pipe.ltrim(self.history_key, 0, 9)
            await pipe.execute()

    # ==========================================
    # 6. 学期循环
    # ==========================================
    async def increment_semester(self) -> int:
        return await self.redis.hincrby(self.key, "semester_idx", 1)

    async def reset_courses_for_new_semester(self, semester_idx: int):
        raw_plan = await self.redis.hget(self.key, "course_plan_json")
        try:
            course_plan = json.loads(raw_plan) if raw_plan else {}
        except:
            course_plan = {}
        
        plan_data = course_plan.get("semesters") or course_plan.get("plan", [])
        my_courses = []
        if plan_data and 0 < semester_idx <= len(plan_data):
            my_courses = plan_data[semester_idx - 1].get("courses", [])

        sem_names = ["大一秋冬", "大一春夏", "大二秋冬", "大二春夏", "大三秋冬", "大三春夏", "大四秋冬", "大四春夏"]
        term_name = sem_names[semester_idx - 1] if 1 <= semester_idx <= 8 else f"延毕学期 {semester_idx}"

        async with self.redis.pipeline() as pipe:
            pipe.delete(self.course_key)
            pipe.delete(self.course_state_key) # [新增] 清空旧状态
            
            pipe.hset(self.key, "semester", term_name)
            if my_courses:
                # 初始化进度为0
                course_mastery = {str(c["id"]): 0 for c in my_courses}
                pipe.hset(self.course_key, mapping=course_mastery)
                # [新增] 初始化状态为1 (摸)
                course_states = {str(c["id"]): 1 for c in my_courses}
                pipe.hset(self.course_state_key, mapping=course_states)
                
                pipe.hset(self.key, "course_info_json", json.dumps(my_courses, ensure_ascii=False))
            else:
                pipe.hset(self.key, "course_info_json", "[]")
            await pipe.execute()