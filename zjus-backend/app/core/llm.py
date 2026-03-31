import json
import os
import logging
from typing import Optional, Dict
from openai import AsyncOpenAI
from app.api.cache import RedisCache
from app.content.state_vector import PlayerStateVector

logger = logging.getLogger(__name__)


PROVIDER_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "glm": "https://open.bigmodel.cn/api/paas/v4",
    "moonshot": "https://api.moonshot.cn/v1",
    "minimax": "https://api.minimax.chat/v1",
}

def _resolve_llm_config(llm_override: Optional[Dict] = None):
    """根据用户配置或环境变量确定 LLM 配置"""
    model = (llm_override or {}).get("model") or os.getenv("LLM")
    api_key = (llm_override or {}).get("api_key") or os.getenv("LLM_API_KEY")
    
    provider = (llm_override or {}).get("provider")
    if provider and provider in PROVIDER_BASE_URLS:
        base_url = PROVIDER_BASE_URLS[provider]
    else:
        base_url = os.getenv("LLM_BASE_URL")
        
    return api_key, base_url, model


def _get_client(api_key: Optional[str], base_url: Optional[str]):
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


CC98_CACHE_MAX_LEN = 200
CC98_CACHE_TTL_SECONDS = 6 * 60 * 60
EVENTS_CACHE_MAX_LEN = 100
EVENTS_CACHE_TTL_SECONDS = 12 * 60 * 60
DINGTALK_CACHE_MAX_LEN = 200
DINGTALK_CACHE_TTL_SECONDS = 6 * 60 * 60


def _load_keywords():
    """加载 world/keywords.json 供 LLM 提示词使用"""
    from pathlib import Path

    base_dir = Path(__file__).resolve().parent.parent.parent
    kw_path = (
        Path("/app/world/keywords.json")
        if Path("/app/world/keywords.json").exists()
        else base_dir / "world" / "keywords.json"
    )
    try:
        with open(kw_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []



async def generate_cc98_post(
    player_stats: dict, effect: str, trigger: str, llm_override: Optional[Dict] = None
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
    messages = []
    prompt = (
        f"玩家状态：{state.to_prompt_fragment()}\n"
        f"模拟浙江大学CC98论坛，生成 5 条帖子。\n"
        f"1. 第一条与\"{trigger}\"相关（{effect}效果）。\n"
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

        data = json.loads(response.choices[0].message.content)
        posts = data.get("posts", [])

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
    player_stats: dict, history: list = None, llm_override: Optional[Dict] = None
):  # [修复] 增加了 history 参数
    """
    生成随机事件（批量缓存版）
    """
    event_key = "game:events_pool"

    # 1. 尝试从缓存获取
    cached_event = await RedisCache.lpop(event_key)
    if cached_event:
        return json.loads(cached_event)

    # 2. LLM 补货 (状态浓缩: ~50 tok 代替 ~300 tok + keywords ~800 tok)
    state = PlayerStateVector.from_stats(player_stats)
    messages = []
    history_hint = ""
    if history:
        history_hint = f"\n已发生事件（勿重复）：{', '.join(history[-5:])}"
    prompt = (
        f"玩家状态：{state.to_prompt_fragment()}{history_hint}\n"
        f"生成 3 个浙大校园随机事件，风格迥异。\n"
        f"每个事件含两个选项，effects 范围 -10~+10。\n"
        f'\n严格 JSON：{{ "events": [{{ "title": "...", "desc": "...", '
        f'"options": [{{"id": "A", "text": "...", "effects": {{"energy": -5, "desc": "..."}}}}, '
        f'{{"id": "B", "text": "...", "effects": {{"sanity": 5, "desc": "..."}}}}] }}] }}'
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
        data = json.loads(response.choices[0].message.content)
        events = data.get("events", [])

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
    player_stats: dict, context: str = "random", llm_override: Optional[Dict] = None
):
    """
    生成钉钉消息（批量缓存版）
    """
    msg_key = f"game:dingtalk_pool:{context}"  # 根据上下文分类缓存

    # 1. 尝试从缓存获取
    cached_msg = await RedisCache.lpop(msg_key)
    if cached_msg:
        return json.loads(cached_msg)

    # 2. LLM 补货 (状态浓缩: ~50 tok 代替 ~2300 tok)
    state = PlayerStateVector.from_stats(player_stats)
    messages = []
    prompt = (
        f"玩家状态：{state.to_prompt_fragment()}\n"
        f"场景：{context}。\n"
        f"模拟浙江大学钉钉消息，生成 5 条（通知/约饭/求助/催作业），发送人身份各异。\n"
        f'\n严格 JSON：{{ "messages": ['
        f'{{ "sender": "发送人", "role": "counselor/student/system/teacher", '
        f'"content": "30字内", "is_urgent": false }}] }}'
    )
    messages.append({"role": "user", "content": prompt})
    try:
        api_key, base_url, model = _resolve_llm_config(llm_override)
        llm_client = _get_client(api_key, base_url)

        response = await llm_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=500,
        )
        data = json.loads(response.choices[0].message.content)
        messages = data.get("messages", [])

        if not messages:
            return None

        current_msg = messages[0]
        remaining_msgs = [json.dumps(m, ensure_ascii=False) for m in messages[1:]]
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


async def generate_wenyan_report(
    final_stats: dict, llm_override: Optional[Dict] = None
) -> str:
    """
    根据玩家final_stats生成一段文言文风格的结业总结。
    """
    keywords = _load_keywords()
    messages = []
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
    prompt = f"""
    玩家数据：{json.dumps(final_stats, ensure_ascii=False)}
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
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM Wenyan Error] {e}")
        return "学业既成，前程似锦。"
