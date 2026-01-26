import json
import os
from openai import AsyncOpenAI
from app.core.config import settings

# 初始化客户端 (适配 OpenAI 或 兼容接口如 DeepSeek/Moonshot)
# 如果是其他模型，请修改 base_url
client = AsyncOpenAI(
    api_key=os.getenv("LLM_API_KEY"),
    base_url=os.getenv("LLM_BASE_URL") 
)

async def generate_cc98_post(player_stats: dict) -> str:
    """生成 CC98 帖子内容"""
    prompt = f"""
    玩家当前状态：{player_stats}
    请模拟浙江大学CC98论坛的语气，生成一个简短的帖子标题和内容。
    风格可以是：吐槽食堂、凡尔赛GPA、询问选课、郁闷小屋、二手交易、情侣秀恩爱、渣男渣女分享感情经历等。
    要求：简短、有趣、符合大学生网络用语。返回格式纯文本即可。
    """
    try:
        response = await client.chat.completions.create(
            model="LLM", 
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"[LLM Error] {e}")
        return "CC98 服务器维护中..."

async def generate_random_event(player_stats: dict):
    """
    生成随机事件，要求返回 JSON 格式以便前端渲染选项
    """
    prompt = f"""
    你是一个文字模拟游戏的上帝系统。玩家是浙大学生，当前状态：{player_stats}。
    请生成一个突发的校园随机事件。
    
    请严格输出 JSON 格式，不包含 markdown 标记，结构如下：
    {{
        "title": "事件标题",
        "desc": "事件描述（50字以内）",
        "options": [
            {{"id": "A", "text": "选项A描述", "effects": {{"energy": -5, "sanity": 5, "desc": "结果描述A"}}}},
            {{"id": "B", "text": "选项B描述", "effects": {{"reputation": -10, "stress": -5, "desc": "结果描述B"}}}}
        ]
    }}
    确保 effects 中的数值变化合理（-20 到 +20 之间）。
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, # 强制 JSON 模式
            max_tokens=300
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"[LLM Error] {e}")
        return None