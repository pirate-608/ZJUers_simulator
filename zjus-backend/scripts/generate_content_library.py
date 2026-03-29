"""
离线批量生成事件库和 CC98 帖子库

使用 Ollama 本地模型 (qwen3.5:4B-Q4_K_M) 批量生成内容，
输出到 world/event_library.json 和 world/cc98_library.json。

Usage:
    python scripts/generate_content_library.py --events 300 --cc98 500
    python scripts/generate_content_library.py --events-only 100
    python scripts/generate_content_library.py --cc98-only 200
"""

import argparse
import json
import sys
import time
import uuid
import random
import re  # 添加这行
import ast
from pathlib import Path
from typing import List, Dict, Any, Optional

import requests

# ============================================================
# 配置
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/chat"
_config = {"model": "qwen3.5:4B"}
WORLD_DIR = Path(__file__).resolve().parent.parent / "zjus-backend" / "world"

# 如果从 zjus-backend 目录运行
if not WORLD_DIR.exists():
    WORLD_DIR = Path(__file__).resolve().parent.parent / "world"

# ============================================================
# 加载 CC98 版面完整数据
# ============================================================

CC98_TOPIC_DATA = {}
TOPIC_EXAMPLES_PATH = WORLD_DIR / "topic_examples.json"

if TOPIC_EXAMPLES_PATH.exists():
    with open(TOPIC_EXAMPLES_PATH, "r", encoding="utf-8") as f:
        topic_data = json.load(f)
    for item in topic_data:
        topic_name = item["topic"]
        CC98_TOPIC_DATA[topic_name] = {
            "description": item.get("description", ""),
            "examples": item.get("examples", [])
        }
    # 动态生成 CC98_TOPICS 列表，用于随机选择版面
    CC98_TOPICS = list(CC98_TOPIC_DATA.keys())
    print(f"✅ 已加载 {len(CC98_TOPICS)} 个 CC98 版面示例数据")
else:
    print(f"⚠️ 未找到 topic_examples.json，将使用默认 CC98_TOPICS 列表")
    # 回退到硬编码列表（如果您之前有定义，可以保留）
    CC98_TOPICS = [
        "似水流年", "心灵之约", "开怀一笑", "郁闷小屋",
        "感性空间", "日用交易", "学习天地", "一路走来",
        "实习兼职", "考研一族", "校园信息", "缘分天空",
        "真我风采"
    ]

# ============================================================
# 加载校园关键词库
# ============================================================

KEYWORDS_DATA = []
KEYWORDS_PATH = WORLD_DIR / "keywords.json"

if KEYWORDS_PATH.exists():
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        KEYWORDS_DATA = json.load(f)
    print(f"✅ 已加载 {len(KEYWORDS_DATA)} 个校园关键词")
else:
    print(f"⚠️ 未找到 keywords.json，将不使用关键词提示")

# ============================================================
# Ollama 调用（非流式，think=False）
# ============================================================

def call_ollama(messages: List[Dict[str, str]], max_retries: int = 3) -> Optional[str]:
    """调用 Ollama API，禁用思考模式，返回纯文本响应"""
    payload = {
        "model": _config["model"],
        "messages": messages,
        "stream": False,
        "think": False,
    }

    for attempt in range(max_retries):
        try:
            # 连接超时 5 秒，读取超时 120 秒
            resp = requests.post(OLLAMA_URL, json=payload, timeout=(5, 120))
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return content.strip()
        except requests.exceptions.Timeout:
            print(f"  ⚠️ 请求超时 (尝试 {attempt+1}/{max_retries})")
        except requests.exceptions.ConnectionError:
            print(f"  ⚠️ Ollama 连接失败 (尝试 {attempt+1}/{max_retries})，请确认 ollama serve 已启动")
        except Exception as e:
            print(f"  ⚠️ 调用失败: {e} (尝试 {attempt+1}/{max_retries})")

        if attempt < max_retries - 1:
            time.sleep(2)
    return None


