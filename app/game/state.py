import json
import random
from redis import asyncio as aioredis
from app.core.config import settings
from pathlib import Path

# ==========================================
# 1. 静态资源路径配置
# ==========================================
COURSES_DATA_PATH = Path("/app/world/courses.json")
if not COURSES_DATA_PATH.exists():
    COURSES_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "world" / "courses.json"
MAP_PATH = Path("/app/world/map.json")
if not MAP_PATH.exists():
    MAP_PATH = Path(__file__).resolve().parent.parent.parent / "world" / "map.json"
MAJORS_DATA_PATH = Path("/app/world/majors.json")
if not MAJORS_DATA_PATH.exists():
    MAJORS_DATA_PATH = Path(__file__).resolve().parent.parent.parent / "world" / "majors.json"

class RedisState:
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        self.key = f"player:{user_id}:stats"
        self.course_key = f"player:{user_id}:courses"

    async def close(self):
        await self.redis.close()

    async def exists(self) -> bool:
        return await self.redis.exists(self.key)

    # ==========================================
    # 内部辅助逻辑：课程筛选算法
    # ==========================================
    def _pick_semester_courses(self, all_courses, academy, grade, term, n_req=3, n_gen=2, n_ele=2):
        """核心选课逻辑：安全、随机、解耦"""
        # 预筛选三个池子
        required = [c for c in all_courses if academy in c['majors'] and c.get('required') and c['grade'] == grade and term in c['semester']]
        general = [c for c in all_courses if ('全校通用' in c['majors'] or 'ALL' in c['majors']) and c.get('type') == '通识' and c['grade'] == grade and term in c['semester']]
        elective = [c for c in all_courses if academy in c['majors'] and not c.get('required') and c.get('type') != '通识' and c['grade'] == grade and term in c['semester']]

        # 打乱顺序
        random.shuffle(required)
        random.shuffle(general)
        random.shuffle(elective)

        # 安全取样：切片操作不会像 random.sample 那样因为样本不足而报错
        return (required[:n_req] + general[:n_gen] + elective[:n_ele])

    # ==========================================
    # 2. 游戏初始化逻辑
    # ==========================================
    async def init_game(self, username: str, tier: str):
        # 1. 随机专业分配
        with open(MAJORS_DATA_PATH, "r", encoding="utf-8") as f:
            majors_config = json.load(f)
        available_majors = majors_config.get(tier, majors_config.get("TIER_4"))
        major_info = random.choice(available_majors)
        major_name = major_info["name"]

        # 2. 获取学院映射
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            major2school = json.load(f)
        academy = major2school.get(major_name, "全校通用")

        # 3. 初始数值
        initial_stats = {
            "username": username,
            "major": major_name,
            "semester": "大一秋冬",
            "semester_idx": 1,
            "energy": 100,
            "sanity": 80,
            "stress": major_info.get("stress_base", 0),
            "iq": random.randint(80, 100) + major_info.get("iq_buff", 0),
            "eq": random.randint(60, 90),
            "luck": random.randint(0, 100),
            "reputation": 0,
            "status": "idle",
            "gpa": "0.0",
            "failed_count": 0
        }

        # 4. 课程库初始化
        with open(COURSES_DATA_PATH, "r", encoding="utf-8") as f:
            all_courses = json.load(f)
        
        my_courses = self._pick_semester_courses(all_courses, academy, grade=1, term="秋")
        initial_stats["course_info_json"] = json.dumps(my_courses, ensure_ascii=False)

        # 5. 写入 Redis
        await self.redis.hset(self.key, mapping=initial_stats)
        
        # 6. 课程擅长度初始化
        if my_courses:
            course_mastery = {c["id"]: 0 for c in my_courses}
            await self.redis.hset(self.course_key, mapping=course_mastery)
        
        return initial_stats

    # ==========================================
    # 3. 基础数值操作 (带安全保护)
    # ==========================================
    async def get_stats(self):
        return await self.redis.hgetall(self.key)

    async def update_stat_safe(self, field: str, delta: int, min_val: int = 0, max_val: int = 200):
        """优化后的数值更新：增加边界检查"""
        current = await self.redis.hget(self.key, field)
        val = int(current or 0) + delta
        final_val = max(min_val, min(max_val, val))
        await self.redis.hset(self.key, field, final_val)
        return final_val

    async def update_stat(self, field: str, delta: int):
        """兼容原有调用方式"""
        return await self.redis.hincrby(self.key, field, delta)

    # ==========================================
    # 4. 课程操作
    # ==========================================
    async def get_courses_mastery(self):
        return await self.redis.hgetall(self.course_key)

    async def update_course_mastery(self, course_id: str, delta: float):
        current = await self.redis.hget(self.course_key, course_id)
        current_val = float(current) if current else 0.0
        new_val = max(0.0, min(100.0, current_val + delta))
        await self.redis.hset(self.course_key, course_id, new_val)
        return new_val

    # ==========================================
    # 5. 动作与成就
    # ==========================================
    async def increment_action_count(self, action_type: str):
        key = f"player:{self.user_id}:actions"
        await self.redis.hincrby(key, action_type, 1)

    async def get_action_counts(self):
        key = f"player:{self.user_id}:actions"
        return await self.redis.hgetall(key)

    async def get_unlocked_achievements(self):
        key = f"player:{self.user_id}:achievements"
        return await self.redis.smembers(key)

    async def unlock_achievement(self, code: str):
        key = f"player:{self.user_id}:achievements"
        await self.redis.sadd(key, code)

    # ==========================================
    # 6. 学期循环逻辑
    # ==========================================
    async def increment_semester(self):
        return await self.redis.hincrby(self.key, "semester_idx", 1)

    async def reset_courses_for_new_semester(self, semester_idx: int):
        """重置学期课程池"""
        await self.redis.delete(self.course_key)
        
        # 计算学年年级和学期
        grade = (semester_idx + 1) // 2
        term = "秋" if semester_idx % 2 == 1 else "春"
        
        stats = await self.redis.hgetall(self.key)
        major_name = stats.get("major", "")

        with open(MAP_PATH, "r", encoding="utf-8") as f:
            major2school = json.load(f)
        academy = major2school.get(major_name, "全校通用")

        with open(COURSES_DATA_PATH, "r", encoding="utf-8") as f:
            all_courses = json.load(f)

        my_courses = self._pick_semester_courses(all_courses, academy, grade, term)
        
        # 更新擅长度与课程详情
        if my_courses:
            course_mastery = {c["id"]: 0 for c in my_courses}
            await self.redis.hset(self.course_key, mapping=course_mastery)
            await self.redis.hset(self.key, "course_info_json", json.dumps(my_courses, ensure_ascii=False))

        # 学期显示名称
        sem_names = ["大一秋冬", "大一春夏", "大二秋冬", "大二春夏", "大三秋冬", "大三春夏", "大四秋冬", "大四春夏"]
        name = sem_names[semester_idx - 1] if semester_idx <= 8 else "延毕"
        await self.redis.hset(self.key, "semester", name)