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

def _load_keywords():
    """加载 world/keywords.json 供 LLM 提示词使用"""
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent.parent
    kw_path = Path("/app/world/keywords.json") if Path("/app/world/keywords.json").exists() else base_dir / "world" / "keywords.json"
    try:
        with open(kw_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []
    
def _load_character_list():
    """加载 world/characters.json 供 LLM 提示词使用"""
    from pathlib import Path
    base_dir = Path(__file__).resolve().parent.parent.parent
    char_path = Path("/app/world/characters.json") if Path("/app/world/characters.json").exists() else base_dir / "world" / "characters.json"
    try:
        with open(char_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

async def generate_cc98_post(player_stats: dict, effect: str, trigger: str):
    """生成 CC98 帖子内容和反馈（批量缓存优化版）"""
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

    # 1. 优先从 Redis 队列获取（库存消耗）
    cc98_key = "cc98:posts"
    post_content = await RedisCache.lpop(cc98_key)
    if post_content:
        # 队列里有货，直接返回，不再存回去（避免重复）
        return post_content, feedback

    # 2. 队列为空，触发批量进货 (Batch Generation)
    keywords = _load_keywords()
    kw_hint = "\n关键词表：" + json.dumps(keywords, ensure_ascii=False) if keywords else ""
    
    # 修改 Prompt：要求一次生成 5 条
    # 第一条必须贴合当前 trigger，剩下的可以随机，确保存货的多样性
    prompt = f"""
    玩家当前状态：{player_stats}
    你正在模拟浙江大学CC98论坛的帖子列表。
    
    请生成 5 条简短、有趣、符合大学生网络用语的帖子标题/内容。
    要求：
    1. 第一条内容必须与主题“{trigger}”相关（效果：{effect}）。
    2. 剩下的 4 条可以是随机的校园日常话题（吐槽、求助、分享等），越丰富越好。
    {kw_hint}
    
    请严格输出 JSON 格式，结构如下：
    {{ "posts": ["帖子内容1", "帖子内容2", "帖子内容3", "帖子内容4", "帖子内容5"] }}
    """
    
    try:
        response = await client.chat.completions.create(
            model=os.getenv("LLM"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, # 开启 JSON 模式确保解析稳定
            max_tokens=300
        )
        
        data = json.loads(response.choices[0].message.content)
        posts = data.get("posts", [])
        
        if not posts:
            return "CC98 现在只有烂坑和吐槽...", feedback

        # 3. 分配货源
        current_post = posts[0] # 第一条直接给用户
        remaining_posts = posts[1:] # 剩下的存入仓库
        
        # 异步存入 Redis
        for p in remaining_posts:
            await RedisCache.rpush(cc98_key, p)
            
        return current_post, feedback

    except Exception as e:
        print(f"[LLM Error] {e}")
        return "CC98 服务器维护中...", feedback


async def generate_random_event(player_stats: dict, history: list = None): # [修复] 增加了 history 参数
    """
    生成随机事件（批量缓存版）
    """
    event_key = "game:events_pool"
    
    # 1. 尝试从缓存获取
    cached_event = await RedisCache.lpop(event_key)
    if cached_event:
        return json.loads(cached_event)

    # 2. 缓存为空，批量进货 (一次生成 3 个)
    keywords = _load_keywords()
    kw_hint = "\n关键词表：" + json.dumps(keywords, ensure_ascii=False) if keywords else ""
    
    # 构建“避雷针”提示词
    history_hint = ""
    if history:
        history_hint = f"\n近期已发生事件（请务必不要生成与之重复或高度相似的内容）：{', '.join(history)}"
        
    prompt = f"""
    你是一个文字模拟游戏的上帝系统。玩家是浙大学生，当前状态：{player_stats}。
    {kw_hint}
    {history_hint}
    请生成 3 个突发的校园随机事件。要求风格迥异：包含学习压力、社团社交、校园传说、校园恋爱、惊险事故、狼狈瞬间或生活小插曲。
    严禁与上方“近期已发生事件”雷同。
    每个事件应包含两个选项，会对玩家状态产生合理影响（-10 到 +10）。
    
    请严格输出 JSON 格式，结构如下：
    {{
        "events": [
            {{
                "title": "事件标题",
                "desc": "描述...",
                "options": [
                    {{"id": "A", "text": "...", "effects": {{"energy": -5, "desc": "..."}}}},
                    {{"id": "B", "text": "...", "effects": {{"sanity": 5, "desc": "..."}}}}
                ]
            }},
            ... (重复 3 个)
        ]
    }}
    """
    try:
        response = await client.chat.completions.create(
            model=os.getenv("LLM"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=800
        )
        data = json.loads(response.choices[0].message.content)
        events = data.get("events", [])
        
        if not events: return None

        # 分配：第一条直接用，剩下的存入 Redis
        current_event = events[0]
        for e in events[1:]:
            await RedisCache.rpush(event_key, json.dumps(e, ensure_ascii=False))
            
        return current_event
    except Exception as e:
        print(f"[LLM Event Error] {e}")
        return None


async def generate_dingtalk_message(player_stats: dict, context: str = "random"):
    """
    生成钉钉消息（批量缓存版）
    """
    msg_key = f"game:dingtalk_pool:{context}" # 根据上下文分类缓存
    
    # 1. 尝试从缓存获取
    cached_msg = await RedisCache.lpop(msg_key)
    if cached_msg:
        return json.loads(cached_msg)

    # 2. 批量进货 (一次生成 5 条)
    character_list = _load_character_list()
    
    prompt = f"""
    你正在模拟浙江大学的“钉钉”消息通知。玩家是浙大学生，当前状态：{player_stats}。
    触发场景：{context}。
    参考角色列表：{character_list}
    
    请批量生成 5 条不同的钉钉消息。
    要求：内容要真实（包含通知、约饭、求助、催作业等），发送人身份要切换。
    请严格输出 JSON 格式：
    {{
        "messages": [
            {{
                "sender": "发送人",
                "role": "counselor/student/system/teacher",
                "content": "内容（30字以内）",
                "is_urgent": false
            }},
            ... (重复 5 条)
        ]
    }}
    """
    try:
        response = await client.chat.completions.create(
            model=os.getenv("LLM"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=500
        )
        data = json.loads(response.choices[0].message.content)
        messages = data.get("messages", [])
        
        if not messages: return None

        current_msg = messages[0]
        for m in messages[1:]:
            # 设置过期时间（例如10分钟），防止旧消息在状态变化后显得太违和
            msg_str = json.dumps(m, ensure_ascii=False)
            await RedisCache.rpush(msg_key, msg_str)
            
        return current_msg
    except Exception as e:
        print(f"[LLM DingTalk Error] {e}")
        return None
    
async def generate_wenyan_report(final_stats: dict) -> str:
    """
    根据玩家final_stats生成一段文言文风格的结业总结。
    """
    keywords = _load_keywords()
    kw_hint = "\n关键词表：" + json.dumps(keywords, ensure_ascii=False) if keywords else ""
    prompt = f"""
    你是一位古风文案大师。请根据以下玩家的折姜大学结业数据，为其撰写一段100字左右的文言文结业总结，内容需涵盖其专业、能力、GPA、性格、成就等主要信息，风格典雅、用词考究，严肃中不失诙谐风趣，结尾可有调侃或祝福。
    {kw_hint}
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