def extract_json(raw: str) -> Optional[Any]:
    """从 LLM 输出中提取 JSON（增强版，处理更多格式问题）"""
    if not raw:
        return None

    text = raw.strip()

    # 1. 移除 Markdown 代码块标记
    text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)

    # 2. 移除注释（单行 // 和 多行 /* */）
    text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    # 3. 修复未转义的控制字符（如换行符在字符串中未转义）
    # 这一步比较复杂，简单处理：将字符串中的真实换行替换为 \\n
    # 注意：可能破坏 JSON 结构，但多数模型输出中换行本应转义
    def escape_control_chars(match):
        s = match.group(0)
        return s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    # 仅处理双引号字符串内的内容（粗略匹配，不够精确，但常用）
    text = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', escape_control_chars, text, flags=re.DOTALL)

    # 4. 清理尾随逗号（对象和数组）
    # 在 } 或 ] 之前的逗号
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    # 5. 处理单引号 -> 双引号（谨慎：可能破坏字符串内的单引号）
    # 只在明显是键名或值未被双引号包裹时替换，简单策略：将最外层的单引号替换
    # 但为避免误伤，先尝试直接解析，若失败再替换
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # 尝试将单引号替换为双引号（注意字符串内可能也有单引号，但多数情况下可用）
        text2 = text.replace("'", '"')
        try:
            return json.loads(text2)
        except json.JSONDecodeError:
            pass

    # 6. 使用 ast.literal_eval 尝试（适用于 Python 字面量，但 JSON 大多兼容）
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        pass

    # 7. 提取 JSON 对象或数组片段（当模型输出包含额外文本时）
    try:
        # 找到第一个 { 或 [ 和最后一个 } 或 ]
        start = None
        end = None
        for i, ch in enumerate(text):
            if ch in '{[':
                start = i
                break
        if start is not None:
            # 从 start 开始找匹配的结束括号
            stack = []
            for i in range(start, len(text)):
                ch = text[i]
                if ch in '{[':
                    stack.append(ch)
                elif ch == '}' and stack and stack[-1] == '{':
                    stack.pop()
                    if not stack:
                        end = i + 1
                        break
                elif ch == ']' and stack and stack[-1] == '[':
                    stack.pop()
                    if not stack:
                        end = i + 1
                        break
            if end:
                json_text = text[start:end]
                # 再次清理尾随逗号
                json_text = re.sub(r',\s*}', '}', json_text)
                json_text = re.sub(r',\s*]', ']', json_text)
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    pass

        # 如果没有找到匹配的括号，尝试找第一个 { 或 [ 到末尾
        start = text.find('{') if text.find('{') != -1 else text.find('[')
        if start != -1:
            json_text = text[start:]
            # 清理尾随逗号
            json_text = re.sub(r',\s*}', '}', json_text)
            json_text = re.sub(r',\s*]', ']', json_text)
            try:
                return json.loads(json_text)
            except json.JSONDecodeError:
                pass
    except Exception:
        pass

    return None

def get_random_keywords(count: int = 3) -> str:
    """随机选取 count 个关键词，返回适合嵌入提示词的字符串（包含示例）"""
    if not KEYWORDS_DATA:
        return ""
    selected = random.sample(KEYWORDS_DATA, min(count, len(KEYWORDS_DATA)))
    lines = []
    for kw in selected:
        keyword = kw.get("keyword", "")
        desc = kw.get("desc", "")
        examples = kw.get("examples", [])
        # 随机选一条示例（如果有）
        example_text = ""
        if examples:
            example = random.choice(examples)
            example_text = f" 示例：{example}"
        lines.append(f"- {keyword}：{desc}{example_text}")
    return "浙大校园关键词（仅供参考）：\n" + "\n".join(lines)

# ============================================================
# 事件库生成
# ============================================================

EVENT_CATEGORIES = [
    ("学业压力", "考试/选课/均绩/挂科/补考/毕业论文"),
    ("社团社交", "社团招新/学生会/聚餐/团建/志愿者"),
    ("校园传说", "月牙楼/图书馆鬼层/校园怪谈/神秘涂鸦"),
    ("校园恋爱", "表白/暗恋/约会/分手/520"),
    ("惊险事故", "骑车摔倒/实验事故/暴雨淹路/停电"),
    ("狼狈瞬间", "迟到/忘带校园卡/外卖丢失/答辩翻车"),
    ("生活小插曲", "食堂/快递/室友/网购/养猫"),
    ("科研日常", "导师/实验室/论文/科研竞赛/项目"),
]

