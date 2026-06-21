"""Player-facing text normalization and prompt-safety checks.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
Usernames enter auth, persistence, and LLM prompts, so this module centralizes
normalization, reserved-word rejection, and prompt-safe fallbacks.
"""

import re
import unicodedata
from typing import Any

USERNAME_MAX_LENGTH = 24
SAFE_USERNAME_FALLBACK = "同学"

_USERNAME_SPACE_RE = re.compile(r" {2,}")
_USERNAME_SEPARATOR_RE = re.compile(r"[\s_\-·]+")

_USERNAME_ALLOWED_PUNCTUATION = {" ", "_", "-", "·"}
_PROMPT_INJECTION_KEYWORDS = {
    "assistant",
    "developer",
    "ignore",
    "instruction",
    "jailbreak",
    "override",
    "prompt",
    "system",
    "tool",
    "系统",
    "提示词",
    "开发者",
    "忽略",
    "越狱",
    "覆盖",
    "指令",
    "规则",
}


def normalize_username(value: Any) -> str:
    """Normalize raw username input before validation or prompt use."""
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value)).strip()
    return _USERNAME_SPACE_RE.sub(" ", normalized)


def _has_forbidden_codepoint(value: str) -> bool:
    for char in value:
        category = unicodedata.category(char)
        if category.startswith("C"):
            return True
        if char.isspace() and char != " ":
            return True
    return False


def _is_allowed_username_char(char: str) -> bool:
    if char in _USERNAME_ALLOWED_PUNCTUATION:
        return True
    category = unicodedata.category(char)
    return category[0] in {"L", "N"}


def validate_username(value: Any) -> tuple[bool, str, str | None]:
    """Validate a username and return normalized value plus rejection reason."""
    username = normalize_username(value)
    if not username:
        return False, username, "用户名不能为空"
    if len(username) > USERNAME_MAX_LENGTH:
        return False, username, f"用户名不能超过 {USERNAME_MAX_LENGTH} 个字符"
    if _has_forbidden_codepoint(username):
        return False, username, "用户名不能包含控制字符或隐藏字符"
    if not all(_is_allowed_username_char(char) for char in username):
        return (
            False,
            username,
            "用户名只能包含中英文、数字、空格、下划线、连字符或间隔号",
        )

    folded = username.casefold()
    compact = _USERNAME_SEPARATOR_RE.sub("", folded)
    for keyword in _PROMPT_INJECTION_KEYWORDS:
        if keyword in folded or keyword in compact:
            return False, username, "用户名包含保留词或疑似提示词注入内容"

    return True, username, None


def is_username_safe(value: Any) -> bool:
    """Return whether a username is safe for auth and prompt contexts."""
    return validate_username(value)[0]


def safe_username_for_prompt(value: Any) -> str:
    """Return a prompt-safe username, falling back for unsafe legacy values."""
    is_safe, username, _reason = validate_username(value)
    return username if is_safe else SAFE_USERNAME_FALLBACK
