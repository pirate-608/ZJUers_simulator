import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

from app.api.cache import RedisCache
from app.content.state_vector import PlayerStateVector
from app.core.input_safety import safe_username_for_prompt

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


def _resolve_llm_config(
    llm_override: Optional[Dict[str, Any]] = None,
) -> Tuple[str | None, str | None, str]:
    """根据用户配置或环境变量确定 LLM 配置"""
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


def _get_client(api_key: Optional[str], base_url: Optional[str]) -> AsyncOpenAI:
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


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
    """探测 LLM API 是否可用（轻量调用，不消耗 token）"""
    try:
        api_key, base_url, _model = _resolve_llm_config(llm_override)
        if not api_key:
            return False
        client = _get_client(api_key, base_url)
        await client.models.list()
        return True
    except Exception as e:
        logger.warning(f"LLM availability check failed: {e}")
        return False


CC98_CACHE_MAX_LEN = 200
CC98_CACHE_TTL_SECONDS = 6 * 60 * 60
EVENTS_CACHE_MAX_LEN = 100
EVENTS_CACHE_TTL_SECONDS = 12 * 60 * 60
DINGTALK_CACHE_MAX_LEN = 200
DINGTALK_CACHE_TTL_SECONDS = 6 * 60 * 60
_KEYWORDS_CACHE_LOADED = False
_KEYWORDS_CACHE: list[Any] = []


def _load_keywords():
    """加载 world/keywords.json 供 LLM 提示词使用"""
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
    """生成 CC98 帖子内容和反馈（批量缓存优化版）"""
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

    # 1. 优先从 Redis 队列获取（库存消耗）
    cc98_key = "cc98:posts"
    post_content = await RedisCache.lpop(cc98_key)
    if post_content:
        # 队列里有货，直接返回，不再存回去（避免重复）
        return post_content, feedback

    # 2. LLM 补货 (状态浓缩: ~50 tok 代替 ~300 tok)
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
        llm_client = _get_client(api_key, base_url)

        response = await llm_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=300,
        )

        data = _json_from_text(response.choices[0].message.content)
        posts = _string_list(data.get("posts"))

        if not posts:
            return "CC98 现在只有烂坑和吐槽...", feedback

        # 3. 分配货源
        current_post = posts[0]  # 第一条直接给用户
        remaining_posts = posts[1:]  # 剩下的存入仓库

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


async def generate_random_event(
    player_stats: dict,
    history: list | None = None,
    llm_override: Optional[Dict[str, Any]] = None,
):  # [修复] 增加了 history 参数
    """
    生成随机事件（批量缓存版）
    """
    event_key = "game:events_pool"

    # 1. 尝试从缓存获取
    cached_event = await RedisCache.lpop(event_key)
    if cached_event:
        return _coerce_cached_json(cached_event)

    # 2. LLM 补货 (状态浓缩: ~50 tok 代替 ~300 tok + keywords ~800 tok)
    state = PlayerStateVector.from_stats(player_stats)
    messages: List[Any] = []
    history_hint = ""
    if history:
        history_hint = f"\n已发生事件（勿重复）：{', '.join(history[-5:])}"
    prompt = (
        f"玩家状态：{state.to_prompt_fragment()}{history_hint}\n"
        f"生成 3 个浙大校园随机事件，风格迥异。\n"
        f"每个事件含两个选项，effects 范围 -10~+10。\n"
        f'\n严格 JSON：{{ "events": [{{ "title": "...", "desc": "...", '
        f'"options": [{{"id": "A", "text": "...", '
        f'"effects": {{"energy": -5, "desc": "..."}}}}, '
        f'{{"id": "B", "text": "...", '
        f'"effects": {{"sanity": 5, "desc": "..."}}}}] }}] }}'
    )
    messages.append({"role": "user", "content": prompt})
    try:
        api_key, base_url, model = _resolve_llm_config(llm_override)
        llm_client = _get_client(api_key, base_url)

        response = await llm_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=800,
        )
        data = _json_from_text(response.choices[0].message.content)
        events = _dict_list(data.get("events"))

        if not events:
            return None

        # 分配：第一条直接用，剩下的存入 Redis
        current_event = events[0]
        remaining_events = [json.dumps(e, ensure_ascii=False) for e in events[1:]]
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


async def generate_dingtalk_message(
    player_stats: dict,
    context: str = "random",
    llm_override: Optional[Dict[str, Any]] = None,
):
    """
    生成钉钉消息（批量缓存版）
    """
    msg_key = f"game:dingtalk_pool:{context}"  # 根据上下文分类缓存

    # 1. 尝试从缓存获取
    cached_msg = await RedisCache.lpop(msg_key)
    if cached_msg:
        return _coerce_cached_json(cached_msg)

    # 2. LLM 补货 (状态浓缩: ~50 tok 代替 ~2300 tok)
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
        llm_client = _get_client(api_key, base_url)

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


async def generate_dingtalk_reply_message(
    character: Dict[str, Any],
    player_stats: dict,
    history: list[dict[str, Any]],
    player_reply: str,
    reply_count: int,
    llm_override: Optional[Dict[str, Any]] = None,
) -> dict[str, Any] | None:
    """用通用 OpenAI-compatible LLM 生成钉钉私聊回复。"""
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
            f"心态 {player_stats.get('sanity', '--')}，"
            f"压力 {player_stats.get('stress', '--')}，"
            f"GPA {player_stats.get('gpa', '--')}。"
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
                "effects 只能包含 energy/sanity/stress/eq/luck/reputation/gold，"
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

        llm_client = _get_client(api_key, base_url)
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


async def generate_wenyan_report(
    final_stats: dict, llm_override: Optional[Dict[str, Any]] = None
) -> str:
    """
    根据玩家final_stats生成一段文言文风格的结业总结。
    """
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

    prompt = f"""
    玩家数据：{json.dumps(safe_stats, ensure_ascii=False)}
    你是一位古风文案大师。请根据以上玩家的折姜大学结业数据，为其撰写一段100字左右的文言文结业总结，内容需涵盖其专业、能力、GPA、性格、成就等主要信息，风格典雅、用词考究，严肃中不失诙谐风趣，结尾可有调侃或祝福。
    只需返回文言文内容本身，不要任何解释。
    """
    messages.append({"role": "user", "content": prompt})
    try:
        api_key, base_url, model = _resolve_llm_config(llm_override)
        llm_client = _get_client(api_key, base_url)

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