SANITY_RANGES = [
    ([0, 30], "低心态"),
    ([30, 70], "中心态"),
    ([70, 200], "高心态"),
]

STRESS_RANGES = [
    ([0, 30], "低压力"),
    ([30, 70], "中压力"),
    ([70, 200], "高压力"),
]


def generate_events(target_count: int) -> List[Dict[str, Any]]:
    """批量生成随机事件"""
    events = []
    batch_size = 3
    consecutive_failures = 0

    print(f"\n🎲 开始生成随机事件库（目标 {target_count} 条）...\n")

    try:
        while len(events) < target_count:
            # 如果连续失败太多，降低 batch_size
            if consecutive_failures > 3:
                current_batch = 1
            else:
                current_batch = batch_size

            category, keywords = random.choice(EVENT_CATEGORIES)
            sanity_range, sanity_label = random.choice(SANITY_RANGES)
            stress_range, stress_label = random.choice(STRESS_RANGES)
            keywords_text = get_random_keywords(3)

            prompt = f"""你是一个浙江大学校园生活模拟游戏的事件设计师。
请生成 {current_batch} 个不同的校园随机事件，主题类型为【{category}】。
{keywords_text}

【重要】请直接输出一个 JSON 对象，不要包含任何其他文字、注释或 Markdown 标记：
{{
  "events": [
    {{
      "title": "事件标题",
      "desc": "事件描述（50-80字）",
      "tags": ["{category}", "标签2"],
      "options": [
        {{
          "id": "A",
          "text": "选项A文本",
          "effects": {{
            "energy": -3,
            "sanity": 2,
            "stress": 1,
            "luck": 0,
            "reputation": 0,
            "desc": "选择A的结果描述"
          }}
        }},
        {{
          "id": "B",
          "text": "选项B文本",
          "effects": {{
            "energy": 1,
            "sanity": -2,
            "stress": -3,
            "luck": 1,
            "reputation": 1,
            "desc": "选择B的结果描述"
          }}
        }}
      ]
    }}
  ]
}}

要求：
1. 每个事件必须包含 title、desc、tags、options
2. options 必须包含两个选项，每个选项必须有 id、text、effects
3. effects 必须包含 desc 字段，以及以下任意字段：energy(-10~10)、sanity(-10~10)、stress(-10~10)、luck(-5~5)、reputation(-5~5)
4. 描述要生动有趣，符合浙大学生视角
5. 事件适合{sanity_label}、{stress_label}的玩家

现在请直接输出 JSON："""

            messages = [{"role": "user", "content": prompt}]
            raw = call_ollama(messages)

            if not raw:
                print(f"  ❌ 生成失败，跳过本批次")
                consecutive_failures += 1
                continue

            data = extract_json(raw)

            if not data:
                print(f"  ❌ JSON 解析失败，跳过本批次")
                print(f"  📝 原始内容前200字符: {raw[:200]}")
                consecutive_failures += 1
                continue

            consecutive_failures = 0

            # 处理不同的返回格式
            if isinstance(data, list):
                events_data = data
            elif isinstance(data, dict) and "events" in data:
                events_data = data["events"]
            else:
                print(f"  ❌ 不支持的 JSON 格式，跳过本批次")
                continue

            if not isinstance(events_data, list):
                print(f"  ❌ events 不是数组格式，跳过本批次")
                continue

            valid_count = 0
            for evt in events_data:
                if not evt or not isinstance(evt, dict):
                    continue
                if not evt.get("title") or not evt.get("desc") or not evt.get("options"):
                    continue

                options = evt.get("options", [])
                if len(options) < 2:
                    continue

                for opt in options:
                    if "effects" in opt:
                        if "desc" not in opt["effects"]:
                            opt["effects"]["desc"] = f"你选择了{opt.get('text', '这个选项')}"
                        opt["effects"] = {k: v for k, v in opt["effects"].items() if v is not None}

                evt["id"] = f"evt_{uuid.uuid4().hex[:8]}"
                evt["sanity_range"] = sanity_range
                evt["stress_range"] = stress_range
                if "tags" not in evt:
                    evt["tags"] = [category]

                events.append(evt)
                valid_count += 1

            print(f"  ✅ {len(events)}/{target_count} 事件已生成 (本批次 +{valid_count})")

            if valid_count == 0:
                time.sleep(1)
            else:
                time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断，正在保存已生成的事件...")
        # 返回已生成的事件（未达到目标数量）
        return events

    return events[:target_count]


