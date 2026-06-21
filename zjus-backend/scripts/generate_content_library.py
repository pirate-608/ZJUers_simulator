"""Generate offline event-library and CC98-library content.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.

Notes:
    The script uses an OpenAI-compatible chat/completions endpoint and writes
    generated data to `world/event_library.json` and `world/cc98_library.json`.
    It can target cloud APIs or a local Ollama `/v1` endpoint.

Usage:
    python scripts/generate_content_library.py --events 300 --cc98 500
    python scripts/generate_content_library.py --events-only 100
    python scripts/generate_content_library.py --cc98-only 200
"""

import argparse
import ast
import json
import os
import random
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from openai import APIConnectionError, APITimeoutError, OpenAI, OpenAIError

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.game.stat_definitions import stat_definitions  # noqa: E402

# ============================================================
# Configuration.
# ============================================================

_config = {
    "api_base": (
        os.environ.get("OPENAI_API_BASE")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ),
    "api_key": os.environ.get("OPENAI_API_KEY", ""),
    "model": (
        os.environ.get("OPENAI_API_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "qwen3.5-flash"
    ),
    "temperature": float(os.environ.get("OPENAI_TEMPERATURE", "0.7")),
    "json_mode": os.environ.get("OPENAI_JSON_MODE", "1").lower()
    not in {"0", "false", "no"},
}
WORLD_DIR = Path(__file__).resolve().parent.parent / "zjus-backend" / "world"

# Support both repository-root and `zjus-backend/` working directories.
if not WORLD_DIR.exists():
    WORLD_DIR = Path(__file__).resolve().parent.parent / "world"

ALLOWED_EVENT_EFFECT_FIELDS = set(stat_definitions.event_effect_fields) | {"desc"}


def allowed_event_effect_prompt() -> str:
    """Return a compact prompt fragment aligned with stat_definitions.json."""
    labels = stat_definitions.feedback_labels
    parts = [
        f"{field}（{labels.get(field, field)}）"
        for field in sorted(stat_definitions.event_effect_fields)
    ]
    return "、".join(parts)

# ============================================================
# Load CC98 topic metadata.
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
    CC98_TOPICS = list(CC98_TOPIC_DATA.keys())
    print(f"✅ 已加载 {len(CC98_TOPICS)} 个 CC98 版面示例数据")
else:
    print("⚠️ 未找到 topic_examples.json，将使用默认 CC98_TOPICS 列表")
    # Fall back to a compact topic list when examples are unavailable.
    CC98_TOPICS = [
        "似水流年", "心灵之约", "开怀一笑", "郁闷小屋",
        "感性空间", "日用交易", "学习天地", "一路走来",
        "实习兼职", "考研一族", "校园信息", "缘分天空",
        "真我风采"
    ]

# ============================================================
# Load campus keyword data.
# ============================================================

KEYWORDS_DATA = []
KEYWORDS_PATH = WORLD_DIR / "keywords.json"

if KEYWORDS_PATH.exists():
    with open(KEYWORDS_PATH, "r", encoding="utf-8") as f:
        KEYWORDS_DATA = json.load(f)
    print(f"✅ 已加载 {len(KEYWORDS_DATA)} 个校园关键词")
else:
    print("⚠️ 未找到 keywords.json，将不使用关键词提示")

# ============================================================
# OpenAI-compatible API calls.
# ============================================================

def _api_base() -> str:
    return str(_config.get("api_base") or "").rstrip("/")


def _api_key() -> str:
    # Ollama's OpenAI-compatible endpoint ignores the key, but the SDK
    # requires a non-empty value.
    return str(_config.get("api_key") or "ollama")


def build_openai_client() -> OpenAI:
    """Build an OpenAI SDK client for Ollama or cloud OpenAI-like endpoints."""
    return OpenAI(
        api_key=_api_key(),
        base_url=_api_base(),
        timeout=120.0,
        max_retries=0,
    )


def _completion_text(content: object) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for part in content:
            if isinstance(part, dict):
                text = part.get("text") or part.get("content")
                if isinstance(text, str):
                    parts.append(text)
            elif isinstance(part, str):
                parts.append(part)
        return "".join(parts).strip()
    return ""


def _chat_once(
    client: OpenAI,
    messages: list[dict[str, str]],
    *,
    use_json_mode: bool,
) -> str:
    kwargs: dict[str, Any] = {
        "model": str(_config["model"]),
        "messages": messages,
        "temperature": float(_config.get("temperature", 0.7)),
    }
    if use_json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    if not response.choices:
        return ""
    return _completion_text(response.choices[0].message.content)


def call_llm(messages: List[Dict[str, str]], max_retries: int = 3) -> Optional[str]:
    """Call an OpenAI-compatible chat/completions endpoint and return text."""
    if not _api_base().startswith(("http://", "https://")):
        print("  ⚠️ 无效的 API_BASE，必须以 http/https 开头")
        return None

    client = build_openai_client()
    use_json_mode = bool(_config.get("json_mode", True))

    for attempt in range(max_retries):
        try:
            return _chat_once(client, messages, use_json_mode=use_json_mode)
        except APITimeoutError:
            print(f"  ⚠️ 请求超时 (尝试 {attempt + 1}/{max_retries})")
        except APIConnectionError:
            print(
                f"  ⚠️ API 连接失败 (尝试 {attempt + 1}/{max_retries})，"
                "请确认网络和 API_BASE 设置"
            )
        except OpenAIError as exc:
            if use_json_mode:
                print("  ⚠️ 当前端点不支持 JSON mode，改用普通文本模式重试")
                use_json_mode = False
                try:
                    return _chat_once(client, messages, use_json_mode=False)
                except Exception as retry_exc:
                    print(
                        f"  ⚠️ 普通文本模式仍失败: {retry_exc} "
                        f"(尝试 {attempt + 1}/{max_retries})"
                    )
            else:
                print(f"  ⚠️ API 调用失败: {exc} (尝试 {attempt + 1}/{max_retries})")
        except Exception as exc:
            print(f"  ⚠️ 调用失败: {exc} (尝试 {attempt + 1}/{max_retries})")

        if attempt < max_retries - 1:
            time.sleep(2)
    return None


def extract_json(raw: str) -> Optional[Any]:
    """Extract JSON from model output that may include markdown or prose."""
    if not raw:
        return None

    text = raw.strip()

    # Strip markdown code fences before parsing.
    text = re.sub(r'^```json\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'^```\s*', '', text, flags=re.MULTILINE)
    text = re.sub(r'\s*```$', '', text, flags=re.MULTILINE)

    # Remove JS-style comments that models sometimes include in JSON.
    text = re.sub(r'//.*?$', '', text, flags=re.MULTILINE)
    text = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)

    # Escape raw control characters inside quoted strings. This heuristic is
    # intentionally conservative and targets common model formatting mistakes.
    def escape_control_chars(match):
        s = match.group(0)
        return s.replace('\n', '\\n').replace('\r', '\\r').replace('\t', '\\t')
    # Only touch double-quoted strings to avoid disturbing JSON structure.
    text = re.sub(
        r'"[^"\\]*(?:\\.[^"\\]*)*"',
        escape_control_chars,
        text,
        flags=re.DOTALL,
    )

    # Remove trailing commas before object or array terminators.
    text = re.sub(r',\s*}', '}', text)
    text = re.sub(r',\s*]', ']', text)

    # Try strict JSON first, then tolerate single-quoted model output.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        text2 = text.replace("'", '"')
        try:
            return json.loads(text2)
        except json.JSONDecodeError:
            pass

    # Python literals are a useful final fallback for near-JSON output.
    try:
        return ast.literal_eval(text)
    except (ValueError, SyntaxError):
        pass

    # Extract a balanced JSON object or array from surrounding prose.
    try:
        start = None
        end = None
        for i, ch in enumerate(text):
            if ch in '{[':
                start = i
                break
        if start is not None:
            # Find the matching closing bracket for the first JSON-like token.
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
                # Clean trailing commas in the extracted fragment.
                json_text = re.sub(r',\s*}', '}', json_text)
                json_text = re.sub(r',\s*]', ']', json_text)
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError:
                    pass

        # If balanced matching fails, try from the first JSON-looking token.
        start = text.find('{') if text.find('{') != -1 else text.find('[')
        if start != -1:
            json_text = text[start:]
            # Clean up trailing commas before the final parse attempt.
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
    """Return a prompt-ready sample of campus keywords and optional examples."""
    if not KEYWORDS_DATA:
        return ""
    selected = random.sample(KEYWORDS_DATA, min(count, len(KEYWORDS_DATA)))
    lines = []
    for kw in selected:
        keyword = kw.get("keyword", "")
        desc = kw.get("desc", "")
        examples = kw.get("examples", [])
        # Include one random example when the keyword provides examples.
        example_text = ""
        if examples:
            example = random.choice(examples)
            example_text = f" 示例：{example}"
        lines.append(f"- {keyword}：{desc}{example_text}")
    return "浙大校园关键词（仅供参考）：\n" + "\n".join(lines)

# ============================================================
# Event library generation.
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
    """Generate random-event library rows in small batches."""
    events = []
    batch_size = 3
    consecutive_failures = 0

    print(f"\n🎲 开始生成随机事件库（目标 {target_count} 条）...\n")

    try:
        while len(events) < target_count:
            # Lower batch size after repeated failures to improve recovery odds.
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
3. effects 必须包含 desc 字段，以及以下任意字段：
   {allowed_event_effect_prompt()}
   数值变化请保持克制，常规字段建议控制在 -10 到 10 之间
4. 描述要生动有趣，符合浙大学生视角
5. 事件适合{sanity_label}、{stress_label}的玩家

现在请直接输出 JSON："""

            messages = [{"role": "user", "content": prompt}]
            raw = call_llm(messages)

            if not raw:
                print("  ❌ 生成失败，跳过本批次")
                consecutive_failures += 1
                continue

            data = extract_json(raw)

            if not data:
                print("  ❌ JSON 解析失败，跳过本批次")
                print(f"  📝 原始内容前200字符: {raw[:200]}")
                consecutive_failures += 1
                continue

            consecutive_failures = 0

            # Accept either a bare list or an object with an `events` list.
            if isinstance(data, list):
                events_data = data
            elif isinstance(data, dict) and "events" in data:
                events_data = data["events"]
            else:
                print("  ❌ 不支持的 JSON 格式，跳过本批次")
                continue

            if not isinstance(events_data, list):
                print("  ❌ events 不是数组格式，跳过本批次")
                continue

            valid_count = 0
            for evt in events_data:
                if not evt or not isinstance(evt, dict):
                    continue
                if not all(evt.get(key) for key in ("title", "desc", "options")):
                    continue

                options = evt.get("options", [])
                if len(options) < 2:
                    continue

                for opt in options:
                    if "effects" in opt:
                        if "desc" not in opt["effects"]:
                            opt["effects"]["desc"] = (
                                f"你选择了{opt.get('text', '这个选项')}"
                            )
                        opt["effects"] = {
                            k: v
                            for k, v in opt["effects"].items()
                            if v is not None and k in ALLOWED_EVENT_EFFECT_FIELDS
                        }

                evt["id"] = f"evt_{uuid.uuid4().hex[:8]}"
                evt["sanity_range"] = sanity_range
                evt["stress_range"] = stress_range
                if "tags" not in evt:
                    evt["tags"] = [category]

                events.append(evt)
                valid_count += 1

            print(
                f"  ✅ {len(events)}/{target_count} 事件已生成 "
                f"(本批次 +{valid_count})"
            )

            if valid_count == 0:
                time.sleep(1)
            else:
                time.sleep(0.3)

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断，正在保存已生成的事件...")
        return events

    return events[:target_count]


# ============================================================
# CC98 post library generation.
# ============================================================

CC98_EFFECTS = ["positive", "neutral", "negative"]

def _choose_balanced_cc98_effect(effect_counts: Dict[str, int]) -> str:
    """Pick the least-used effect bucket so generated libraries stay balanced."""
    min_count = min(effect_counts.get(effect, 0) for effect in CC98_EFFECTS)
    candidates = [
        effect for effect in CC98_EFFECTS
        if effect_counts.get(effect, 0) == min_count
    ]
    return random.choice(candidates)

def generate_cc98_posts(target_count: int) -> List[Dict[str, Any]]:
    """Generate CC98 post-library rows in balanced effect buckets."""
    posts = []
    batch_size = 5
    consecutive_failures = 0
    effect_counts = {effect: 0 for effect in CC98_EFFECTS}

    print(f"\n🌊 开始生成 CC98 帖子库（目标 {target_count} 条）...\n")

    try:
        while len(posts) < target_count:
            if consecutive_failures > 3:
                current_batch = 2
            else:
                current_batch = batch_size

            current_batch = min(current_batch, target_count - len(posts))
            effect = _choose_balanced_cc98_effect(effect_counts)
            topic = random.choice(CC98_TOPICS)

            # Use full topic metadata to ground the prompt.
            topic_info = CC98_TOPIC_DATA.get(topic, {})
            description = topic_info.get("description", "")
            examples = topic_info.get("examples", [])

            # One example is enough grounding without making the prompt too long.
            example_text = ""
            if examples:
                selected_example = random.choice(examples)
                example_text = f"参考示例：{selected_example}"

            effect_desc = {
                "positive": "搞笑/治愈/正能量，让人心情变好",
                "neutral": "普通/日常/无聊，不影响心情",
                "negative": "emo/焦虑/吐槽/烂坑，让人心态崩",
            }[effect]

            # Add a small keyword sample to diversify CC98 topics.
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
5. 可根据语境添加cc98独有的表情符号，如[ac01]（扇子）、
   [ac05]（呆住，无语）、[ac06]（抿嘴憋笑卖萌，表示可爱）、
   [ac08]（抱拳微笑，表示感谢、祝福、赞美等）、
   [ac09]（暴跳如雷，表示“怒了一下”）、[ac19]（震惊、惊讶）、
   [ac22]（难过）、[ac35]（大哭）

现在请直接输出 JSON："""

            messages = [{"role": "user", "content": prompt}]
            raw = call_llm(messages)

            if not raw:
                print("  ❌ 生成失败，跳过本批次")
                consecutive_failures += 1
                continue

            data = extract_json(raw)

            if not data:
                print("  ❌ JSON 解析失败，跳过本批次")
                print(f"  📝 原始内容: {raw[:150]}...")
                consecutive_failures += 1
                continue

            consecutive_failures = 0

            if isinstance(data, dict) and "posts" in data:
                posts_data = data["posts"]
            elif isinstance(data, list):
                posts_data = data
            else:
                print("  ❌ 不支持的 JSON 格式，跳过本批次")
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
                    effect_counts[effect] += 1
                    valid_count += 1

            print(
                f"  ✅ {len(posts)}/{target_count} 帖子已生成 "
                f"(本批次 +{valid_count})"
            )

            if valid_count == 0:
                time.sleep(1)
            else:
                time.sleep(0.2)

    except KeyboardInterrupt:
        print("\n⚠️ 用户中断，正在保存已生成的帖子...")
        return posts

    print(
        "  📊 CC98 情绪分布："
        + ", ".join(
            f"{effect}={effect_counts.get(effect, 0)}" for effect in CC98_EFFECTS
        )
    )
    return posts[:target_count]


# ============================================================
# CLI entry point.
# ============================================================

def main():
    """CLI entry point for offline event and CC98 library generation."""
    parser = argparse.ArgumentParser(description="离线批量生成事件库和 CC98 帖子库")
    parser.add_argument("--events", type=int, default=0, help="生成随机事件数量")
    parser.add_argument("--cc98", type=int, default=0, help="生成 CC98 帖子数量")
    parser.add_argument("--events-only", type=int, default=0, help="仅生成事件")
    parser.add_argument("--cc98-only", type=int, default=0, help="仅生成帖子")
    parser.add_argument(
        "--model", type=str, default=_config["model"], help="调用的模型名"
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=_config["api_base"],
        help="OpenAI 兼容 API Base URL",
    )
    parser.add_argument(
        "--api-key", type=str, default=_config["api_key"], help="API Key"
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=float(_config["temperature"]),
        help="采样温度",
    )
    parser.add_argument(
        "--no-json-mode",
        action="store_true",
        help="禁用 response_format=json_object，用于兼容较旧端点",
    )
    parser.add_argument("--append", action="store_true", help="追加到现有库而不是覆盖")
    args = parser.parse_args()

    _config["model"] = args.model
    _config["api_base"] = args.api_base
    _config["api_key"] = args.api_key
    _config["temperature"] = args.temperature
    if args.no_json_mode:
        _config["json_mode"] = False

    event_count = args.events or args.events_only
    cc98_count = args.cc98 or args.cc98_only

    if not event_count and not cc98_count:
        print("请指定生成数量，例如：")
        print("  python scripts/generate_content_library.py --events 300 --cc98 500")
        print("  python scripts/generate_content_library.py --events-only 50")
        sys.exit(1)

    # Probe the configured endpoint before starting expensive generation.
    if not _api_base().startswith(("http://", "https://")):
        print("⚠️ 无效的 API_BASE，必须以 http/https 开头")
        sys.exit(1)

    try:
        models_page = build_openai_client().models.list()
        models = [m.id for m in models_page.data if getattr(m, "id", None)]
        print(f"✅ API 已连接，获取到 {len(models)} 个可用模型")
        if models and _config["model"] not in models:
            print(
                f"⚠️  提示：目标模型 '{_config['model']}' "
                "可能不在可用模型列表中。请确认拼写正确。"
            )
    except Exception as e:
        print(f"⚠️ API 连接测试失败: {e}，将直接尝试调用...")

    events: List[Dict[str, Any]] = []
    posts: List[Dict[str, Any]] = []

    try:
        # Generate and save random events.
        if event_count > 0:
            events = generate_events(event_count)
            out_path = WORLD_DIR / "event_library.json"

            if args.append and out_path.exists():
                with open(out_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                events = existing + events
                print(
                    f"\n📎 追加模式：已有 {len(existing)} 条 + "
                    f"新增 {len(events) - len(existing)} 条"
                )

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
            print(f"\n📦 事件库已保存: {out_path} ({len(events)} 条)")

        # Generate and save CC98 posts.
        if cc98_count > 0:
            posts = generate_cc98_posts(cc98_count)
            out_path = WORLD_DIR / "cc98_library.json"

            if args.append and out_path.exists():
                with open(out_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                posts = existing + posts
                print(
                    f"\n📎 追加模式：已有 {len(existing)} 条 + "
                    f"新增 {len(posts) - len(existing)} 条"
                )

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(posts, f, ensure_ascii=False, indent=2)
            print(f"\n📦 CC98 帖子库已保存: {out_path} ({len(posts)} 条)")

    except KeyboardInterrupt:
        print("\n⚠️ 程序被用户中断。")
        # Preserve partial output if the operator interrupts the run.
        if events:
            out_path = WORLD_DIR / "event_library.json"
            if args.append and out_path.exists():
                try:
                    with open(out_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    events = existing + events
                except (OSError, json.JSONDecodeError, TypeError):
                    pass
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
            print(f"📦 已保存 {len(events)} 条事件到 {out_path}")
        if posts:
            out_path = WORLD_DIR / "cc98_library.json"
            if args.append and out_path.exists():
                try:
                    with open(out_path, "r", encoding="utf-8") as f:
                        existing = json.load(f)
                    posts = existing + posts
                except (OSError, json.JSONDecodeError, TypeError):
                    pass
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(posts, f, ensure_ascii=False, indent=2)
            print(f"📦 已保存 {len(posts)} 条帖子到 {out_path}")
        sys.exit(0)

    print("\n🎉 生成完毕！")

if __name__ == "__main__":
    main()
