"""MiniMax M2-her DingTalk role-play message generation.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.

Notes:
    Character definitions from `characters.json` are mapped into M2-her's
    OpenAI-compatible chat API while preserving player-provided RP keys and
    fallback behavior.
"""

import json
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

from openai import APITimeoutError, AsyncOpenAI, OpenAIError

from app.api.cache import RedisCache
from app.core.config import settings
from app.core.input_safety import safe_username_for_prompt
from app.game.stat_definitions import stat_definitions
from app.schemas.dingtalk import (
    build_contact_id,
    is_replyable_role,
    normalize_dingtalk_role,
)

logger = logging.getLogger(__name__)


def _allowed_effect_fields_prompt() -> str:
    return "/".join(sorted(stat_definitions.event_effect_fields))


def _stat_value(stats: Dict[str, Any], stat_id: str) -> int:
    definition = stat_definitions.by_id[stat_id]
    try:
        return int(stats.get(stat_id, definition.default))
    except (TypeError, ValueError):
        return definition.default


def _stat_ratio(value: int, stat_id: str) -> float:
    definition = stat_definitions.by_id[stat_id]
    span = definition.max - definition.min
    if span <= 0:
        return 0.0
    return max(0.0, min(1.0, (value - definition.min) / span))


_M2HER_ALLOWED_ROLES = {
    "system",
    "user",
    "assistant",
    "user_system",
    "group",
    "sample_message_user",
    "sample_message_ai",
}

# Redis-backed cache for platform-default generated messages.
_CACHE_KEY = "game:dingtalk_m2her"
_CACHE_MAX_LEN = 100
_CACHE_TTL_SECONDS = 6 * 60 * 60
_CHARACTER_CACHE: List[Dict[str, Any]] | None = None
_M2HER_CLIENTS: dict[tuple[str, str], AsyncOpenAI] = {}
_DEFAULT_M2HER_BASE_URL = "https://api.minimaxi.com/v1"

_FALLBACK_REPLY_OPTIONS = {
    "roommate": ["哈哈收到", "我马上看看", "你先别急"],
    "classmate": ["可以，我看一下", "等我整理一下资料", "我也有点懵"],
    "friend": ["晚上再说？", "可以啊", "你这也太会了"],
    "teaching_assistant": ["谢谢助教提醒", "我有个问题想问", "我会尽快完成"],
    "teacher": ["谢谢老师", "我会提前准备", "我还有一个问题"],
    "crush": ["还好，你呢？", "我也在想这个", "要不要一起去？"],
}


# ==========================================
# Data loading.
# ==========================================

def _load_characters() -> List[Dict[str, Any]]:
    """Load character-library records from world data."""
    global _CHARACTER_CACHE
    if _CHARACTER_CACHE is not None:
        return _CHARACTER_CACHE

    base_dir = Path(__file__).resolve().parent.parent.parent
    char_path = (
        Path("/app/world/characters.json")
        if Path("/app/world/characters.json").exists()
        else base_dir / "world" / "characters.json"
    )
    try:
        with open(char_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _CHARACTER_CACHE = data if isinstance(data, list) else []
    except Exception:
        logger.error("Failed to load characters.json")
        _CHARACTER_CACHE = []
    return _CHARACTER_CACHE


def get_character_by_contact_id(contact_id: str) -> Optional[Dict[str, Any]]:
    """Find a character-library record by deterministic DingTalk contact ID."""
    for character in _load_characters():
        sender = str(character.get("name") or "未知")
        role = str(character.get("role") or "unknown")
        if build_contact_id(sender, role) == contact_id:
            return character
    return None


def _json_from_text(content: object) -> dict[str, Any]:
    if not isinstance(content, str):
        return {}
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _fallback_reply_options(role: str) -> list[dict[str, str]]:
    role = normalize_dingtalk_role(role)
    options = _FALLBACK_REPLY_OPTIONS.get(
        role, ["好的收到", "我想想怎么回", "可以再说详细点吗"]
    )
    return [
        {"option_id": f"opt_{idx + 1}", "text": text}
        for idx, text in enumerate(options[:3])
    ]


def _coerce_reply_options(value: object, role: str) -> list[dict[str, str]]:
    role = normalize_dingtalk_role(role)
    if not isinstance(value, list):
        return _fallback_reply_options(role)
    options: list[dict[str, str]] = []
    for idx, item in enumerate(value[:3]):
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(item.get("text") or item.get("content") or "").strip()
        else:
            text = ""
        if text:
            options.append({"option_id": f"opt_{idx + 1}", "text": text[:80]})
    return options or _fallback_reply_options(role)


def _sanitize_m2her_messages(messages: List[Dict]) -> list[dict[str, str]]:
    """Keep only MiniMax-documented message fields before sending to the API."""
    sanitized: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "").strip()
        content = str(message.get("content") or "").strip()
        if role in _M2HER_ALLOWED_ROLES and content:
            sanitized.append({"role": role, "content": content})
    return sanitized