# ============================================================
# CC98 帖子库生成
# ============================================================

CC98_EFFECTS = ["positive", "neutral", "negative"]

def generate_cc98_posts(target_count: int) -> List[Dict[str, Any]]:
    """批量生成 CC98 帖子"""
    posts = []
    batch_size = 5
    consecutive_failures = 0

    print(f"\n🌊 开始生成 CC98 帖子库（目标 {target_count} 条）...\n")

    try:
        while len(posts) < target_count:
            if consecutive_failures > 3:
                current_batch = 2
            else:
                current_batch = batch_size

            effect = random.choice(CC98_EFFECTS)
            topic = random.choice(CC98_TOPICS)  # 使用动态生成的 CC98_TOPICS

            # 获取该版面的完整数据
            topic_info = CC98_TOPIC_DATA.get(topic, {})
            description = topic_info.get("description", "")
            examples = topic_info.get("examples", [])

            # 随机选一条示例作为参考（可选多条，但建议单条避免 prompt 过长）
            example_text = ""
            if examples:
                selected_example = random.choice(examples)
                example_text = f"参考示例：{selected_example}"

            effect_desc = {
                "positive": "搞笑/治愈/正能量，让人心情变好",
                "neutral": "普通/日常/无聊，不影响心情",
                "negative": "emo/焦虑/吐槽/烂坑，让人心态崩",
            }[effect]

            # 随机选取 2 个关键词
            keywords_text = get_random_keywords(2)

            prompt = f"""你正在模拟浙江大学 CC98 论坛的「{topic}」版面。
版面描述：{description}
{example_text}

{keywords_text}

请生成 {current_batch} 条符合该版面风格的简短论坛帖子内容。
情绪效果：{effect_desc}

【重要】请直接输出一个 JSON 对象，不要包含任何其他文字：
{{"posts": ["帖子内容1", "帖子内容2", ...]}}

要求：
1. 每条帖子内容简短（10-30字），像真实浙大学生发的
2. 使用大学生网络用语，自然接地气
3. {keywords_text}
4. 不同帖子之间风格要有差异 
5. 可根据语境添加cc98独有的表情符号，如[ac01]（扇子）、[ac05]（呆住，无语）、[ac06]（抿嘴憋笑卖萌，表示可爱）、[ac08]（抱拳微笑，表示感谢、祝福、赞美等）、[ac09]（暴跳如雷，表示“怒了一下”）、[ac19]（震惊、惊讶）、[ac22]（难过）、[ac35]（大哭）

现在请直接输出 JSON："""

            messages = [{"role": "user", "content": prompt}]
            raw = call_ollama(messages)

            if not raw:
                print(f"  ❌ 生成失败，跳过本批次")
                consecutive_failures += 1
                continue

            data = extract_json(raw)

            if not data:
                print(f"  ❌ JSON 解析失败，跳过本批次")
                print(f"  📝 原始内容: {raw[:150]}...")
                consecutive_failures += 1
                continue

            consecutive_failures = 0

            if isinstance(data, dict) and "posts" in data:
                posts_data = data["posts"]
            elif isinstance(data, list):
                posts_data = data
            else:
                print(f"  ❌ 不支持的 JSON 格式，跳过本批次")
                continue

            if not isinstance(posts_data, list):
                continue

            valid_count = 0
            for content in posts_data:
                if content and isinstance(content, str):
                    posts.append({
                        "id": f"cc98_{uuid.uuid4().hex[:8]}",
                        "effect": effect,
                        "topic": topic,
                        "content": content.strip(),
                    })
                    valid_count += 1

            print(f"  ✅ {len(posts)}/{target_count} 帖子已生成 (本批次 +{valid_count})")

            if valid_count == 0:
                time.sleep(1)
            else:
                time.sleep(0.2)

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断，正在保存已生成的帖子...")
        return posts

    return posts[:target_count]


