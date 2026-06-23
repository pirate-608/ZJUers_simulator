"""General OpenAI-compatible LLM helpers for game content generation.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The functions here generate random events, CC98 posts, and non-RP DingTalk
fallbacks while preserving deterministic library-mode fallbacks.
"""

import inspect
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from app.api.cache import RedisCache
from app.content.state_vector import PlayerStateVector
from app.core.input_safety import safe_username_for_prompt
from app.game.stat_definitions import stat_definitions
from app.schemas.dingtalk import (
    build_contact_id,
    is_replyable_role,
    normalize_dingtalk_role,
)

logger = logging.getLogger(__name__)


PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "moonshot": "https://api.moonshot.cn/v1",
    "minimax": "https://api.minimaxi.com/v1",
}

DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_LLM_TIMEOUT_SECONDS = 20.0
_DEFAULT_LLM_CLIENTS: dict[tuple[str | None, str | None], AsyncOpenAI] = {}


def _allowed_effect_fields_prompt() -> str:
    return "/".join(sorted(stat_definitions.event_effect_fields))


def _stat_label(stat_id: str) -> str:
    definition = stat_definitions.by_id.get(stat_id)
    return definition.label if definition else stat_id


def _resolve_llm_config(
    llm_override: Optional[Dict[str, Any]] = None,
) -> Tuple[str | None, str | None, str]:
    """Resolve model credentials from player override or environment settings."""
    override = llm_override or {}
    model = str(override.get("model") or os.getenv("LLM") or DEFAULT_LLM_MODEL)
    api_key_value = override.get("api_key") or os.getenv("LLM_API_KEY")
    api_key = str(api_key_value) if api_key_value else None

    provider = override.get("provider")
    if provider and provider in PROVIDER_BASE_URLS:
        base_url = PROVIDER_BASE_URLS[provider]
    else:
        base_url = os.getenv("LLM_BASE_URL")

    return api_key, base_url, model


def _get_client(
    api_key: Optional[str], base_url: Optional[str], *, cache: bool = False
) -> AsyncOpenAI:
    """Return an OpenAI-compatible async client with explicit timeout.

    Platform-default clients are safe to reuse across requests. Player-provided
    overrides are session-sensitive and should be closed after the single call
    that needed them, so callers pass `cache=False` for overrides.
    """
    if cache:
        key = (api_key, base_url)
        if key not in _DEFAULT_LLM_CLIENTS:
            _DEFAULT_LLM_CLIENTS[key] = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                timeout=DEFAULT_LLM_TIMEOUT_SECONDS,
            )
        return _DEFAULT_LLM_CLIENTS[key]
    return AsyncOpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=DEFAULT_LLM_TIMEOUT_SECONDS,
    )


async def _close_client_if_uncached(client: Any, *, cache: bool) -> None:
    """Close session-scoped clients without assuming concrete SDK types."""
    if cache:
        return
    close = getattr(client, "close", None)
    if close is None:
        return
    result = close()
    if inspect.isawaitable(result):
        await result


async def close_llm_clients() -> None:
    """Close cached platform-default LLM clients during process shutdown."""
    clients = list(_DEFAULT_LLM_CLIENTS.values())
    _DEFAULT_LLM_CLIENTS.clear()
    for client in clients:
        close = getattr(client, "close", None)
        if close is None:
            continue
        result = close()
        if inspect.isawaitable(result):
            await result


def _use_global_content_cache(llm_override: Optional[Dict[str, Any]]) -> bool:
    """Return whether generated content may use the shared Redis content pool."""
    return llm_override is None


def _json_from_text(content: object) -> dict[str, Any]:
    if not isinstance(content, str) or not content.strip():
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


