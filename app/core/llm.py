import json
import os
from openai import AsyncOpenAI
from app.core.config import settings
from app.api.cache import RedisCache

# 初始化客户端 (适配 OpenAI 或 兼容接口如 DeepSeek/Moonshot)
# 如果是其他模型，请修改 base_url
client = AsyncOpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") 
)

async def generate_cc98_post(player_stats: dict, effect: str, trigger: str):
    """生成 CC98 帖子内容和反馈"""
    feedback_map = {
        "positive": [
            "你刷到了一个{trigger}，心态+5",
            "你看到{trigger}，忍不住笑出声，心态+5"
        ],
        "neutral": [
            "你觉得有点无聊，停止了水贴。",
            "你刷到{trigger}，但没什么感觉，继续划水。"
        ],
        "negative": [
            "你点进了一个{trigger}的帖子，太不求是，你被暴击，心态-5",
            "你刷到了一个烂坑，人与人的悲欢并不相通，你只觉得吵闹，心态-5",
            "你看的快抑郁了，心态-5"
        ]
    }
    import random as _random
    feedback = _random.choice(feedback_map[effect]).format(trigger=trigger)
    # 1. 优先从 Redis 队列获取
    cc98_key = "cc98:posts"
    post_content = await RedisCache.lpop(cc98_key)
    if post_content:
        return post_content, feedback
    # 2. 队列为空，实时生成
    prompt = f"""
    玩家当前状态：{player_stats}
    你正在模拟浙江大学CC98论坛的帖子。
    主题类型：{trigger}
    效果类型：{effect}
    请生成一个简短、有趣、符合大学生网络用语的帖子标题和内容。
    只返回内容本身，不要带任何解释。
    """
    try:
        response = await client.chat.completions.create(
            model=os.getenv("LLM"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        post_content = response.choices[0].message.content.strip()
        # 实时生成的内容补充回队列，便于后续复用
        await RedisCache.rpush(cc98_key, post_content)
        return post_content, feedback
    except Exception as e:
        print(f"[LLM Error] {e}")
        return "CC98 服务器维护中...", feedback

async def generate_random_event(player_stats: dict):
    """
    生成随机事件，要求返回 JSON 格式以便前端渲染选项
    """
    prompt = f"""
    你是一个文字模拟游戏的上帝系统。玩家是浙大学生，当前状态：{player_stats}。
    请生成一个突发的校园随机事件。
    内容可以是有趣的、挑战性的，或者是日常生活中的小插曲。关键词可以是：小测、早八、社团活动、恋爱、兼职、校内八卦、突发状况等,请在这些主题中随机选择。
    事件应包含两个选项，每个选项会对玩家的状态产生不同的影响（如心态、精力、风评等）。
    请严格输出 JSON 格式，不包含 markdown 标记，结构如下：
    {{
        "title": "事件标题",
        "desc": "事件描述（50字以内）",
        "options": [
            {{"id": "A", "text": "选项A描述", "effects": {{"energy": -5, "sanity": 5, "desc": "结果描述A"}}}},
            {{"id": "B", "text": "选项B描述", "effects": {{"reputation": -10, "stress": -5, "desc": "结果描述B"}}}}
        ]
    }}
    确保 effects 中的数值变化合理（-10 到 +10 之间）。
    """
    try:
        response = await client.chat.completions.create(
            model=os.getenv("LLM"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, # 强制 JSON 模式
            max_tokens=300
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM Error] {e}")
        return None
    
async def generate_wenyan_report(final_stats: dict) -> str:
    """
    根据玩家final_stats生成一段文言文风格的结业总结。
    """
    prompt = f"""
    你是一位古风文案大师。请根据以下玩家的折姜大学结业数据，为其撰写一段100字左右的文言文结业总结，内容需涵盖其专业、能力、GPA、性格、成就等主要信息，风格典雅、用词考究，严肃中不失诙谐风趣，结尾可有调侃或祝福。
    玩家数据：{final_stats}
    只需返回文言文内容本身，不要任何解释。
    """
    try:
        response = await client.chat.completions.create(
            model=os.getenv("LLM"),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[LLM Wenyan Error] {e}")
        return "学业既成，前程似锦。"