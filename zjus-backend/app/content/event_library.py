"""
预编译事件库与帖子库加载 / 检索模块

运行时零 LLM 调用，通过标签 + 范围匹配从本地 JSON 库选取内容。
"""

import json
import random
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger(__name__)

# ============================================================
# 世界文件根目录探测
# ============================================================

def _world_dir() -> Path:
    """Docker 优先 /app/world，本地开发回退到相对路径"""
    docker_path = Path("/app/world")
    if docker_path.exists():
        return docker_path
    return Path(__file__).resolve().parent.parent.parent / "world"


# ============================================================
# 事件库
# ============================================================

_event_library: List[Dict[str, Any]] = []


def _load_event_library() -> List[Dict[str, Any]]:
    global _event_library
    if _event_library:
        return _event_library
    path = _world_dir() / "event_library.json"
    if not path.exists():
        logger.warning("event_library.json not found at %s", path)
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            _event_library = json.load(f)
        logger.info("Loaded %d events from event_library.json", len(_event_library))
    except Exception as e:
        logger.error("Failed to load event_library.json: %s", e)
    return _event_library


def pick_random_event(
    sanity: int = 50,
    stress: int = 0,
    seen_ids: Optional[Set[str]] = None,
) -> Optional[Dict[str, Any]]:
    """
    从预编译事件库中按玩家状态范围筛选，随机返回一条未见过的事件。

    返回格式与原 LLM 生成的 event_data 完全一致：
    {"title": ..., "desc": ..., "options": [...]}
    """
    library = _load_event_library()
    if not library:
        return None

    seen = seen_ids or set()
    candidates = []
    for evt in library:
        if evt.get("id") in seen:
            continue
        sr = evt.get("sanity_range", [0, 200])
        tr = evt.get("stress_range", [0, 200])
        if sr[0] <= sanity <= sr[1] and tr[0] <= stress <= tr[1]:
            candidates.append(evt)

    if not candidates:
        # 放宽条件：忽略范围限制，仅去重
        candidates = [e for e in library if e.get("id") not in seen]

    if not candidates:
        return None

    chosen = random.choice(candidates)
    # 返回纯净结构（与 LLM 版兼容）
    return {
        "title": chosen["title"],
        "desc": chosen["desc"],
        "options": chosen["options"],
    }


# ============================================================
# CC98 帖子库
# ============================================================

_cc98_library: List[Dict[str, Any]] = []


def _load_cc98_library() -> List[Dict[str, Any]]:
    global _cc98_library
    if _cc98_library:
        return _cc98_library
    path = _world_dir() / "cc98_library.json"
    if not path.exists():
        logger.warning("cc98_library.json not found at %s", path)
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            _cc98_library = json.load(f)
        logger.info("Loaded %d posts from cc98_library.json", len(_cc98_library))
    except Exception as e:
        logger.error("Failed to load cc98_library.json: %s", e)
    return _cc98_library


def pick_cc98_post(
    effect: str = "neutral",
    trigger: str = "",
) -> Optional[str]:
    """
    从预编译 CC98 帖子库中按 effect 类型随机选取一条。

    Returns:
        帖子内容字符串，或 None（库为空时回退到 LLM）
    """
    library = _load_cc98_library()
    if not library:
        return None

    # 按 effect 过滤
    candidates = [p for p in library if p.get("effect") == effect]
    if not candidates:
        candidates = library  # 兜底：不过滤

    chosen = random.choice(candidates)
    return chosen.get("content", "CC98 帖子加载失败...")