def _coerce_cached_json(content: object) -> dict[str, Any] | None:
    if isinstance(content, dict):
        return content
    return _json_from_text(content) or None


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _dict_list(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


async def check_llm_availability(llm_override: Optional[Dict[str, Any]] = None) -> bool:
    """Probe whether the configured OpenAI-compatible endpoint is reachable."""
    client = None
    cache_client = _use_global_content_cache(llm_override)
    try:
        api_key, base_url, _model = _resolve_llm_config(llm_override)
        if not api_key:
            return False
        client = _get_client(api_key, base_url, cache=cache_client)
        await client.models.list()
        return True
    except Exception as e:
        logger.warning(f"LLM availability check failed: {e}")
        return False
    finally:
        if client is not None:
            await _close_client_if_uncached(client, cache=cache_client)


CC98_CACHE_MAX_LEN = 200
CC98_CACHE_TTL_SECONDS = 6 * 60 * 60
EVENTS_CACHE_MAX_LEN = 100
EVENTS_CACHE_TTL_SECONDS = 12 * 60 * 60
DINGTALK_CACHE_MAX_LEN = 200
DINGTALK_CACHE_TTL_SECONDS = 6 * 60 * 60
_KEYWORDS_CACHE_LOADED = False
_KEYWORDS_CACHE: list[Any] = []


def _load_keywords():
    """Load `world/keywords.json` for prompt grounding."""
    global _KEYWORDS_CACHE_LOADED, _KEYWORDS_CACHE
    if _KEYWORDS_CACHE_LOADED:
        return _KEYWORDS_CACHE

    from pathlib import Path

    base_dir = Path(__file__).resolve().parent.parent.parent
    kw_path = (
        Path("/app/world/keywords.json")
        if Path("/app/world/keywords.json").exists()
        else base_dir / "world" / "keywords.json"
    )
    try:
        with open(kw_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        _KEYWORDS_CACHE = data if isinstance(data, list) else []
    except Exception:
        _KEYWORDS_CACHE = []
    _KEYWORDS_CACHE_LOADED = True
    return _KEYWORDS_CACHE


async def generate_cc98_post(
    player_stats: dict,
    effect: str,
    trigger: str,
    llm_override: Optional[Dict[str, Any]] = None,
):
    """Generate a CC98 post and feedback with Redis-backed batch caching."""
    feedback_map = {
        "positive": [
            "你刷到了一个{trigger}，心态+5",
            "你看到{trigger}，忍不住笑出声，心态+5",
        ],
        "neutral": [
            "你觉得有点无聊，停止了水贴。",
            "你刷到{trigger}，但没什么感觉，继续划水。",
        ],
        "negative": [
            "你点进了一个{trigger}的帖子，太不求是，你被暴击，心态-5",
            "你刷到了一个烂坑，人与人的悲欢并不相通，你只觉得吵闹，心态-5",
            "你看的快抑郁了，心态-5",
        ],
    }
    import random as _random

    feedback = _random.choice(feedback_map[effect]).format(trigger=trigger)

    # Consume from the Redis pool first so cached content is not duplicated.
    use_cache = _use_global_content_cache(llm_override)
    cc98_key = "cc98:posts"
    if use_cache:
        post_content = await RedisCache.lpop(cc98_key)
        if post_content:
            return post_content, feedback

    # Refill the pool with compact state context to keep token usage bounded.
    state = PlayerStateVector.from_stats(player_stats)
    messages: List[Any] = []
    prompt = (
        f"玩家状态：{state.to_prompt_fragment()}\n"
        f"模拟浙江大学CC98论坛，生成 5 条帖子。\n"
        f'1. 第一条与"{trigger}"相关（{effect}效果）。\n'
        f"2. 其余 4 条随机校园话题。\n"
        f'\n严格输出 JSON：{{ "posts": ["帖1", "帖2", "帖3", "帖4", "帖5"] }}'
    )
    messages.append({"role": "user", "content": prompt})

    try:
        api_key, base_url, model = _resolve_llm_config(llm_override)
        llm_client = _get_client(api_key, base_url, cache=use_cache)

        response = await llm_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=300,
        )

        data = _json_from_text(response.choices[0].message.content)
        posts = _string_list(data.get("posts"))

        if not posts:
            return "CC98 现在只有烂坑和吐槽...", feedback

        current_post = posts[0]
        remaining_posts = posts[1:]

        if use_cache:
            await RedisCache.rpush_many_with_limit(
                cc98_key,
                remaining_posts,
                max_len=CC98_CACHE_MAX_LEN,
                ttl_seconds=CC98_CACHE_TTL_SECONDS,
            )

        return current_post, feedback

    except Exception as e:
        print(f"[LLM Error] {e}")
        return "CC98 服务器维护中...", feedback
    finally:
        if "llm_client" in locals():
            await _close_client_if_uncached(llm_client, cache=use_cache)


async def generate_random_event(
    player_stats: dict,
    history: list | None = None,
    llm_override: Optional[Dict[str, Any]] = None,
) -> dict[str, Any] | None:
    """Generate a random event with Redis-backed batch caching."""
    use_cache = _use_global_content_cache(llm_override)
    event_key = "game:events_pool"

    # Use the cached pool before paying for another LLM batch.
    if use_cache:
        cached_event = await RedisCache.lpop(event_key)
        if cached_event:
            return _coerce_cached_json(cached_event)

    # Compact player state and recent history keep the generation prompt small.
    state = PlayerStateVector.from_stats(player_stats)
    messages: List[Any] = []
    history_hint = ""
    if history:
        history_hint = f"\n已发生事件（勿重复）：{', '.join(history[-5:])}"
    prompt = (
        f"玩家状态：{state.to_prompt_fragment()}{history_hint}\n"
        f"生成 3 个浙大校园随机事件，风格迥异。\n"
        f"每个事件含两个选项，effects 范围 -10~+10，"
        f"可包含 {_allowed_effect_fields_prompt()}。\n"
        f'\n严格 JSON：{{ "events": [{{ "title": "...", "desc": "...", '
        f'"options": [{{"id": "A", "text": "...", '
        f'"effects": {{"energy": -5, "desc": "..."}}}}, '
        f'{{"id": "B", "text": "...", '
        f'"effects": {{"sanity": 5, "desc": "..."}}}}] }}] }}'
    )
    messages.append({"role": "user", "content": prompt})
    try:
        api_key, base_url, model = _resolve_llm_config(llm_override)
        llm_client = _get_client(api_key, base_url, cache=use_cache)

        response = await llm_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=800,
        )
        data = _json_from_text(response.choices[0].message.content)
        events = _dict_list(data.get("events"))

        if not events:
            return None

        current_event = events[0]
        remaining_events = [json.dumps(e, ensure_ascii=False) for e in events[1:]]
        if use_cache:
            await RedisCache.rpush_many_with_limit(
                event_key,
                remaining_events,
                max_len=EVENTS_CACHE_MAX_LEN,
                ttl_seconds=EVENTS_CACHE_TTL_SECONDS,
            )

        return current_event
    except Exception as e:
        print(f"[LLM Event Error] {e}")
        return None
    finally:
        if "llm_client" in locals():
            await _close_client_if_uncached(llm_client, cache=use_cache)