async def _generate_reply_options_via_m2her(
    character: Dict[str, Any],
    player_stats: dict,
    npc_message: str,
    context: str,
    llm_override: Optional[dict[str, Any]] = None,
) -> list[dict[str, str]]:
    role = normalize_dingtalk_role(str(character.get("role") or "unknown"))
    if not is_replyable_role(role):
        return []

    messages = _build_m2her_messages(character, player_stats, context)
    messages.append(
        {
            "role": "assistant",
            "content": npc_message,
        }
    )
    messages.append(
        {
            "role": "user",
            "content": (
                "请为玩家生成 2-3 个自然、短句式的回复选项。"
                '严格返回 JSON：{"reply_options":["选项1","选项2","选项3"]}'
            ),
        }
    )
    raw = await _call_m2her_api(
        messages, max_completion_tokens=180, llm_override=llm_override
    )
    data = _json_from_text(raw)
    return _coerce_reply_options(data.get("reply_options"), role)


async def generate_dingtalk_for_character_via_m2her(
    character: Dict[str, Any],
    player_stats: dict,
    context: str = "random",
    llm_override: Optional[dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Generate one opening DingTalk message for a specific character."""
    api_key, _, _ = _resolve_m2her_config(llm_override)
    if not api_key:
        return None

    messages = _build_m2her_messages(character, player_stats, context)
    content = await _call_m2her_api(messages, llm_override=llm_override)
    if not content:
        return None

    sender = str(character.get("name") or "未知")
    role = normalize_dingtalk_role(str(character.get("role") or "unknown"))
    reply_options = await _generate_reply_options_via_m2her(
        character,
        player_stats,
        content,
        context,
        llm_override=llm_override,
    )
    contact_id = build_contact_id(sender, role)
    is_urgent = role in ("counselor", "system", "teacher")
    return {
        "sender": sender,
        "role": role,
        "content": content,
        "is_urgent": is_urgent,
        "contact": {
            "contact_id": contact_id,
            "sender": sender,
            "role": role,
            "is_replyable": is_replyable_role(role),
            "is_urgent": is_urgent,
        },
        "message": {"speaker": "npc", "content": content},
        "reply_options": reply_options,
    }


# ==========================================
# M2-her message construction.
# ==========================================

def _build_m2her_messages(
    character: Dict[str, Any],
    player_stats: dict,
    context: str,
) -> List[Dict[str, Any]]:
    """
    Map one character-library entry to MiniMax M2-her structured messages.

    Uses M2-her-specific roles:
        system: NPC persona.
        user_system: Player identity and state.
        group: Scene and background.
        sample_message_ai / sample_message_user: Conversation examples.
    """
    char_name = character.get("name", "未知")
    char_content = character.get("content", "")
    examples = character.get("examples", [])

    username = safe_username_for_prompt(player_stats.get("username", "同学"))
    major = player_stats.get("major", "未知专业")
    semester = player_stats.get("semester", "大一秋冬")
    stress = _stat_value(player_stats, "stress")
    sanity = _stat_value(player_stats, "sanity")
    charm = _stat_value(player_stats, "charm")
    stress_ratio = _stat_ratio(stress, "stress")
    sanity_ratio = _stat_ratio(sanity, "sanity")
    charm_ratio = _stat_ratio(charm, "charm")
    charm_label = stat_definitions.by_id["charm"].label

    messages = []

    # system: NPC persona.
    messages.append({
        "role": "system",
        "content": f"你当前扮演：{char_name}。\n{char_content}",
    })

    # user_system: player identity and current state.
    player_desc = (
        f"你是一位浙江大学{major}专业的学生，名叫{username}，"
        f"目前处于{semester}，{charm_label}值约为{charm}。"
    )
    if stress_ratio > 0.35:
        player_desc += "你最近压力很大，看起来很疲惫。"
    elif sanity_ratio < 0.15:
        player_desc += "你最近心态不太好，情绪低落。"
    if charm_ratio >= 0.6:
        player_desc += "你在人际互动中很有亲和力。"
    elif charm_ratio <= 0.1:
        player_desc += "你最近在社交表达上稍显拘谨。"

    messages.append({
        "role": "user_system",
        "content": player_desc,
    })

    # group: scene and situational framing.
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

    # sample_message_*: examples from the character library.
    sample_examples = examples[:3] if len(examples) > 3 else examples
    for i, example in enumerate(sample_examples):
        messages.append({
            "role": "sample_message_ai",
            "content": example,
        })
        # Interleave short player replies so examples read like a dialogue.
        if i < len(sample_examples) - 1:
            messages.append({
                "role": "sample_message_user",
                "content": random.choice(["好的收到", "了解~", "嗯嗯", "OK"]),
            })

    # user: trigger the assistant to produce the next DingTalk message.
    messages.append({
        "role": "user",
        "content": f"（{username}打开了钉钉，看到一条新消息）",
    })

    return messages


# ==========================================
# API calls.
# ==========================================

async def _call_m2her_api(
    messages: List[Dict],
    max_completion_tokens: int = 200,
    llm_override: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """Call MiniMax M2-her through the OpenAI-compatible SDK surface."""
    api_key, model, base_url = _resolve_m2her_config(llm_override)
    payload_messages = _sanitize_m2her_messages(messages)

    if not api_key or not payload_messages:
        return None

    client: AsyncOpenAI | None = None
    should_close_client = _has_custom_m2her_api_key(llm_override)
    try:
        client = (
            AsyncOpenAI(api_key=api_key, base_url=base_url, timeout=15.0)
            if should_close_client
            else await _get_m2her_client(api_key, base_url)
        )
        response = await client.chat.completions.create(
            model=model,
            messages=cast(Any, payload_messages),
            temperature=1.0,
            top_p=0.95,
            max_completion_tokens=max_completion_tokens,
        )
        choices = response.choices or []
        if choices:
            content = choices[0].message.content
            return content.strip() if isinstance(content, str) else None

        return None

    except APITimeoutError:
        logger.warning("M2-her API timeout")
        return None
    except OpenAIError as e:
        logger.warning("M2-her API error: %s", e)
        return None
    except Exception as e:
        logger.error("M2-her API call failed: %s", e)
        return None
    finally:
        if should_close_client and client is not None:
            await client.close()


def _normalize_m2her_base_url(base_url: str | None) -> str:
    """Return an OpenAI SDK base URL, tolerating older full endpoint config."""
    normalized = (base_url or _DEFAULT_M2HER_BASE_URL).strip().rstrip("/")
    for suffix in ("/chat/completions", "/text/chatcompletion_v2"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)].rstrip("/")
    return normalized or _DEFAULT_M2HER_BASE_URL


def _config_str(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _override_str(llm_override: Optional[dict[str, Any]], key: str) -> str:
    if not isinstance(llm_override, dict):
        return ""
    return _config_str(llm_override.get(key))


def _has_custom_m2her_api_key(llm_override: Optional[dict[str, Any]]) -> bool:
    return bool(_override_str(llm_override, "api_key"))


def _resolve_m2her_config(
    llm_override: Optional[dict[str, Any]] = None,
) -> tuple[str, str, str]:
    api_key = _override_str(llm_override, "api_key") or _config_str(
        getattr(settings, "MINIMAX_API_KEY", "")
    )
    model = _override_str(llm_override, "model") or _config_str(
        getattr(settings, "MINIMAX_MODEL", "M2-her")
    ) or "M2-her"
    base_url = _normalize_m2her_base_url(
        _override_str(llm_override, "base_url")
        or _config_str(getattr(settings, "MINIMAX_BASE_URL", ""))
    )
    return api_key, model, base_url


async def _get_m2her_client(api_key: str, base_url: str) -> AsyncOpenAI:
    client_config = (api_key, base_url)
    client = _M2HER_CLIENTS.get(client_config)
    if client is None:
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=15.0,
        )
        _M2HER_CLIENTS[client_config] = client
    return client


async def close_m2her_client() -> None:
    """Close cached platform MiniMax clients during application shutdown."""
    for client in list(_M2HER_CLIENTS.values()):
        await client.close()
    _M2HER_CLIENTS.clear()


# ==========================================
# Vectorized character selection.
# ==========================================


async def _select_characters_vectorized(
    player_stats: dict,
    context: str,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """
    Select matching characters by pgvector cosine similarity.

    Uses precomputed context query vectors and performs no runtime embedding
    inference while retrieving Top-K matches from `character_embeddings`.

    Returns:
        Character dictionaries, or an empty list for caller fallback.
    """
    try:
        from app.content.vector_store import search_similar_characters
    except ImportError:
        logger.debug("vector_store not available, skipping vectorized selection")
        return []

    try:
        results = await search_similar_characters(context, top_k=top_k)
        if results:
            chars = [r["char"] for r in results]
            logger.info(
                "Vector search selected %d characters: %s (context=%s)",
                len(chars),
                [c.get("name", "?") for c in chars],
                context,
            )
            return chars
    except Exception as e:
        logger.warning("Vector search failed, will fallback: %s", e)

    return []


# ==========================================
# Public generation entry point.
# ==========================================

async def generate_dingtalk_via_m2her(
    player_stats: dict,
    context: str = "random",
    llm_override: Optional[dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Generate one role-play DingTalk message through M2-her.

    Returns:
        A DingTalk payload dictionary, or None so the caller can fall back.
    """
    # Missing credentials mean the engine should use its fallback generator.
    api_key, _, _ = _resolve_m2her_config(llm_override)
    if not api_key:
        return None

    use_shared_cache = llm_override is None
    # Shared cache is only safe for the platform key, not user RP keys.
    if use_shared_cache:
        cached = await RedisCache.lpop(_CACHE_KEY)
        if cached:
            try:
                cached_data = json.loads(cached) if isinstance(cached, str) else cached
                return cached_data if isinstance(cached_data, dict) else None
            except (json.JSONDecodeError, TypeError):
                pass

    # Prefer vector-selected characters, then fall back to random sampling.
    unique_chars = await _select_characters_vectorized(player_stats, context)

    if not unique_chars:
        characters = _load_characters()
        if not characters:
            return None
        unique_chars = random.sample(characters, min(3, len(characters)))

    # Generate multiple candidate messages concurrently.
    import asyncio

    async def _generate_one(char: Dict) -> Optional[Dict[str, Any]]:
        return await generate_dingtalk_for_character_via_m2her(
            char,
            player_stats,
            context,
            llm_override=llm_override,
        )

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

    # Return the first candidate and cache the rest for platform-key sessions.
    current_msg = valid_results[0]
    remaining = [json.dumps(m, ensure_ascii=False) for m in valid_results[1:]]

    if use_shared_cache and remaining:
        await RedisCache.rpush_many_with_limit(
            _CACHE_KEY,
            remaining,
            max_len=_CACHE_MAX_LEN,
            ttl_seconds=_CACHE_TTL_SECONDS,
        )

    return current_msg


async def generate_dingtalk_reply_via_m2her(
    character: Dict[str, Any],
    player_stats: dict,
    history: list[dict[str, Any]],
    player_reply: str,
    reply_count: int,
    llm_override: Optional[dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Generate an NPC reply and settle the round after the third player reply."""
    api_key, _, _ = _resolve_m2her_config(llm_override)
    if not api_key:
        return None

    sender = str(character.get("name") or "未知")
    role = normalize_dingtalk_role(str(character.get("role") or "unknown"))
    if not is_replyable_role(role):
        return None

    history_lines = []
    for msg in history[-8:]:
        speaker = "玩家" if msg.get("speaker") == "player" else sender
        content = str(msg.get("content") or "").strip()
        if content:
            history_lines.append(f"{speaker}: {content}")
    history_text = "\n".join(history_lines)
    should_settle = reply_count >= 3

    messages = _build_m2her_messages(character, player_stats, "random")
    if should_settle:
        request = (
            "以下是当前私聊历史：\n"
            f"{history_text}\n玩家刚回复：{player_reply}\n"
            "请生成 NPC 的下一条回复，并对这一轮三次往返对话"
            "产生的游戏数值影响做轻量结算。"
            f"影响只能包含 {_allowed_effect_fields_prompt()}，"
            "数值为整数，幅度要克制。"
            '严格返回 JSON：{"npc_reply":"...",'
            '"settlement":{"desc":"...","effects":{"sanity":1}}}'
        )
    else:
        request = (
            "以下是当前私聊历史：\n"
            f"{history_text}\n玩家刚回复：{player_reply}\n"
            "请生成 NPC 的下一条回复，并为玩家生成 2-3 个后续回复选项。"
            '严格返回 JSON：{"npc_reply":"...","reply_options":["选项1","选项2"]}'
        )

    messages.append({"role": "user", "content": request})
    raw = await _call_m2her_api(
        messages, max_completion_tokens=420, llm_override=llm_override
    )
    if not raw:
        return None

    data = _json_from_text(raw)
    npc_reply = str(data.get("npc_reply") or raw).strip()
    if not npc_reply:
        return None

    result: Dict[str, Any] = {"content": npc_reply[:500]}
    if should_settle:
        settlement = data.get("settlement")
        result["settlement"] = settlement if isinstance(settlement, dict) else None
    else:
        result["reply_options"] = _coerce_reply_options(
            data.get("reply_options"), role
        )
    return result
