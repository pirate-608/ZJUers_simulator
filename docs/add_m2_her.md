# M2-her 钉钉消息集成完成

## 变更清单

### 1. [NEW] [dingtalk_llm.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/core/dingtalk_llm.py) — M2-her 原生 API 模块

核心设计：
- **角色映射**：[characters.json](file:///d:/projects/ZJUers_simulator/zjus-backend/world/characters.json) → M2-her `system`/`user_system`/`group`/`sample_message_*` 角色
- **httpx 直调**：直接请求 `api.minimaxi.com` 原生 API，不依赖 OpenAI SDK
- **上下文感知选角**：根据 [context](file:///d:/projects/ZJUers_simulator/zjus-backend/app/services/game_service.py#24-75)（low_sanity/high_stress/low_gpa）加权选择适合的角色
- **并发 + 缓存**：每次随机选 2-3 个角色并发生成，多余消息存入 Redis 队列 `game:dingtalk_m2her`
- **敏感词检测**：M2-her 返回 `output_sensitive` 时自动丢弃

```diff:dingtalk_llm.py
===
"""
MiniMax M2-her 钉钉消息生成模块

将 characters.json 中的角色映射到 M2-her 的 RP 角色系统，
使用 httpx 直接调用原生 API，生成高质量角色扮演钉钉消息。
"""

import json
import random
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any

import httpx

from app.core.config import settings
from app.api.cache import RedisCache

logger = logging.getLogger(__name__)

# Redis 缓存配置
_CACHE_KEY = "game:dingtalk_m2her"
_CACHE_MAX_LEN = 100
_CACHE_TTL_SECONDS = 6 * 60 * 60  # 6 小时


# ==========================================
# 数据加载
# ==========================================

def _load_characters() -> List[Dict[str, Any]]:
    """加载 characters.json"""
    base_dir = Path(__file__).resolve().parent.parent.parent
    char_path = (
        Path("/app/world/characters.json")
        if Path("/app/world/characters.json").exists()
        else base_dir / "world" / "characters.json"
    )
    try:
        with open(char_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.error("Failed to load characters.json")
        return []


# ==========================================
# M2-her 消息构建
# ==========================================

def _build_m2her_messages(
    character: Dict[str, Any],
    player_stats: dict,
    context: str,
) -> List[Dict[str, Any]]:
    """
    将一个 character 条目映射为 M2-her 的结构化 messages。

    利用 M2-her 独有的角色类型：
    - system: AI 角色设定
    - user_system: 用户/玩家身份设定
    - group: 场景/背景设定
    - sample_message_ai / sample_message_user: 示例对话
    """
    char_name = character.get("name", "未知")
    char_content = character.get("content", "")
    examples = character.get("examples", [])

    username = player_stats.get("username", "同学")
    major = player_stats.get("major", "未知专业")
    semester = player_stats.get("semester", "大一秋冬")
    stress = int(player_stats.get("stress", 0))
    sanity = int(player_stats.get("sanity", 50))

    messages = []

    # 1. system — AI 角色人设
    messages.append({
        "role": "system",
        "name": char_name,
        "content": char_content,
    })

    # 2. user_system — 玩家身份/状态
    player_desc = (
        f"你是一位浙江大学{major}专业的学生，名叫{username}，"
        f"目前处于{semester}。"
    )
    if stress > 70:
        player_desc += "你最近压力很大，看起来很疲惫。"
    elif sanity < 30:
        player_desc += "你最近心态不太好，情绪低落。"

    messages.append({
        "role": "user_system",
        "content": player_desc,
    })

    # 3. group — 场景设定
    context_desc_map = {
        "random": "日常校园生活",
        "low_sanity": "学生情绪低落需要关心",
        "high_stress": "学生压力大需要适度放松",
        "low_gpa": "学生成绩亮红灯需要学业提醒",
    }
    scene = context_desc_map.get(context, "日常校园生活")
    messages.append({
        "role": "group",
        "content": f"场景：浙江大学校园，{semester}，钉钉消息对话。当前情境：{scene}。",
    })

    # 4. sample_message — 从 examples 中选取示例对话
    sample_examples = examples[:3] if len(examples) > 3 else examples
    for i, example in enumerate(sample_examples):
        messages.append({
            "role": "sample_message_ai",
            "name": char_name,
            "content": example,
        })
        # 穿插用户回复（简短的通用回复）
        if i < len(sample_examples) - 1:
            messages.append({
                "role": "sample_message_user",
                "name": username,
                "content": random.choice(["好的收到", "了解~", "嗯嗯", "OK"]),
            })

    # 5. user — 触发 AI 生成
    messages.append({
        "role": "user",
        "name": username,
        "content": "（你打开了钉钉，看到一条新消息）",
    })

    return messages


# ==========================================
# API 调用
# ==========================================

async def _call_m2her_api(messages: List[Dict]) -> Optional[str]:
    """调用 MiniMax M2-her 原生 API"""
    api_key = settings.MINIMAX_API_KEY
    base_url = settings.MINIMAX_BASE_URL

    if not api_key:
        return None

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                base_url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "M2-her",
                    "messages": messages,
                    "temperature": 1.0,
                    "top_p": 0.95,
                    "max_completion_tokens": 200,
                },
                timeout=15.0,
            )
            resp.raise_for_status()
            data = resp.json()

            # 检查 base_resp 错误
            base_resp = data.get("base_resp", {})
            if base_resp.get("status_code", 0) != 0:
                logger.warning(
                    "M2-her API error: %s", base_resp.get("status_msg", "unknown")
                )
                return None

            # 检查敏感词
            if data.get("output_sensitive"):
                logger.warning("M2-her output hit sensitive filter")
                return None

            choices = data.get("choices", [])
            if choices:
                return choices[0].get("message", {}).get("content", "").strip()

            return None

    except httpx.TimeoutException:
        logger.warning("M2-her API timeout")
        return None
    except Exception as e:
        logger.error("M2-her API call failed: %s", e)
        return None


# ==========================================
# 主入口
# ==========================================

async def generate_dingtalk_via_m2her(
    player_stats: dict,
    context: str = "random",
) -> Optional[Dict[str, Any]]:
    """
    使用 M2-her 生成单条角色扮演钉钉消息。

    Returns:
        {"sender": "【室友】", "role": "roommate", "content": "...", "is_urgent": false}
        或 None（失败时由调用方 fallback）
    """
    # 0. 无 API key 直接返回 None（由调用方 fallback）
    if not settings.MINIMAX_API_KEY:
        return None

    # 1. 尝试从 Redis 缓存获取
    cached = await RedisCache.lpop(_CACHE_KEY)
    if cached:
        try:
            return json.loads(cached)
        except (json.JSONDecodeError, TypeError):
            pass

    # 2. 加载角色列表并随机选取
    characters = _load_characters()
    if not characters:
        return None

    # 根据 context 做加权选取（某些角色在特定场景下更合适）
    context_role_weights = {
        "low_sanity": {"roommate": 3, "crush": 2, "counselor": 2},
        "high_stress": {"roommate": 3, "classmate": 2, "volunteer_coordinator": 1},
        "low_gpa": {"teaching_assistant": 3, "teacher": 2, "classmate": 2},
        "random": {},  # 均等权重
    }
    weights = context_role_weights.get(context, {})

    weighted_chars = []
    for char in characters:
        role = char.get("role", "")
        w = weights.get(role, 1)
        weighted_chars.extend([char] * w)

    # 选一个主角色 + 额外角色用于补充缓存
    selected_chars = random.sample(
        weighted_chars, min(3, len(weighted_chars))
    )
    # 去重（可能抽到同一个角色多次）
    seen = set()
    unique_chars = []
    for c in selected_chars:
        key = c.get("name", "")
        if key not in seen:
            seen.add(key)
            unique_chars.append(c)

    # 3. 并发调用 M2-her 生成多条消息
    import asyncio

    async def _generate_one(char: Dict) -> Optional[Dict[str, Any]]:
        messages = _build_m2her_messages(char, player_stats, context)
        content = await _call_m2her_api(messages)
        if content:
            return {
                "sender": char.get("name", "未知"),
                "role": char.get("role", "unknown"),
                "content": content,
                "is_urgent": char.get("role") in ("counselor", "system", "teacher"),
            }
        return None

    results = await asyncio.gather(
        *[_generate_one(c) for c in unique_chars],
        return_exceptions=True,
    )

    valid_results = [
        r for r in results
        if isinstance(r, dict)
    ]

    if not valid_results:
        return None

    # 4. 第一条直接返回，剩余存入 Redis 缓存
    current_msg = valid_results[0]
    remaining = [json.dumps(m, ensure_ascii=False) for m in valid_results[1:]]

    if remaining:
        await RedisCache.rpush_many_with_limit(
            _CACHE_KEY,
            remaining,
            max_len=_CACHE_MAX_LEN,
            ttl_seconds=_CACHE_TTL_SECONDS,
        )

    return current_msg
```

---

### 2. [MODIFY] [config.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/core/config.py) — 新增配置

```diff:config.py
from pydantic_settings import BaseSettings
from pydantic import model_validator
import os
import logging
import secrets

_config_logger = logging.getLogger("app.core.config")

# 危险的默认值列表，启动时必须检测
_INSECURE_DEFAULTS = {
    "YOUR_SECRET_KEY_CHANGE_ME",
    "CHANGE_ME_ADMIN_SESSION_SECRET",
    "admin123",
    "password",
    "secret",
}


class Settings(BaseSettings):
    PROJECT_NAME: str = "ZJUers Simulator"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "YOUR_SECRET_KEY_CHANGE_ME"
    )  # 用于JWT加密，生产环境请修改
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # Token有效期7天

    # 数据库配置 (默认为 Docker 中的服务名，本地调试可改为 localhost)
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://zju:password@db/zjuers"
    )

    # Redis配置
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    REDIS_PLAYER_TTL_SECONDS: int = int(
        os.environ.get("REDIS_PLAYER_TTL_SECONDS", 60 * 60 * 24)
    )

    # Admin配置
    ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "admin123")
    ADMIN_SESSION_SECRET: str = os.environ.get(
        "ADMIN_SESSION_SECRET", "CHANGE_ME_ADMIN_SESSION_SECRET"
    )

    # 环境标识：production / development
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")

    class Config:
        env_file = ".env"

    @model_validator(mode="after")
    def _check_insecure_defaults(self) -> "Settings":
        """启动时校验是否存在不安全的默认密钥"""
        is_prod = self.ENVIRONMENT.lower() in ("production", "prod")

        warnings = []
        if self.SECRET_KEY in _INSECURE_DEFAULTS:
            warnings.append("SECRET_KEY 使用了不安全的默认值！JWT 签名可被伪造")
        if self.ADMIN_PASSWORD in _INSECURE_DEFAULTS:
            warnings.append("ADMIN_PASSWORD 使用了不安全的默认值！后台将被入侵")
        if self.ADMIN_SESSION_SECRET in _INSECURE_DEFAULTS:
            warnings.append(
                "ADMIN_SESSION_SECRET 使用了不安全的默认值！Session 可被篡改"
            )

        if warnings:
            msg = (
                "\n⚠️  安全配置告警 ⚠️\n"
                + "\n".join(f"  - {w}" for w in warnings)
                + "\n请通过环境变量或 .env 文件设置安全密钥"
            )
            if is_prod:
                raise ValueError(msg + "\n生产环境无法启动，请先修复。")
            else:
                _config_logger.warning(msg + "\n(开发环境已放行，生产部署务必修改)")

        return self


settings = Settings()
===
from pydantic_settings import BaseSettings
from pydantic import model_validator
import os
import logging
import secrets

_config_logger = logging.getLogger("app.core.config")

# 危险的默认值列表，启动时必须检测
_INSECURE_DEFAULTS = {
    "YOUR_SECRET_KEY_CHANGE_ME",
    "CHANGE_ME_ADMIN_SESSION_SECRET",
    "admin123",
    "password",
    "secret",
}


class Settings(BaseSettings):
    PROJECT_NAME: str = "ZJUers Simulator"
    API_V1_STR: str = "/api"
    SECRET_KEY: str = os.environ.get(
        "SECRET_KEY", "YOUR_SECRET_KEY_CHANGE_ME"
    )  # 用于JWT加密，生产环境请修改
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # Token有效期7天

    # 数据库配置 (默认为 Docker 中的服务名，本地调试可改为 localhost)
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", "postgresql+asyncpg://zju:password@db/zjuers"
    )

    # Redis配置
    REDIS_URL: str = os.environ.get("REDIS_URL", "redis://redis:6379/0")
    REDIS_PLAYER_TTL_SECONDS: int = int(
        os.environ.get("REDIS_PLAYER_TTL_SECONDS", 60 * 60 * 24)
    )

    # Admin配置
    ADMIN_USERNAME: str = os.environ.get("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD: str = os.environ.get("ADMIN_PASSWORD", "admin123")
    ADMIN_SESSION_SECRET: str = os.environ.get(
        "ADMIN_SESSION_SECRET", "CHANGE_ME_ADMIN_SESSION_SECRET"
    )

    # 环境标识：production / development
    ENVIRONMENT: str = os.environ.get("ENVIRONMENT", "development")

    # MiniMax M2-her 配置（钉钉消息 RP 生成）
    MINIMAX_API_KEY: str = os.environ.get("MINIMAX_API_KEY", "")
    MINIMAX_BASE_URL: str = os.environ.get(
        "MINIMAX_BASE_URL",
        "https://api.minimaxi.com/v1/text/chatcompletion_v2",
    )

    class Config:
        env_file = ".env"

    @model_validator(mode="after")
    def _check_insecure_defaults(self) -> "Settings":
        """启动时校验是否存在不安全的默认密钥"""
        is_prod = self.ENVIRONMENT.lower() in ("production", "prod")

        warnings = []
        if self.SECRET_KEY in _INSECURE_DEFAULTS:
            warnings.append("SECRET_KEY 使用了不安全的默认值！JWT 签名可被伪造")
        if self.ADMIN_PASSWORD in _INSECURE_DEFAULTS:
            warnings.append("ADMIN_PASSWORD 使用了不安全的默认值！后台将被入侵")
        if self.ADMIN_SESSION_SECRET in _INSECURE_DEFAULTS:
            warnings.append(
                "ADMIN_SESSION_SECRET 使用了不安全的默认值！Session 可被篡改"
            )

        if warnings:
            msg = (
                "\n⚠️  安全配置告警 ⚠️\n"
                + "\n".join(f"  - {w}" for w in warnings)
                + "\n请通过环境变量或 .env 文件设置安全密钥"
            )
            if is_prod:
                raise ValueError(msg + "\n生产环境无法启动，请先修复。")
            else:
                _config_logger.warning(msg + "\n(开发环境已放行，生产部署务必修改)")

        return self


settings = Settings()
```

---

### 3. [MODIFY] [engine.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/game/engine.py) — M2-her 优先 + 旧接口 fallback

```diff:engine.py
import asyncio
import random
import json
import logging
from pathlib import Path
from sqlalchemy import update
from typing import Callable, Optional

import time

from app.core.llm import (
    generate_cc98_post,
    generate_random_event,
    generate_dingtalk_message,
)
from app.models.user import User
from app.core.database import AsyncSessionLocal
from app.game.balance import balance  # 游戏数值配置
from app.core.events import GameEvent
from app.repositories.redis_repo import RedisRepository
from app.services.save_service import SaveService
from app.services.game_service import GameService

logger = logging.getLogger(__name__)


class GameEngine:
    async def emit(self, event_type: str, data: dict, msg: str = None):
        if msg:
            await self.event_queue.put(
                GameEvent(
                    user_id=self.user_id,
                    event_type="event",
                    data={"data": {"desc": msg}},
                )
            )
        await self.event_queue.put(
            GameEvent(user_id=self.user_id, event_type=event_type, data=data)
        )

    def resume(self):
        if not self.is_running:
            # 注意：不要提前设置 is_running = True，让 run_loop() 自己设置
            # 否则 run_loop() 第一行检查会直接返回
            asyncio.create_task(self.run_loop())
            # 推送最新状态和通知消息
            asyncio.create_task(self._push_update())
            asyncio.create_task(self.emit("resumed", {"msg": "游戏已继续。"}))

    def pause(self):
        self.is_running = False
        # 可选：通知前端已暂停
        asyncio.create_task(self.emit("paused", {"msg": "游戏已暂停，可随时继续。"}))

    def __init__(
        self,
        user_id: str,
        repo: RedisRepository,
        save_service: SaveService,
        game_service: GameService,
        db_factory: Callable = AsyncSessionLocal,
        llm_override: Optional[dict] = None,
    ):
        self.user_id = user_id
        self.repo = repo
        self.save_service = save_service
        self.game_service = game_service
        self.db_factory = db_factory
        self.llm_override = llm_override
        self.event_queue: asyncio.Queue[GameEvent] = asyncio.Queue()
        self.is_running = False
        self._ttl_refresh_interval_seconds = 600
        self._last_ttl_refresh = 0.0
        # ✨ 新增：倍速乘数，默认为 1.0
        self.speed_multiplier = 1.0

        # 预设成就路径
        self.achievement_path = Path("/app/world/achievements.json")
        if not self.achievement_path.exists():
            self.achievement_path = (
                Path(__file__).resolve().parent.parent.parent
                / "world"
                / "achievements.json"
            )

        # ========== 从配置文件加载数值参数 ==========
        # 状态定义: 0=摆(Lay Flat), 1=摸(Chill), 2=卷(Hardcore)
        self.COURSE_STATE_COEFFS = balance.get_course_state_coeffs()
        self.BASE_ENERGY_DRAIN = balance.base_energy_drain
        self.BASE_MASTERY_GROWTH = balance.base_mastery_growth

    async def check_and_trigger_gameover(self) -> bool:
        """检测精力/心态是否归零并触发game over"""
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        if not stats:
            return False
        try:
            # 使用 get(..., 100) 确保即便 Key 不存在也能逻辑运行
            sanity = int(stats.get("sanity", 100))
            energy = int(stats.get("energy", 100))

            reason = ""
            if sanity <= 0:
                reason = "心态崩了，天台风好大..."
            elif energy <= 0:
                reason = "精力耗尽，远去的救护车..."

            if reason:
                await self.emit(
                    "game_over",
                    {"reason": reason, "restartable": True},
                )
                self.stop()
                return True
        except (ValueError, TypeError):
            pass
        return False

    def _sanity_stress_growth_factor(self, sanity, stress):
        """
        心态修正：50为基准，低于50负面影响，极低(<20)最大-40%；高于50正面提升，最佳(80+)+20%
        压力修正：40-70为最佳区间，区间内+30%，区间外-15%，极端（<20或>90）-40%
        """
        # 从配置加载参数
        growth_mod = balance.get_growth_modifiers()
        sanity_cfg = growth_mod.get("sanity", {})
        stress_cfg = growth_mod.get("stress", {})

        # 心态修正
        critical_threshold = sanity_cfg.get("critical_low", {}).get("threshold", 20)
        critical_factor = sanity_cfg.get("critical_low", {}).get("factor", 0.6)
        low_slope = sanity_cfg.get("low_slope", 0.013)
        high_slope = sanity_cfg.get("high_slope", 0.007)
        excellent_threshold = sanity_cfg.get("excellent", {}).get("threshold", 80)
        excellent_factor = sanity_cfg.get("excellent", {}).get("factor", 1.2)

        if sanity < critical_threshold:
            sanity_factor = critical_factor
        elif sanity < 50:
            sanity_factor = 1 - (50 - sanity) * low_slope
        elif sanity >= excellent_threshold:
            sanity_factor = excellent_factor
        elif sanity > 50:
            sanity_factor = 1 + (sanity - 50) * high_slope
        else:
            sanity_factor = 1.0

        # 压力修正
        optimal_range = stress_cfg.get("optimal_range", [40, 70])
        optimal_factor = stress_cfg.get("optimal_factor", 1.3)
        suboptimal_factor = stress_cfg.get("suboptimal_factor", 0.85)
        extreme_factor = stress_cfg.get("extreme_factor", 0.6)

        if optimal_range[0] <= stress <= optimal_range[1]:
            stress_factor = optimal_factor
        elif 20 <= stress < optimal_range[0] or optimal_range[1] < stress <= 90:
            stress_factor = suboptimal_factor
        else:
            stress_factor = extreme_factor

        return sanity_factor * stress_factor

    def _sanity_stress_exam_factor(self, sanity, stress):
        """
        心态修正：50为基准，低于50分数线性下滑，最低-15分，高于50最多+6分
        压力修正：40-70区间+6分，区间外-5分，极端（<20或>90）-10分
        """
        # 从配置加载参数
        exam_mod = balance.get_exam_modifiers()
        sanity_cfg = exam_mod.get("sanity", {})
        stress_cfg = exam_mod.get("stress", {})

        # 心态
        low_slope = sanity_cfg.get("low_slope", 0.3)
        high_slope = sanity_cfg.get("high_slope", 0.12)
        excellent_bonus = sanity_cfg.get("excellent_bonus", 6)

        if sanity < 50:
            sanity_bonus = (sanity - 50) * low_slope
        elif sanity >= 80:
            sanity_bonus = excellent_bonus
        elif sanity > 50:
            sanity_bonus = (sanity - 50) * high_slope
        else:
            sanity_bonus = 0

        # 压力
        optimal_bonus = stress_cfg.get("optimal_bonus", 6)
        suboptimal_penalty = stress_cfg.get("suboptimal_penalty", -5)
        extreme_penalty = stress_cfg.get("extreme_penalty", -10)

        if 40 <= stress <= 70:
            stress_bonus = optimal_bonus
        elif 20 <= stress < 40 or 70 < stress <= 90:
            stress_bonus = suboptimal_penalty
        else:
            stress_bonus = extreme_penalty

        return sanity_bonus + stress_bonus

    async def run_loop(self):
        """核心循环：基于状态的资源分配计算"""
        if self.is_running:
            return
        self.is_running = True
        logger.info(f"State-based Game loop started for {self.user_id}")

        tick_count = 0
        try:
            while self.is_running:
                # ✨ 核心：真实的睡眠时间被倍速缩短！
                # 例如 2.0 倍速下，真实世界只睡 1.5 秒
                await asyncio.sleep(3.0 / self.speed_multiplier)
                tick_count += 1

                # ✨ 核心：但游戏内的虚拟时间，永远坚定地往前走 3 秒！
                await self.repo.update_stat_safe("elapsed_game_time", 3)

                # 低频 TTL 刷新：仅对活跃玩家做防线更新
                now_ts = asyncio.get_running_loop().time()
                if (
                    now_ts - self._last_ttl_refresh
                    >= self._ttl_refresh_interval_seconds
                ):
                    await self.repo.touch_ttl()
                    self._last_ttl_refresh = now_ts

                # 1. 基础检查
                if await self.check_and_trigger_gameover():
                    break

                # 2. 获取计算所需数据 (并行获取以提升性能)
                snapshot = await self.repo.get_snapshot()
                stats = snapshot.stats.model_dump()
                course_states_raw = snapshot.course_states

                # 解析课程信息
                try:
                    course_info = json.loads(stats.get("course_info_json", "[]"))
                except:
                    course_info = []

                # 如果没有课程（如假期），只自然恢复或轻微消耗
                if not course_info:
                    await self.repo.update_stat_safe("energy", 1)  # 假期回血
                    await self._push_update()
                    continue

                # 3. 核心算法：加权计算
                # -------------------------------------------------
                total_credits = sum(c.get("credits", 1.0) for c in course_info)
                if total_credits <= 0:
                    total_credits = 1.0

                total_drain_factor = 0.0
                mastery_updates = {}

                # 遍历每门课，计算这一跳的进度和对总精力的负担
                for course in course_info:
                    c_id = str(course.get("id"))
                    credits = float(course.get("credits", 1.0))
                    # 获取该课当前状态 (默认1:摸)
                    state_val = int(course_states_raw.get(c_id, 1))
                    coeffs = self.COURSE_STATE_COEFFS.get(
                        state_val, self.COURSE_STATE_COEFFS[1]
                    )
                    # A. 计算擅长度增量
                    iq_buff = (int(stats.get("iq", 100)) - 100) * 0.01
                    # 仅在摸/卷状态下引入心态压力修正
                    if state_val in (1, 2):
                        sanity = int(stats.get("sanity", 80))
                        stress = int(stats.get("stress", 40))
                        factor = self._sanity_stress_growth_factor(sanity, stress)
                    else:
                        factor = 1.0
                    actual_growth = (
                        self.BASE_MASTERY_GROWTH
                        * coeffs["growth"]
                        * (1 + iq_buff)
                        * factor
                    )
                    if actual_growth > 0:
                        mastery_updates[c_id] = actual_growth
                    # B. 计算精力消耗权重
                    weight = credits / total_credits
                    total_drain_factor += weight * coeffs["drain"]

                # 4. 执行更新
                # -------------------------------------------------
                # 批量更新课程进度
                if mastery_updates:
                    await self.repo.batch_update_course_mastery(mastery_updates)

                # 结算总精力消耗
                # 最终消耗 = 基础消耗 * 加权系数（保留浮点数精度）
                final_energy_cost_float = self.BASE_ENERGY_DRAIN * total_drain_factor

                # 修复：只有drain系数真正接近0（全摆烂）才回血
                # 避免"全摸"状态因int截断误判为摆烂
                if final_energy_cost_float < 0.3:  # 真正的摆烂阈值
                    await self.repo.update_stat_safe("energy", 2)
                    await self.repo.update_stat_safe("stress", -2)  # 摆烂降压
                else:
                    # 向上取整，确保至少消耗1点精力
                    import math

                    final_energy_cost = max(1, math.ceil(final_energy_cost_float))
                    await self.repo.update_stat_safe("energy", -final_energy_cost)
                    # 卷多了压力大：如果消耗系数高，增加压力
                    if total_drain_factor > 1.5:
                        await self.repo.update_stat_safe("stress", 1)

                # 5. 随机事件与成就 (从配置读取频率) - 仅在游戏运行时触发
                if self.is_running:
                    event_cfg = balance.get_random_event_config()
                    event_interval = event_cfg.get("check_interval_ticks", 5)
                    event_probability = event_cfg.get("trigger_probability", 0.4)

                    if tick_count % event_interval == 0:
                        if random.random() < event_probability:
                            asyncio.create_task(self._trigger_random_event())
                        await self._check_achievements()

                    # [新增] 6. 钉钉消息 (从配置读取频率) - 仅在游戏运行时触发
                    dingtalk_cfg = balance.get_dingtalk_config()
                    dingtalk_interval = dingtalk_cfg.get("check_interval_ticks", 10)
                    dingtalk_probability = dingtalk_cfg.get("trigger_probability", 0.3)

                    if (
                        tick_count % dingtalk_interval == 0
                        and random.random() < dingtalk_probability
                    ):
                        asyncio.create_task(self._trigger_dingtalk_message())

                await self._push_update()

        except Exception as e:
            logger.error(f"Engine Loop Error: {e}")
            self.stop()

    async def process_action(self, action_data: dict):
        action = action_data.get("action")
        target = action_data.get("target")  # 通常是 course_id
        value = action_data.get("value")  # 新增: 状态值 0/1/2
        if action == "pause":
            self.pause()
            return
        if action == "resume":
            self.resume()
            return
        if action == "restart":
            self.stop()
            initial_stats = self._build_initial_stats("ZJUer")
            await self.repo.set_game_data(initial_stats)
            await self.emit("init", {"data": initial_stats})
            asyncio.create_task(self.run_loop())
            return
        
        # ✨ 新增：真正接管全局倍速
        if action == "set_speed":
            speed = float(action_data.get("speed", 1.0))
            # 限制在合理范围内，防止过快导致服务器 CPU 飙升
            self.speed_multiplier = max(0.5, min(5.0, speed))
            return

        # [新增] 切换课程状态指令
        if action == "change_course_state":
            if target and value is not None:
                # 更新 Redis 状态
                await self.repo.set_course_state(target, int(value))
                # 立即推送一次更新，让前端看到精力预估变化(可选，run_loop也会推)
                await self._push_update()
            return

        # [保留] 其它一次性动作 (Relax/Event)
        try:
            if action == "relax":
                await self._handle_relax(target)
            elif action == "exam":
                await self._handle_final_exam()
            elif action == "event_choice":
                await self._handle_event_choice(action_data)
            elif action == "next_semester":
                await self._next_semester()

            await self.check_and_trigger_gameover()
        except Exception as e:
            logger.error(f"Action Error {action}: {e}")

    async def _handle_final_exam(self):
        """期末考试结算逻辑"""
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        course_mastery = snapshot.courses

        try:
            course_info = json.loads(stats.get("course_info_json", "[]"))
        except:
            course_info = []

        total_credits, total_gp, failed_count = 0, 0, 0
        transcript = []

        sanity = int(stats.get("sanity", 50))
        luck = int(stats.get("luck", 50))

        for course in course_info:
            c_id = str(course.get("id"))
            mastery = float(course_mastery.get(c_id, 0))
            credits = course.get("credits", 1)
            # 考试表现计算公式：擅长度占大头，心态和运气波动
            # 新增：心态压力修正
            sanity = int(stats.get("sanity", 50))
            stress = int(stats.get("stress", 40))
            exam_bonus = self._sanity_stress_exam_factor(sanity, stress)
            luck_bonus = random.uniform(-2, 5) + (luck - 50) / 20
            final_score = max(0, min(100, mastery * 0.9 + exam_bonus + luck_bonus + 10))

            # 5分制绩点计算：绩点 = 分数 / 10 - 5，最低0分
            gp = max(0.0, round(final_score / 10 - 5, 2))
            # 挂科阈值从配置读取
            fail_threshold = balance.fail_threshold
            if final_score < fail_threshold:
                failed_count += 1

            total_credits += credits
            total_gp += gp * credits
            transcript.append(
                {
                    "name": course.get("name", "未知课程"),
                    "score": round(final_score, 1),
                    "gp": round(gp, 2),
                }
            )

        gpa = round(total_gp / total_credits, 2) if total_credits > 0 else 0.0

        # 结果反馈（从配置读取惩罚/奖励）
        msg = f"期末考试结束！GPA: {gpa}"
        if failed_count > 0:
            penalty = balance.fail_sanity_penalty * failed_count
            await self.repo.update_stat_safe("sanity", penalty)
            msg += f" | 挂了 {failed_count} 门！"
        else:
            bonus = balance.pass_all_bonus
            await self.repo.update_stat_safe("sanity", bonus)

        # 异步更新持久化数据库
        asyncio.create_task(self._update_db_highest_gpa(gpa))

        # 发送结算弹窗和通知
        await self.emit(
            "semester_summary",
            {
                "data": {
                    "gpa": str(gpa),
                    "failed_count": failed_count,
                    "details": transcript,
                }
            },
        )

        await self._push_update(msg)

    async def _update_db_highest_gpa(self, gpa: float):
        """内部方法：持久化最高 GPA 到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                stmt = (
                    update(User)
                    .where(User.id == int(self.user_id))
                    .values(highest_gpa=str(gpa))
                )
                await db.execute(stmt)
                await db.commit()
            await self.repo.update_stats({"highest_gpa": str(gpa)})
        except Exception as e:
            logger.error(f"DB Update Failed: {e}")

    async def _handle_study_action(self, action_type: str, course_id: str):
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        iq = int(stats.get("iq", 90))

        try:
            course_info = json.loads(stats.get("course_info_json", "[]"))
        except:
            course_info = []

        difficulty = 1.0
        for c in course_info:
            if str(c.get("id")) == str(course_id):
                difficulty = float(c.get("difficulty", 1.0))
                break

        mastery_delta = 0
        if action_type == "study":
            # 提升了学习收益率
            efficiency = 4.0 + (iq - 100) * 0.1
            mastery_delta = max(1.0, efficiency / (1 + difficulty))
            await self.repo.update_stat_safe("energy", -5)
            await self.repo.update_stat_safe("stress", 2)
            await self.repo.update_stat_safe("sanity", -1)
            msg = f"你埋头苦读，感觉知识暴涨！(擅长度 +{mastery_delta:.1f}%)"
        elif action_type == "fish":
            mastery_delta = 0.2
            await self.repo.update_stat_safe("energy", -1)
            await self.repo.update_stat_safe("stress", -1)
            await self.repo.update_stat_safe("sanity", 1)
            msg = "你在课上摸鱼，虽然学得慢，但心情不错。"
        elif action_type == "skip":
            await self.repo.update_stat_safe("energy", 2)
            await self.repo.update_stat_safe("stress", -3)
            await self.repo.update_stat_safe("sanity", 2)
            msg = "逃课一时爽，一直逃课一直爽！"

        if mastery_delta > 0:
            await self.repo.update_course_mastery(course_id, mastery_delta)

        await self._push_update(msg)

    async def _handle_relax(self, target: str):
        # 检查冷却时间
        remaining_cd = await self._check_cooldown(target)
        if remaining_cd > 0:
            msg = f"该操作还在冷却中，请等待 {remaining_cd} 秒后再试。"
            await self._push_update(msg)
            return

        # 从配置读取摸鱼动作参数
        action_cfg = balance.get_relax_action(target)
        if not action_cfg:
            msg = f"未知的休闲动作: {target}"
            await self._push_update(msg)
            return

        msg = ""
        if target == "gym":
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()
            current_energy = int(stats.get("energy", 0))
            min_energy = action_cfg.get("min_energy_required", 50)

            if current_energy < min_energy:
                msg = "你太累了，现在去健身只会晕过去..."
            else:
                # 从配置读取数值
                energy_cost = action_cfg.get("energy_cost", -50)
                energy_gain = action_cfg.get("energy_gain", 60)
                sanity_gain = action_cfg.get("sanity_gain", 5)
                stress_change = action_cfg.get("stress_change", -5)

                await self.repo.update_stat_safe("energy", energy_cost)
                await self.repo.update_stat_safe("energy", energy_gain)
                await self.repo.update_stat_safe("sanity", sanity_gain)
                await self.repo.update_stat_safe("stress", stress_change)
                await self.repo.set_cooldown(target, time.time())
                msg = "在风雨操场挥汗如雨，感觉整个人都升华了！"
        elif target == "game":
            energy_cost = action_cfg.get("energy_cost", -5)
            sanity_gain = action_cfg.get("sanity_gain", 20)

            await self.repo.update_stat_safe("energy", energy_cost)
            await self.repo.update_stat_safe("sanity", sanity_gain)
            await self.repo.set_cooldown(target, time.time())
            msg = "宿舍开黑连胜，这就是电子竞技的魅力吗？"
        elif target == "walk":
            stress_change = action_cfg.get("stress_change", -10)

            await self.repo.update_stat_safe("stress", stress_change)
            await self.repo.set_cooldown(target, time.time())
            msg = "启真湖畔的黑天鹅还是那么高傲..."
        elif target == "cc98":
            # CC98随机效果从配置读取
            effects = action_cfg.get("effects", [])
            if not effects:
                # 兜底默认值
                effects = [
                    {"weight": 0.5, "sanity": 8, "stress": -5},
                    {"weight": 0.3, "sanity": -10, "stress": 8},
                    {"weight": 0.2, "sanity": -15, "stress": 15},
                ]

            # 根据权重随机选择效果
            total_weight = sum(e.get("weight", 0) for e in effects)
            roll = random.uniform(0, total_weight)
            cumulative = 0
            selected_effect = effects[0]  # 默认

            for effect in effects:
                cumulative += effect.get("weight", 0)
                if roll <= cumulative:
                    selected_effect = effect
                    break

            # 应用效果
            if "sanity" in selected_effect:
                await self.repo.update_stat_safe("sanity", selected_effect["sanity"])
            if "stress" in selected_effect:
                await self.repo.update_stat_safe("stress", selected_effect["stress"])

            # 生成对应效果描述
            effect_type = (
                "positive" if selected_effect.get("sanity", 0) > 0 else "negative"
            )
            roll = random.randint(1, 100)  # 用于触发词

            if effect_type == "positive":
                trigger_words = [
                    "校友糗事分享",
                    "今日开怀",
                    "难绷瞬间",
                    "幽默段子",
                    "校园梗",
                    "甜蜜爱情故事",
                ]
            else:
                trigger_words = [
                    "凡尔赛GPA",
                    "郁闷小屋",
                    "烂坑",
                    "情侣秀恩爱",
                    "渣男渣女",
                ]

            trigger = random.choice(trigger_words)
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()
            post_content, feedback = await generate_cc98_post(
                stats, effect_type, trigger, llm_override=self.llm_override
            )
            await self.repo.set_cooldown(target, time.time())
            msg = f"你在CC98刷到了：\n{post_content}\n{feedback}"

        await self._push_update(msg)

    # app/game/engine.py

    async def _trigger_random_event(self):
        """触发 LLM 驱动的随机事件（带去重逻辑）"""
        # 再次检查游戏是否暂停（防止暂停时已创建的任务执行）
        if not self.is_running:
            return

        try:
            # 1. 从 Redis 获取该玩家的事件历史
            history = await self.repo.get_event_history()

            # 2. 获取当前状态
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()

            # 3. 调用 LLM（传入历史记录进行避雷）
            event_data = await generate_random_event(
                stats, history, llm_override=self.llm_override
            )

            if event_data:
                # 4. 记录本次事件标题到历史中
                await self.repo.add_event_to_history(event_data["title"])

                # 5. 推送给前端
                await self.emit("random_event", {"data": event_data})
        except Exception as e:
            logger.error(f"Random event error: {e}", exc_info=True)

    # 事件效果允许修改的属性白名单及每次最大变化量
    _ALLOWED_EFFECT_FIELDS = {
        "energy": 50,
        "sanity": 30,
        "stress": 30,
        "eq": 20,
        "luck": 20,
        "reputation": 20,
    }

    async def _handle_event_choice(self, data):
        """处理随机事件的选择结果（带白名单校验）"""
        effects = data.get("effects", {})
        desc = effects.get("desc", "")
        for key, val in effects.items():
            if key == "desc":
                continue
            # 白名单校验：只允许修改预定义字段
            max_delta = self._ALLOWED_EFFECT_FIELDS.get(key)
            if max_delta is None:
                logger.warning(
                    "Blocked illegal effect field '%s' from user %s", key, self.user_id
                )
                continue
            try:
                delta = int(val)
                # 限制单次变化幅度
                delta = max(-max_delta, min(max_delta, delta))
                await self.repo.update_stat_safe(key, delta)
            except (ValueError, TypeError):
                continue
        await self._push_update(f"事件：{desc}")

    async def _trigger_dingtalk_message(self):
        """触发钉钉消息推送"""
        # 再次检查游戏是否暂停
        if not self.is_running:
            return

        try:
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()

            # 简单的上下文判断逻辑
            context = "random"
            sanity = int(stats.get("sanity", 50))
            stress = int(stats.get("stress", 0))
            gpa = float(stats.get("gpa", 0))

            if sanity < 30:
                context = "low_sanity"
            elif stress > 80:
                context = "high_stress"
            elif gpa > 0 and gpa < 2.0:
                context = "low_gpa"

            msg_data = await generate_dingtalk_message(
                stats, context, llm_override=self.llm_override
            )

            if msg_data:
                await self.emit(
                    "dingtalk_message",
                    {"data": msg_data},
                )

        except Exception as e:
            logger.error(f"DingTalk trigger error: {e}", exc_info=True)

    async def _check_achievements(self):
        """成就系统判定逻辑"""
        try:
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()
            action_counts = await self.repo.get_action_counts()

            # 防御性转换
            gpa = float(stats.get("highest_gpa") or 0)
            sanity = int(stats.get("sanity") or 50)
            eq = int(stats.get("eq") or 50)
            study_count = int(action_counts.get("study") or 0)

            if not self.achievement_path.exists():
                return
            with open(self.achievement_path, "r", encoding="utf-8") as f:
                ach_config = json.load(f)

            unlocked = await self.repo.get_unlocked_achievements()

            for code, item in ach_config.items():
                if code in unlocked:
                    continue

                passed = False
                if code == "gpa_king" and gpa >= 4.0:
                    passed = True
                elif code == "broken_heart" and sanity < 10:
                    passed = True
                elif code == "social_butterfly" and eq >= 95:
                    passed = True
                elif code == "library_ghost" and study_count > 50:
                    passed = True

                if passed:
                    await self.repo.unlock_achievement(code)
                    await self.emit(
                        "achievement_unlocked",
                        {"data": item},
                    )
        except Exception as e:
            logger.error(f"Achievement check error: {e}")

    async def _next_semester(self):
        """进入下一学期逻辑"""
        async with self.db_factory() as db:
            transition = await self.game_service.process_semester_transition(
                db,
                holiday_event_factory=generate_random_event,
            )

        current_semester_idx = transition.get("semester_idx")

        if transition.get("status") == "graduated":
            stats = transition.get("stats") or {}
            # 调用AI生成文言文结业总结
            from app.core.llm import generate_wenyan_report

            wenyan_report = await generate_wenyan_report(
                stats, llm_override=self.llm_override
            )
            await self.emit(
                "graduation",
                {
                    "data": {
                        "msg": "恭喜你从折姜大学毕业！",
                        "final_stats": stats,
                        "wenyan_report": wenyan_report,
                    }
                },
            )
            self.stop()
            return

        await self.emit(
            "new_semester",
            {
                "data": {
                    "semester_name": f"第 {current_semester_idx} 学期",
                    "holiday_event": transition.get("holiday_event"),
                }
            },
        )
        await self._push_update("新学期开始了，加油！")

    async def _push_update(self, msg: str = None):
        """统一数据推送接口"""
        try:
            snapshot = await self.repo.get_snapshot()
            new_stats = snapshot.stats.model_dump()
            course_mastery = snapshot.courses
            course_states = snapshot.course_states

            # 计算学期剩余时间
            semester_idx = int(new_stats.get("semester_idx", 1))
            semester_config = balance.semester_config
            base_duration = semester_config.get("durations", {}).get(
                str(semester_idx), semester_config.get("default_duration", 360)
            )
            # ✨ 传入我们在 Redis 中累加的虚拟流逝时间
            elapsed = int(new_stats.get("elapsed_game_time", 0))
            semester_time_left = self._get_semester_time_left(elapsed, base_duration)

            await self.emit(
                "tick",
                {
                    "stats": new_stats,
                    "courses": course_mastery,
                    "course_states": course_states,
                    "semester_time_left": semester_time_left,
                },
                msg,
            )
        except Exception as e:
            logger.error(f"Push failed: {e}")

    def stop(self):
        """安全停止游戏循环"""
        self.is_running = False

    def _get_semester_time_left(self, elapsed_game_time: int, duration_seconds: int) -> int:
        try:
            # 尝试将传入的值强制转换为整型，防范 Redis 中的脏数据或 None
            elapsed = int(elapsed_game_time)
            duration = int(duration_seconds)
            return max(0, duration - elapsed)
        except (TypeError, ValueError):
            # 如果解析失败，兜底返回初始的 duration_seconds
            # 若 duration_seconds 本身也有问题，则返回一个安全的硬编码值（如 360）
            if isinstance(duration_seconds, (int, float)):
                return int(duration_seconds)
            return 360
    def _build_initial_stats(self, username: str) -> dict:
        return {
            "username": username,
            "major": "",
            "major_abbr": "",
            "semester": "大一秋冬",
            "semester_idx": 1,
            "semester_start_time": int(time.time()),
            "energy": 100,
            "sanity": 80,
            "stress": 0,
            "iq": 0,
            "eq": random.randint(60, 90),
            "luck": random.randint(0, 100),
            "gpa": "0.0",
            "highest_gpa": "0.0",
            "reputation": 0,
            "course_plan_json": "",
            "course_info_json": "",
        }

    async def _check_cooldown(self, action_type: str) -> int:
        last_use = await self.repo.get_cooldown_timestamp(action_type)
        if not last_use:
            return 0

        elapsed = time.time() - float(last_use)
        cd_time = balance.get_cooldown(action_type)
        remaining = max(0, cd_time - elapsed)
        return int(remaining)
===
import asyncio
import random
import json
import logging
from pathlib import Path
from sqlalchemy import update
from typing import Callable, Optional

import time

from app.core.llm import (
    generate_cc98_post,
    generate_random_event,
    generate_dingtalk_message,
)
from app.models.user import User
from app.core.database import AsyncSessionLocal
from app.game.balance import balance  # 游戏数值配置
from app.core.events import GameEvent
from app.repositories.redis_repo import RedisRepository
from app.services.save_service import SaveService
from app.services.game_service import GameService

logger = logging.getLogger(__name__)


class GameEngine:
    async def emit(self, event_type: str, data: dict, msg: str = None):
        if msg:
            await self.event_queue.put(
                GameEvent(
                    user_id=self.user_id,
                    event_type="event",
                    data={"data": {"desc": msg}},
                )
            )
        await self.event_queue.put(
            GameEvent(user_id=self.user_id, event_type=event_type, data=data)
        )

    def resume(self):
        if not self.is_running:
            # 注意：不要提前设置 is_running = True，让 run_loop() 自己设置
            # 否则 run_loop() 第一行检查会直接返回
            asyncio.create_task(self.run_loop())
            # 推送最新状态和通知消息
            asyncio.create_task(self._push_update())
            asyncio.create_task(self.emit("resumed", {"msg": "游戏已继续。"}))

    def pause(self):
        self.is_running = False
        # 可选：通知前端已暂停
        asyncio.create_task(self.emit("paused", {"msg": "游戏已暂停，可随时继续。"}))

    def __init__(
        self,
        user_id: str,
        repo: RedisRepository,
        save_service: SaveService,
        game_service: GameService,
        db_factory: Callable = AsyncSessionLocal,
        llm_override: Optional[dict] = None,
    ):
        self.user_id = user_id
        self.repo = repo
        self.save_service = save_service
        self.game_service = game_service
        self.db_factory = db_factory
        self.llm_override = llm_override
        self.event_queue: asyncio.Queue[GameEvent] = asyncio.Queue()
        self.is_running = False
        self._ttl_refresh_interval_seconds = 600
        self._last_ttl_refresh = 0.0
        # ✨ 新增：倍速乘数，默认为 1.0
        self.speed_multiplier = 1.0

        # 预设成就路径
        self.achievement_path = Path("/app/world/achievements.json")
        if not self.achievement_path.exists():
            self.achievement_path = (
                Path(__file__).resolve().parent.parent.parent
                / "world"
                / "achievements.json"
            )

        # ========== 从配置文件加载数值参数 ==========
        # 状态定义: 0=摆(Lay Flat), 1=摸(Chill), 2=卷(Hardcore)
        self.COURSE_STATE_COEFFS = balance.get_course_state_coeffs()
        self.BASE_ENERGY_DRAIN = balance.base_energy_drain
        self.BASE_MASTERY_GROWTH = balance.base_mastery_growth

    async def check_and_trigger_gameover(self) -> bool:
        """检测精力/心态是否归零并触发game over"""
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        if not stats:
            return False
        try:
            # 使用 get(..., 100) 确保即便 Key 不存在也能逻辑运行
            sanity = int(stats.get("sanity", 100))
            energy = int(stats.get("energy", 100))

            reason = ""
            if sanity <= 0:
                reason = "心态崩了，天台风好大..."
            elif energy <= 0:
                reason = "精力耗尽，远去的救护车..."

            if reason:
                await self.emit(
                    "game_over",
                    {"reason": reason, "restartable": True},
                )
                self.stop()
                return True
        except (ValueError, TypeError):
            pass
        return False

    def _sanity_stress_growth_factor(self, sanity, stress):
        """
        心态修正：50为基准，低于50负面影响，极低(<20)最大-40%；高于50正面提升，最佳(80+)+20%
        压力修正：40-70为最佳区间，区间内+30%，区间外-15%，极端（<20或>90）-40%
        """
        # 从配置加载参数
        growth_mod = balance.get_growth_modifiers()
        sanity_cfg = growth_mod.get("sanity", {})
        stress_cfg = growth_mod.get("stress", {})

        # 心态修正
        critical_threshold = sanity_cfg.get("critical_low", {}).get("threshold", 20)
        critical_factor = sanity_cfg.get("critical_low", {}).get("factor", 0.6)
        low_slope = sanity_cfg.get("low_slope", 0.013)
        high_slope = sanity_cfg.get("high_slope", 0.007)
        excellent_threshold = sanity_cfg.get("excellent", {}).get("threshold", 80)
        excellent_factor = sanity_cfg.get("excellent", {}).get("factor", 1.2)

        if sanity < critical_threshold:
            sanity_factor = critical_factor
        elif sanity < 50:
            sanity_factor = 1 - (50 - sanity) * low_slope
        elif sanity >= excellent_threshold:
            sanity_factor = excellent_factor
        elif sanity > 50:
            sanity_factor = 1 + (sanity - 50) * high_slope
        else:
            sanity_factor = 1.0

        # 压力修正
        optimal_range = stress_cfg.get("optimal_range", [40, 70])
        optimal_factor = stress_cfg.get("optimal_factor", 1.3)
        suboptimal_factor = stress_cfg.get("suboptimal_factor", 0.85)
        extreme_factor = stress_cfg.get("extreme_factor", 0.6)

        if optimal_range[0] <= stress <= optimal_range[1]:
            stress_factor = optimal_factor
        elif 20 <= stress < optimal_range[0] or optimal_range[1] < stress <= 90:
            stress_factor = suboptimal_factor
        else:
            stress_factor = extreme_factor

        return sanity_factor * stress_factor

    def _sanity_stress_exam_factor(self, sanity, stress):
        """
        心态修正：50为基准，低于50分数线性下滑，最低-15分，高于50最多+6分
        压力修正：40-70区间+6分，区间外-5分，极端（<20或>90）-10分
        """
        # 从配置加载参数
        exam_mod = balance.get_exam_modifiers()
        sanity_cfg = exam_mod.get("sanity", {})
        stress_cfg = exam_mod.get("stress", {})

        # 心态
        low_slope = sanity_cfg.get("low_slope", 0.3)
        high_slope = sanity_cfg.get("high_slope", 0.12)
        excellent_bonus = sanity_cfg.get("excellent_bonus", 6)

        if sanity < 50:
            sanity_bonus = (sanity - 50) * low_slope
        elif sanity >= 80:
            sanity_bonus = excellent_bonus
        elif sanity > 50:
            sanity_bonus = (sanity - 50) * high_slope
        else:
            sanity_bonus = 0

        # 压力
        optimal_bonus = stress_cfg.get("optimal_bonus", 6)
        suboptimal_penalty = stress_cfg.get("suboptimal_penalty", -5)
        extreme_penalty = stress_cfg.get("extreme_penalty", -10)

        if 40 <= stress <= 70:
            stress_bonus = optimal_bonus
        elif 20 <= stress < 40 or 70 < stress <= 90:
            stress_bonus = suboptimal_penalty
        else:
            stress_bonus = extreme_penalty

        return sanity_bonus + stress_bonus

    async def run_loop(self):
        """核心循环：基于状态的资源分配计算"""
        if self.is_running:
            return
        self.is_running = True
        logger.info(f"State-based Game loop started for {self.user_id}")

        tick_count = 0
        try:
            while self.is_running:
                # ✨ 核心：真实的睡眠时间被倍速缩短！
                # 例如 2.0 倍速下，真实世界只睡 1.5 秒
                await asyncio.sleep(3.0 / self.speed_multiplier)
                tick_count += 1

                # ✨ 核心：但游戏内的虚拟时间，永远坚定地往前走 3 秒！
                await self.repo.update_stat_safe("elapsed_game_time", 3)

                # 低频 TTL 刷新：仅对活跃玩家做防线更新
                now_ts = asyncio.get_running_loop().time()
                if (
                    now_ts - self._last_ttl_refresh
                    >= self._ttl_refresh_interval_seconds
                ):
                    await self.repo.touch_ttl()
                    self._last_ttl_refresh = now_ts

                # 1. 基础检查
                if await self.check_and_trigger_gameover():
                    break

                # 2. 获取计算所需数据 (并行获取以提升性能)
                snapshot = await self.repo.get_snapshot()
                stats = snapshot.stats.model_dump()
                course_states_raw = snapshot.course_states

                # 解析课程信息
                try:
                    course_info = json.loads(stats.get("course_info_json", "[]"))
                except:
                    course_info = []

                # 如果没有课程（如假期），只自然恢复或轻微消耗
                if not course_info:
                    await self.repo.update_stat_safe("energy", 1)  # 假期回血
                    await self._push_update()
                    continue

                # 3. 核心算法：加权计算
                # -------------------------------------------------
                total_credits = sum(c.get("credits", 1.0) for c in course_info)
                if total_credits <= 0:
                    total_credits = 1.0

                total_drain_factor = 0.0
                mastery_updates = {}

                # 遍历每门课，计算这一跳的进度和对总精力的负担
                for course in course_info:
                    c_id = str(course.get("id"))
                    credits = float(course.get("credits", 1.0))
                    # 获取该课当前状态 (默认1:摸)
                    state_val = int(course_states_raw.get(c_id, 1))
                    coeffs = self.COURSE_STATE_COEFFS.get(
                        state_val, self.COURSE_STATE_COEFFS[1]
                    )
                    # A. 计算擅长度增量
                    iq_buff = (int(stats.get("iq", 100)) - 100) * 0.01
                    # 仅在摸/卷状态下引入心态压力修正
                    if state_val in (1, 2):
                        sanity = int(stats.get("sanity", 80))
                        stress = int(stats.get("stress", 40))
                        factor = self._sanity_stress_growth_factor(sanity, stress)
                    else:
                        factor = 1.0
                    actual_growth = (
                        self.BASE_MASTERY_GROWTH
                        * coeffs["growth"]
                        * (1 + iq_buff)
                        * factor
                    )
                    if actual_growth > 0:
                        mastery_updates[c_id] = actual_growth
                    # B. 计算精力消耗权重
                    weight = credits / total_credits
                    total_drain_factor += weight * coeffs["drain"]

                # 4. 执行更新
                # -------------------------------------------------
                # 批量更新课程进度
                if mastery_updates:
                    await self.repo.batch_update_course_mastery(mastery_updates)

                # 结算总精力消耗
                # 最终消耗 = 基础消耗 * 加权系数（保留浮点数精度）
                final_energy_cost_float = self.BASE_ENERGY_DRAIN * total_drain_factor

                # 修复：只有drain系数真正接近0（全摆烂）才回血
                # 避免"全摸"状态因int截断误判为摆烂
                if final_energy_cost_float < 0.3:  # 真正的摆烂阈值
                    await self.repo.update_stat_safe("energy", 2)
                    await self.repo.update_stat_safe("stress", -2)  # 摆烂降压
                else:
                    # 向上取整，确保至少消耗1点精力
                    import math

                    final_energy_cost = max(1, math.ceil(final_energy_cost_float))
                    await self.repo.update_stat_safe("energy", -final_energy_cost)
                    # 卷多了压力大：如果消耗系数高，增加压力
                    if total_drain_factor > 1.5:
                        await self.repo.update_stat_safe("stress", 1)

                # 5. 随机事件与成就 (从配置读取频率) - 仅在游戏运行时触发
                if self.is_running:
                    event_cfg = balance.get_random_event_config()
                    event_interval = event_cfg.get("check_interval_ticks", 5)
                    event_probability = event_cfg.get("trigger_probability", 0.4)

                    if tick_count % event_interval == 0:
                        if random.random() < event_probability:
                            asyncio.create_task(self._trigger_random_event())
                        await self._check_achievements()

                    # [新增] 6. 钉钉消息 (从配置读取频率) - 仅在游戏运行时触发
                    dingtalk_cfg = balance.get_dingtalk_config()
                    dingtalk_interval = dingtalk_cfg.get("check_interval_ticks", 10)
                    dingtalk_probability = dingtalk_cfg.get("trigger_probability", 0.3)

                    if (
                        tick_count % dingtalk_interval == 0
                        and random.random() < dingtalk_probability
                    ):
                        asyncio.create_task(self._trigger_dingtalk_message())

                await self._push_update()

        except Exception as e:
            logger.error(f"Engine Loop Error: {e}")
            self.stop()

    async def process_action(self, action_data: dict):
        action = action_data.get("action")
        target = action_data.get("target")  # 通常是 course_id
        value = action_data.get("value")  # 新增: 状态值 0/1/2
        if action == "pause":
            self.pause()
            return
        if action == "resume":
            self.resume()
            return
        if action == "restart":
            self.stop()
            initial_stats = self._build_initial_stats("ZJUer")
            await self.repo.set_game_data(initial_stats)
            await self.emit("init", {"data": initial_stats})
            asyncio.create_task(self.run_loop())
            return
        
        # ✨ 新增：真正接管全局倍速
        if action == "set_speed":
            speed = float(action_data.get("speed", 1.0))
            # 限制在合理范围内，防止过快导致服务器 CPU 飙升
            self.speed_multiplier = max(0.5, min(5.0, speed))
            return

        # [新增] 切换课程状态指令
        if action == "change_course_state":
            if target and value is not None:
                # 更新 Redis 状态
                await self.repo.set_course_state(target, int(value))
                # 立即推送一次更新，让前端看到精力预估变化(可选，run_loop也会推)
                await self._push_update()
            return

        # [保留] 其它一次性动作 (Relax/Event)
        try:
            if action == "relax":
                await self._handle_relax(target)
            elif action == "exam":
                await self._handle_final_exam()
            elif action == "event_choice":
                await self._handle_event_choice(action_data)
            elif action == "next_semester":
                await self._next_semester()

            await self.check_and_trigger_gameover()
        except Exception as e:
            logger.error(f"Action Error {action}: {e}")

    async def _handle_final_exam(self):
        """期末考试结算逻辑"""
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        course_mastery = snapshot.courses

        try:
            course_info = json.loads(stats.get("course_info_json", "[]"))
        except:
            course_info = []

        total_credits, total_gp, failed_count = 0, 0, 0
        transcript = []

        sanity = int(stats.get("sanity", 50))
        luck = int(stats.get("luck", 50))

        for course in course_info:
            c_id = str(course.get("id"))
            mastery = float(course_mastery.get(c_id, 0))
            credits = course.get("credits", 1)
            # 考试表现计算公式：擅长度占大头，心态和运气波动
            # 新增：心态压力修正
            sanity = int(stats.get("sanity", 50))
            stress = int(stats.get("stress", 40))
            exam_bonus = self._sanity_stress_exam_factor(sanity, stress)
            luck_bonus = random.uniform(-2, 5) + (luck - 50) / 20
            final_score = max(0, min(100, mastery * 0.9 + exam_bonus + luck_bonus + 10))

            # 5分制绩点计算：绩点 = 分数 / 10 - 5，最低0分
            gp = max(0.0, round(final_score / 10 - 5, 2))
            # 挂科阈值从配置读取
            fail_threshold = balance.fail_threshold
            if final_score < fail_threshold:
                failed_count += 1

            total_credits += credits
            total_gp += gp * credits
            transcript.append(
                {
                    "name": course.get("name", "未知课程"),
                    "score": round(final_score, 1),
                    "gp": round(gp, 2),
                }
            )

        gpa = round(total_gp / total_credits, 2) if total_credits > 0 else 0.0

        # 结果反馈（从配置读取惩罚/奖励）
        msg = f"期末考试结束！GPA: {gpa}"
        if failed_count > 0:
            penalty = balance.fail_sanity_penalty * failed_count
            await self.repo.update_stat_safe("sanity", penalty)
            msg += f" | 挂了 {failed_count} 门！"
        else:
            bonus = balance.pass_all_bonus
            await self.repo.update_stat_safe("sanity", bonus)

        # 异步更新持久化数据库
        asyncio.create_task(self._update_db_highest_gpa(gpa))

        # 发送结算弹窗和通知
        await self.emit(
            "semester_summary",
            {
                "data": {
                    "gpa": str(gpa),
                    "failed_count": failed_count,
                    "details": transcript,
                }
            },
        )

        await self._push_update(msg)

    async def _update_db_highest_gpa(self, gpa: float):
        """内部方法：持久化最高 GPA 到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                stmt = (
                    update(User)
                    .where(User.id == int(self.user_id))
                    .values(highest_gpa=str(gpa))
                )
                await db.execute(stmt)
                await db.commit()
            await self.repo.update_stats({"highest_gpa": str(gpa)})
        except Exception as e:
            logger.error(f"DB Update Failed: {e}")

    async def _handle_study_action(self, action_type: str, course_id: str):
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        iq = int(stats.get("iq", 90))

        try:
            course_info = json.loads(stats.get("course_info_json", "[]"))
        except:
            course_info = []

        difficulty = 1.0
        for c in course_info:
            if str(c.get("id")) == str(course_id):
                difficulty = float(c.get("difficulty", 1.0))
                break

        mastery_delta = 0
        if action_type == "study":
            # 提升了学习收益率
            efficiency = 4.0 + (iq - 100) * 0.1
            mastery_delta = max(1.0, efficiency / (1 + difficulty))
            await self.repo.update_stat_safe("energy", -5)
            await self.repo.update_stat_safe("stress", 2)
            await self.repo.update_stat_safe("sanity", -1)
            msg = f"你埋头苦读，感觉知识暴涨！(擅长度 +{mastery_delta:.1f}%)"
        elif action_type == "fish":
            mastery_delta = 0.2
            await self.repo.update_stat_safe("energy", -1)
            await self.repo.update_stat_safe("stress", -1)
            await self.repo.update_stat_safe("sanity", 1)
            msg = "你在课上摸鱼，虽然学得慢，但心情不错。"
        elif action_type == "skip":
            await self.repo.update_stat_safe("energy", 2)
            await self.repo.update_stat_safe("stress", -3)
            await self.repo.update_stat_safe("sanity", 2)
            msg = "逃课一时爽，一直逃课一直爽！"

        if mastery_delta > 0:
            await self.repo.update_course_mastery(course_id, mastery_delta)

        await self._push_update(msg)

    async def _handle_relax(self, target: str):
        # 检查冷却时间
        remaining_cd = await self._check_cooldown(target)
        if remaining_cd > 0:
            msg = f"该操作还在冷却中，请等待 {remaining_cd} 秒后再试。"
            await self._push_update(msg)
            return

        # 从配置读取摸鱼动作参数
        action_cfg = balance.get_relax_action(target)
        if not action_cfg:
            msg = f"未知的休闲动作: {target}"
            await self._push_update(msg)
            return

        msg = ""
        if target == "gym":
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()
            current_energy = int(stats.get("energy", 0))
            min_energy = action_cfg.get("min_energy_required", 50)

            if current_energy < min_energy:
                msg = "你太累了，现在去健身只会晕过去..."
            else:
                # 从配置读取数值
                energy_cost = action_cfg.get("energy_cost", -50)
                energy_gain = action_cfg.get("energy_gain", 60)
                sanity_gain = action_cfg.get("sanity_gain", 5)
                stress_change = action_cfg.get("stress_change", -5)

                await self.repo.update_stat_safe("energy", energy_cost)
                await self.repo.update_stat_safe("energy", energy_gain)
                await self.repo.update_stat_safe("sanity", sanity_gain)
                await self.repo.update_stat_safe("stress", stress_change)
                await self.repo.set_cooldown(target, time.time())
                msg = "在风雨操场挥汗如雨，感觉整个人都升华了！"
        elif target == "game":
            energy_cost = action_cfg.get("energy_cost", -5)
            sanity_gain = action_cfg.get("sanity_gain", 20)

            await self.repo.update_stat_safe("energy", energy_cost)
            await self.repo.update_stat_safe("sanity", sanity_gain)
            await self.repo.set_cooldown(target, time.time())
            msg = "宿舍开黑连胜，这就是电子竞技的魅力吗？"
        elif target == "walk":
            stress_change = action_cfg.get("stress_change", -10)

            await self.repo.update_stat_safe("stress", stress_change)
            await self.repo.set_cooldown(target, time.time())
            msg = "启真湖畔的黑天鹅还是那么高傲..."
        elif target == "cc98":
            # CC98随机效果从配置读取
            effects = action_cfg.get("effects", [])
            if not effects:
                # 兜底默认值
                effects = [
                    {"weight": 0.5, "sanity": 8, "stress": -5},
                    {"weight": 0.3, "sanity": -10, "stress": 8},
                    {"weight": 0.2, "sanity": -15, "stress": 15},
                ]

            # 根据权重随机选择效果
            total_weight = sum(e.get("weight", 0) for e in effects)
            roll = random.uniform(0, total_weight)
            cumulative = 0
            selected_effect = effects[0]  # 默认

            for effect in effects:
                cumulative += effect.get("weight", 0)
                if roll <= cumulative:
                    selected_effect = effect
                    break

            # 应用效果
            if "sanity" in selected_effect:
                await self.repo.update_stat_safe("sanity", selected_effect["sanity"])
            if "stress" in selected_effect:
                await self.repo.update_stat_safe("stress", selected_effect["stress"])

            # 生成对应效果描述
            effect_type = (
                "positive" if selected_effect.get("sanity", 0) > 0 else "negative"
            )
            roll = random.randint(1, 100)  # 用于触发词

            if effect_type == "positive":
                trigger_words = [
                    "校友糗事分享",
                    "今日开怀",
                    "难绷瞬间",
                    "幽默段子",
                    "校园梗",
                    "甜蜜爱情故事",
                ]
            else:
                trigger_words = [
                    "凡尔赛GPA",
                    "郁闷小屋",
                    "烂坑",
                    "情侣秀恩爱",
                    "渣男渣女",
                ]

            trigger = random.choice(trigger_words)
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()
            post_content, feedback = await generate_cc98_post(
                stats, effect_type, trigger, llm_override=self.llm_override
            )
            await self.repo.set_cooldown(target, time.time())
            msg = f"你在CC98刷到了：\n{post_content}\n{feedback}"

        await self._push_update(msg)

    # app/game/engine.py

    async def _trigger_random_event(self):
        """触发 LLM 驱动的随机事件（带去重逻辑）"""
        # 再次检查游戏是否暂停（防止暂停时已创建的任务执行）
        if not self.is_running:
            return

        try:
            # 1. 从 Redis 获取该玩家的事件历史
            history = await self.repo.get_event_history()

            # 2. 获取当前状态
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()

            # 3. 调用 LLM（传入历史记录进行避雷）
            event_data = await generate_random_event(
                stats, history, llm_override=self.llm_override
            )

            if event_data:
                # 4. 记录本次事件标题到历史中
                await self.repo.add_event_to_history(event_data["title"])

                # 5. 推送给前端
                await self.emit("random_event", {"data": event_data})
        except Exception as e:
            logger.error(f"Random event error: {e}", exc_info=True)

    # 事件效果允许修改的属性白名单及每次最大变化量
    _ALLOWED_EFFECT_FIELDS = {
        "energy": 50,
        "sanity": 30,
        "stress": 30,
        "eq": 20,
        "luck": 20,
        "reputation": 20,
    }

    async def _handle_event_choice(self, data):
        """处理随机事件的选择结果（带白名单校验）"""
        effects = data.get("effects", {})
        desc = effects.get("desc", "")
        for key, val in effects.items():
            if key == "desc":
                continue
            # 白名单校验：只允许修改预定义字段
            max_delta = self._ALLOWED_EFFECT_FIELDS.get(key)
            if max_delta is None:
                logger.warning(
                    "Blocked illegal effect field '%s' from user %s", key, self.user_id
                )
                continue
            try:
                delta = int(val)
                # 限制单次变化幅度
                delta = max(-max_delta, min(max_delta, delta))
                await self.repo.update_stat_safe(key, delta)
            except (ValueError, TypeError):
                continue
        await self._push_update(f"事件：{desc}")

    async def _trigger_dingtalk_message(self):
        """触发钉钉消息推送（优先使用 M2-her RP 模型）"""
        # 再次检查游戏是否暂停
        if not self.is_running:
            return

        try:
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()

            # 简单的上下文判断逻辑
            context = "random"
            sanity = int(stats.get("sanity", 50))
            stress = int(stats.get("stress", 0))
            gpa = float(stats.get("gpa", 0))

            if sanity < 30:
                context = "low_sanity"
            elif stress > 80:
                context = "high_stress"
            elif gpa > 0 and gpa < 2.0:
                context = "low_gpa"

            # 优先使用 M2-her RP 模型
            msg_data = None
            try:
                from app.core.dingtalk_llm import generate_dingtalk_via_m2her
                msg_data = await generate_dingtalk_via_m2her(stats, context)
            except Exception as e:
                logger.warning(f"M2-her dingtalk fallback: {e}")

            # Fallback 到旧接口
            if not msg_data:
                msg_data = await generate_dingtalk_message(
                    stats, context, llm_override=self.llm_override
                )

            if msg_data:
                await self.emit(
                    "dingtalk_message",
                    {"data": msg_data},
                )

        except Exception as e:
            logger.error(f"DingTalk trigger error: {e}", exc_info=True)

    async def _check_achievements(self):
        """成就系统判定逻辑"""
        try:
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()
            action_counts = await self.repo.get_action_counts()

            # 防御性转换
            gpa = float(stats.get("highest_gpa") or 0)
            sanity = int(stats.get("sanity") or 50)
            eq = int(stats.get("eq") or 50)
            study_count = int(action_counts.get("study") or 0)

            if not self.achievement_path.exists():
                return
            with open(self.achievement_path, "r", encoding="utf-8") as f:
                ach_config = json.load(f)

            unlocked = await self.repo.get_unlocked_achievements()

            for code, item in ach_config.items():
                if code in unlocked:
                    continue

                passed = False
                if code == "gpa_king" and gpa >= 4.0:
                    passed = True
                elif code == "broken_heart" and sanity < 10:
                    passed = True
                elif code == "social_butterfly" and eq >= 95:
                    passed = True
                elif code == "library_ghost" and study_count > 50:
                    passed = True

                if passed:
                    await self.repo.unlock_achievement(code)
                    await self.emit(
                        "achievement_unlocked",
                        {"data": item},
                    )
        except Exception as e:
            logger.error(f"Achievement check error: {e}")

    async def _next_semester(self):
        """进入下一学期逻辑"""
        async with self.db_factory() as db:
            transition = await self.game_service.process_semester_transition(
                db,
                holiday_event_factory=generate_random_event,
            )

        current_semester_idx = transition.get("semester_idx")

        if transition.get("status") == "graduated":
            stats = transition.get("stats") or {}
            # 调用AI生成文言文结业总结
            from app.core.llm import generate_wenyan_report

            wenyan_report = await generate_wenyan_report(
                stats, llm_override=self.llm_override
            )
            await self.emit(
                "graduation",
                {
                    "data": {
                        "msg": "恭喜你从折姜大学毕业！",
                        "final_stats": stats,
                        "wenyan_report": wenyan_report,
                    }
                },
            )
            self.stop()
            return

        await self.emit(
            "new_semester",
            {
                "data": {
                    "semester_name": f"第 {current_semester_idx} 学期",
                    "holiday_event": transition.get("holiday_event"),
                }
            },
        )
        await self._push_update("新学期开始了，加油！")

    async def _push_update(self, msg: str = None):
        """统一数据推送接口"""
        try:
            snapshot = await self.repo.get_snapshot()
            new_stats = snapshot.stats.model_dump()
            course_mastery = snapshot.courses
            course_states = snapshot.course_states

            # 计算学期剩余时间
            semester_idx = int(new_stats.get("semester_idx", 1))
            semester_config = balance.semester_config
            base_duration = semester_config.get("durations", {}).get(
                str(semester_idx), semester_config.get("default_duration", 360)
            )
            # ✨ 传入我们在 Redis 中累加的虚拟流逝时间
            elapsed = int(new_stats.get("elapsed_game_time", 0))
            semester_time_left = self._get_semester_time_left(elapsed, base_duration)

            await self.emit(
                "tick",
                {
                    "stats": new_stats,
                    "courses": course_mastery,
                    "course_states": course_states,
                    "semester_time_left": semester_time_left,
                },
                msg,
            )
        except Exception as e:
            logger.error(f"Push failed: {e}")

    def stop(self):
        """安全停止游戏循环"""
        self.is_running = False

    def _get_semester_time_left(self, elapsed_game_time: int, duration_seconds: int) -> int:
        try:
            # 尝试将传入的值强制转换为整型，防范 Redis 中的脏数据或 None
            elapsed = int(elapsed_game_time)
            duration = int(duration_seconds)
            return max(0, duration - elapsed)
        except (TypeError, ValueError):
            # 如果解析失败，兜底返回初始的 duration_seconds
            # 若 duration_seconds 本身也有问题，则返回一个安全的硬编码值（如 360）
            if isinstance(duration_seconds, (int, float)):
                return int(duration_seconds)
            return 360
    def _build_initial_stats(self, username: str) -> dict:
        from app.schemas.game_state import PlayerStats
        return PlayerStats.build_initial(username=username).model_dump()

    async def _check_cooldown(self, action_type: str) -> int:
        last_use = await self.repo.get_cooldown_timestamp(action_type)
        if not last_use:
            return 0

        elapsed = time.time() - float(last_use)
        cd_time = balance.get_cooldown(action_type)
        remaining = max(0, cd_time - elapsed)
        return int(remaining)
```

## 验证

| 检查项 | 结果 |
|---|---|
| [dingtalk_llm.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/core/dingtalk_llm.py) 语法 | ✅ 编译通过 |
| [config.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/core/config.py) 语法 | ✅ 编译通过 |
| [engine.py](file:///d:/projects/ZJUers_simulator/zjus-backend/app/game/engine.py) 语法 | ✅ 编译通过 |

## 使用方式

在 [.env](file:///d:/projects/ZJUers_simulator/.env) 中添加：
```bash
MINIMAX_API_KEY=your_minimax_api_key_here
# 可选：自定义 API 地址
# MINIMAX_BASE_URL=https://api.minimaxi.com/v1/text/chatcompletion_v2
```

未配置 `MINIMAX_API_KEY` 时自动降级到旧的 [generate_dingtalk_message](file:///d:/projects/ZJUers_simulator/zjus-backend/app/core/llm.py#246-324)。