async def generate_dingtalk_message(
    player_stats: dict,
    context: str = "random",
    llm_override: Optional[Dict[str, Any]] = None,
):
    """Generate a DingTalk message with context-scoped Redis batch caching."""
    use_cache = _use_global_content_cache(llm_override)
    msg_key = f"game:dingtalk_pool:{context}"

    # Use a context-scoped cached pool before generating a new batch.
    if use_cache:
        cached_msg = await RedisCache.lpop(msg_key)
        if cached_msg:
            return _coerce_cached_json(cached_msg)

    # Compact state context avoids shipping the full game snapshot to the model.
    state = PlayerStateVector.from_stats(player_stats)
    request_messages: List[Any] = []
    prompt = (
        f"玩家状态：{state.to_prompt_fragment()}\n"
        f"场景：{context}。\n"
        f"模拟浙江大学钉钉消息，生成 5 条（通知/约饭/求助/催作业），发送人身份各异。\n"
        f'\n严格 JSON：{{ "messages": ['
        f'{{ "sender": "发送人", "role": "counselor/student/system/teacher", '
        f'"content": "30字内", "is_urgent": false }}] }}'
    )
    request_messages.append({"role": "user", "content": prompt})
    try:
        api_key, base_url, model = _resolve_llm_config(llm_override)
        llm_client = _get_client(api_key, base_url, cache=use_cache)

        response = await llm_client.chat.completions.create(
            model=model,
            messages=request_messages,
            max_tokens=500,
        )
        data = _json_from_text(response.choices[0].message.content)
        generated_messages = _dict_list(data.get("messages"))

        if not generated_messages:
            return None

        current_msg = generated_messages[0]
        remaining_msgs = [
            json.dumps(m, ensure_ascii=False) for m in generated_messages[1:]
        ]
        if use_cache:
            await RedisCache.rpush_many_with_limit(
                msg_key,
                remaining_msgs,
                max_len=DINGTALK_CACHE_MAX_LEN,
                ttl_seconds=DINGTALK_CACHE_TTL_SECONDS,
            )

        return current_msg
    except Exception as e:
        print(f"[LLM DingTalk Error] {e}")
        return None
    finally:
        if "llm_client" in locals():
            await _close_client_if_uncached(llm_client, cache=use_cache)