# ============================================================
# 主入口
# ============================================================

def main():
    print("DEBUG: 进入 main 函数", flush=True)
    parser = argparse.ArgumentParser(description="离线批量生成事件库和 CC98 帖子库")
    parser.add_argument("--events", type=int, default=0, help="生成随机事件数量")
    parser.add_argument("--cc98", type=int, default=0, help="生成 CC98 帖子数量")
    parser.add_argument("--events-only", type=int, default=0, help="仅生成事件")
    parser.add_argument("--cc98-only", type=int, default=0, help="仅生成帖子")
    parser.add_argument("--model", type=str, default=_config["model"], help=f"Ollama 模型名（默认 {_config['model']}）")
    parser.add_argument("--append", action="store_true", help="追加到现有库而不是覆盖")
    args = parser.parse_args()

    _config["model"] = args.model

    event_count = args.events or args.events_only
    cc98_count = args.cc98 or args.cc98_only

    if not event_count and not cc98_count:
        print("请指定生成数量，例如：")
        print("  python scripts/generate_content_library.py --events 300 --cc98 500")
        print("  python scripts/generate_content_library.py --events-only 50")
        sys.exit(1)

    # 检查 Ollama 可用性
    try:
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m["name"] for m in resp.json().get("models", [])]
        print(f"✅ Ollama 已连接，可用模型: {', '.join(models[:5])}")
        if not any(_config["model"].split(":")[0] in m for m in models):
            print(f"⚠️  模型 {_config['model']} 未找到，请先 `ollama pull {_config['model']}`")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 无法连接 Ollama: {e}")
        print("请确保已启动 `ollama serve`")
        sys.exit(1)

    try:
        # 生成事件
        if event_count > 0:
            events = generate_events(event_count)
            out_path = WORLD_DIR / "event_library.json"

            if args.append and out_path.exists():
                with open(out_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                events = existing + events
                print(f"\n📎 追加模式：已有 {len(existing)} 条 + 新增 {len(events) - len(existing)} 条")

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
            print(f"\n📦 事件库已保存: {out_path} ({len(events)} 条)")

        # 生成 CC98 帖子
        if cc98_count > 0:
            posts = generate_cc98_posts(cc98_count)
            out_path = WORLD_DIR / "cc98_library.json"

            if args.append and out_path.exists():
                with open(out_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                posts = existing + posts
                print(f"\n📎 追加模式：已有 {len(existing)} 条 + 新增 {len(posts) - len(existing)} 条")

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(posts, f, ensure_ascii=False, indent=2)
            print(f"\n📦 CC98 帖子库已保存: {out_path} ({len(posts)} 条)")

    except KeyboardInterrupt:
        print("\n⚠️ 程序被用户中断。")
        # 如果已经生成了部分数据，仍然保存
        if 'events' in locals() and events:
            out_path = WORLD_DIR / "event_library.json"
            if args.append and out_path.exists():
                try:
                    with open(out_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    events = existing + events
                except:
                    pass
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
            print(f"📦 已保存 {len(events)} 条事件到 {out_path}")
        if 'posts' in locals() and posts:
            out_path = WORLD_DIR / "cc98_library.json"
            if args.append and out_path.exists():
                try:
                    with open(out_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    posts = existing + posts
                except:
                    pass
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(posts, f, ensure_ascii=False, indent=2)
            print(f"📦 已保存 {len(posts)} 条帖子到 {out_path}")
        sys.exit(0)

    print("\n🎉 生成完毕！")

if __name__ == "__main__":
    main()
