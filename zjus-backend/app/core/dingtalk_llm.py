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