async def generate_dingtalk_message_for_character(
    character: Dict[str, Any],
    player_stats: dict,
    context: str = "random",
    llm_override: Optional[Dict[str, Any]] = None,
) -> dict[str, Any] | None:
    """Generate one opening DingTalk message for a specific character."""
    use_cache = _use_global_content_cache(llm_override)
    llm_client = None
    try:
        api_key, base_url, model = _resolve_llm_config(llm_override)
        if not api_key:
            return None

        sender = str(character.get("name") or character.get("sender") or "对方")
        role = normalize_dingtalk_role(str(character.get("role") or "unknown"))
        persona = str(character.get("content") or f"你是{sender}。")
        examples = character.get("examples")
        example_hint = ""
        if isinstance(examples, list) and examples:
            example_hint = "角色说话示例：" + " / ".join(str(x) for x in examples[:3])

        state = PlayerStateVector.from_stats(player_stats)
        prompt = (
            "你正在模拟浙江大学校园钉钉私聊。\n"
            f"玩家状态：{state.to_prompt_fragment()}\n"
            f"场景：{context}。\n"
            f"NPC：{sender}，角色类型：{role}。\n"
            f"NPC人设：{persona}\n"
            f"{example_hint}\n"
            "请生成这个 NPC 主动发给玩家的一条自然私聊消息，30 字内。"
            '严格返回 JSON：{"content":"...",'
            '"reply_options":["选项1","选项2","选项3"]}。'
            "只有可回复角色需要 reply_options；不可回复角色可返回空数组。"
        )

        llm_client = _get_client(api_key, base_url, cache=use_cache)
        response = await llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=320,
        )
        raw = response.choices[0].message.content
        data = _json_from_text(raw)
        content = str(
            data.get("content") or data.get("message") or data.get("npc_reply") or raw
        ).strip()
        if not content:
            return None

        reply_options = [
            {"option_id": f"opt_{idx + 1}", "text": text[:80]}
            for idx, text in enumerate(_string_list(data.get("reply_options"))[:3])
        ]
        if not is_replyable_role(role):
            reply_options = []

        contact_id = build_contact_id(sender, role)
        is_urgent = role in ("counselor", "system", "teacher")
        return {
            "sender": sender,
            "role": role,
            "content": content[:500],
            "is_urgent": is_urgent,
            "contact": {
                "contact_id": contact_id,
                "sender": sender,
                "role": role,
                "is_replyable": is_replyable_role(role),
                "is_urgent": is_urgent,
            },
            "message": {"speaker": "npc", "content": content[:500]},
            "reply_options": reply_options,
        }
    except Exception as e:
        logger.warning("Generic DingTalk opening generation failed: %s", e)
        return None
    finally:
        if llm_client is not None:
            await _close_client_if_uncached(llm_client, cache=use_cache)


async def generate_dingtalk_reply_message(
    character: Dict[str, Any],
    player_stats: dict,
    history: list[dict[str, Any]],
    player_reply: str,
    reply_count: int,
    llm_override: Optional[Dict[str, Any]] = None,
) -> dict[str, Any] | None:
    """Generate a DingTalk private-chat reply with the generic LLM."""
    use_cache = _use_global_content_cache(llm_override)
    llm_client = None
    try:
        api_key, base_url, model = _resolve_llm_config(llm_override)
        if not api_key:
            return None

        sender = str(character.get("name") or character.get("sender") or "对方")
        role = str(character.get("role") or "unknown")
        persona = str(character.get("content") or f"你是{sender}。")
        examples = character.get("examples")
        example_hint = ""
        if isinstance(examples, list) and examples:
            example_hint = "角色说话示例：" + " / ".join(str(x) for x in examples[:3])

        username = safe_username_for_prompt(player_stats.get("username") or "同学")
        major = str(player_stats.get("major") or "未知专业")
        semester = str(player_stats.get("semester") or "当前学期")
        stats_hint = (
            f"玩家：{username}，{major}，{semester}。"
            f"{_stat_label('sanity')} {player_stats.get('sanity', '--')}，"
            f"{_stat_label('stress')} {player_stats.get('stress', '--')}，"
            f"GPA {player_stats.get('gpa', '--')}，"
            f"{_stat_label('charm')} {player_stats.get('charm', '--')}。"
        )

        history_lines = []
        for msg in history[-8:]:
            speaker = "玩家" if msg.get("speaker") == "player" else sender
            text = str(msg.get("content") or "").strip()
            if text:
                history_lines.append(f"{speaker}: {text}")
        history_text = "\n".join(history_lines) or "暂无历史。"
        should_settle = reply_count >= 3

        if should_settle:
            output_contract = (
                '严格返回 JSON：{"npc_reply":"...",'
                '"settlement":{"desc":"...","effects":{"sanity":1}}}。'
                f"effects 只能包含 {_allowed_effect_fields_prompt()}，"
                "整数幅度要克制，通常在 -3 到 3。"
            )
        else:
            output_contract = (
                '严格返回 JSON：{"npc_reply":"...",'
                '"reply_options":["选项1","选项2","选项3"]}。'
                "回复选项要像玩家会点的短句，2-3 个。"
            )

        prompt = (
            "你正在模拟浙江大学校园钉钉私聊。\n"
            f"NPC：{sender}，角色类型：{role}。\n"
            f"NPC人设：{persona}\n"
            f"{example_hint}\n"
            f"{stats_hint}\n"
            f"当前私聊历史：\n{history_text}\n"
            f"玩家刚选择回复：{player_reply}\n"
            "请保持自然、简短、有角色感，不要解释生成过程。\n"
            f"{output_contract}"
        )

        llm_client = _get_client(api_key, base_url, cache=use_cache)
        response = await llm_client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=420,
        )
        raw = response.choices[0].message.content
        data = _json_from_text(raw)
        npc_reply = str(data.get("npc_reply") or raw or "").strip()
        if not npc_reply:
            return None

        result: dict[str, Any] = {"content": npc_reply[:500]}
        if should_settle:
            settlement = data.get("settlement")
            result["settlement"] = settlement if isinstance(settlement, dict) else None
        else:
            options = _string_list(data.get("reply_options"))
            if options:
                result["reply_options"] = [
                    {"option_id": f"opt_{idx + 1}", "text": text[:80]}
                    for idx, text in enumerate(options[:3])
                ]
        return result
    except Exception as e:
        logger.warning("Generic DingTalk reply generation failed: %s", e)
        return None
    finally:
        if llm_client is not None:
            await _close_client_if_uncached(llm_client, cache=use_cache)


async def generate_wenyan_report(
    final_stats: dict, llm_override: Optional[Dict[str, Any]] = None
) -> str:
    """Generate a classical-Chinese-style graduation summary from final stats."""
    use_cache = _use_global_content_cache(llm_override)
    llm_client = None
    keywords = _load_keywords()
    messages: List[Any] = []
    if keywords:
        messages.append(
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(keywords, ensure_ascii=False),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        )
    safe_stats = dict(final_stats or {})
    if "username" in safe_stats:
        safe_stats["username"] = safe_username_for_prompt(safe_stats.get("username"))

    prompt = (
        f"玩家数据：{json.dumps(safe_stats, ensure_ascii=False)}\n"
        "你是一位古风文案大师。请根据以上玩家的折姜大学结业数据，"
        "为其撰写一段100字左右的文言文结业总结，内容需涵盖其专业、"
        "能力、GPA、性格、成就等主要信息，风格典雅、用词考究，"
        "严肃中不失诙谐风趣，结尾可有调侃或祝福。\n"
        "只需返回文言文内容本身，不要任何解释。"
    )
    messages.append({"role": "user", "content": prompt})
    try:
        api_key, base_url, model = _resolve_llm_config(llm_override)
        llm_client = _get_client(api_key, base_url, cache=use_cache)

        response = await llm_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=200,
        )
        content = response.choices[0].message.content
        if not isinstance(content, str) or not content.strip():
            return "学业既成，前程似锦。"
        return content.strip()
    except Exception as e:
        print(f"[LLM Wenyan Error] {e}")
        return "学业既成，前程似锦。"
    finally:
        if llm_client is not None:
            await _close_client_if_uncached(llm_client, cache=use_cache)
