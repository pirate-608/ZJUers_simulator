"""Admin item-catalog validation and atomic publishing service.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
This module converts SQLAdmin form submissions into validated `items.json`
documents, writes them atomically, and exposes audit-restore helpers.
"""

import copy
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.game.stat_definitions import StatDefinition, stat_definitions
from app.models.admin import AdminAuditLog

ReplaceFunc = Callable[
    [str | bytes | os.PathLike[str], str | bytes | os.PathLike[str]], None
]

_ITEM_ID_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ECONOMY_EXAM_FIELDS: tuple[str, ...] = (
    "base",
    "gpa_multiplier",
    "pass_all_bonus",
    "failed_penalty_per_course",
    "min",
    "max",
)


class ItemConfigError(ValueError):
    """Raised when an admin-submitted item config is invalid."""


@dataclass(frozen=True)
class ItemEffectField:
    """Editable effect field derived from `world/stat_definitions.json`."""

    id: str
    label: str
    icon: str
    minimum: int = -50
    maximum: int = 50


@dataclass(frozen=True)
class ItemAuditSnapshot:
    """Previous item config recovered from an audit-log entry."""

    log_id: int
    old_config: dict[str, Any]


def load_items_config(path: Path) -> dict[str, Any]:
    """Read and validate `world/items.json` from disk."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ItemConfigError(f"items.json 不是合法 JSON：{exc}") from exc
    return normalize_items_config(raw)


def build_item_effect_fields() -> list[ItemEffectField]:
    """Return effect fields shown by the admin item editor."""
    allowed = stat_definitions.item_effect_fields
    return [
        ItemEffectField(id=stat.id, label=stat.label, icon=stat.icon)
        for stat in stat_definitions.stats
        if stat.id in allowed
    ]


def config_to_form_data(config: Mapping[str, Any]) -> dict[str, str]:
    """Flatten an item config into HTML form field values."""
    normalized = normalize_items_config(config)
    form: dict[str, str] = {
        "version": str(normalized["version"]),
        "description": str(normalized.get("description", "")),
        "economy__initial_gold": str(normalized["economy"]["initial_gold"]),
        "item_count": str(len(normalized["items"])),
    }
    exam_income = normalized["economy"]["exam_income"]
    for field in _ECONOMY_EXAM_FIELDS:
        form[f"economy__exam_income__{field}"] = str(exam_income[field])

    effect_fields = build_item_effect_fields()
    for index, item in enumerate(normalized["items"]):
        prefix = f"item__{index}"
        form[f"{prefix}__id"] = str(item["id"])
        form[f"{prefix}__name"] = str(item["name"])
        form[f"{prefix}__category"] = str(item["category"])
        form[f"{prefix}__description"] = str(item["description"])
        form[f"{prefix}__price"] = str(item["price"])
        form[f"{prefix}__sell_price"] = str(item["sell_price"])
        form[f"{prefix}__tags"] = ", ".join(item["tags"])
        for field in effect_fields:
            value = item["effects"].get(field.id, 0)
            form[f"{prefix}__effect__{field.id}"] = str(value)

    _fill_new_item_defaults(form, effect_fields)
    return form


def build_item_rows(config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Return existing item rows for the SQLAdmin template."""
    normalized = normalize_items_config(config)
    return [
        {"index": index, "item": item}
        for index, item in enumerate(normalized["items"])
    ]


def build_config_from_form(
    original_config: Mapping[str, Any],
    form_data: Mapping[str, Any],
) -> dict[str, Any]:
    """Build and validate a complete item config from submitted form values."""
    normalized_original = normalize_items_config(original_config)
    errors: list[str] = []

    try:
        next_config: dict[str, Any] = {
            "version": _parse_text(form_data, "version", "版本号", 40),
            "description": _parse_text(
                form_data,
                "description",
                "说明",
                240,
                required=False,
            ),
            "economy": _build_economy_from_form(form_data),
            "items": [],
        }
    except ItemConfigError as exc:
        errors.append(str(exc))
        next_config = copy.deepcopy(normalized_original)

    for index, _item in enumerate(normalized_original["items"]):
        prefix = f"item__{index}"
        if _checkbox_enabled(form_data.get(f"{prefix}__delete")):
            continue
        try:
            next_config["items"].append(_build_item_from_form(form_data, prefix))
        except ItemConfigError as exc:
            errors.append(str(exc))

    if _has_new_item(form_data):
        try:
            next_config["items"].append(_build_item_from_form(form_data, "new"))
        except ItemConfigError as exc:
            errors.append(str(exc))

    if errors:
        raise ItemConfigError("；".join(errors))
    return normalize_items_config(next_config)


def normalize_items_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and normalize the full item catalog config."""
    if not isinstance(config, Mapping):
        raise ItemConfigError("items.json 根节点必须是对象")

    version = _normalize_text(config.get("version"), "版本号", 40)
    description = _normalize_text(
        config.get("description", ""),
        "说明",
        240,
        required=False,
    )
    economy = _normalize_economy(config.get("economy"))

    raw_items = config.get("items")
    if not isinstance(raw_items, list):
        raise ItemConfigError("items.json 必须包含 items 数组")

    seen_ids: set[str] = set()
    normalized_items: list[dict[str, Any]] = []
    for index, raw_item in enumerate(raw_items, start=1):
        item = _normalize_item(raw_item, label=f"道具 {index}")
        item_id = item["id"]
        if item_id in seen_ids:
            raise ItemConfigError(f"道具 ID 重复：{item_id}")
        seen_ids.add(item_id)
        normalized_items.append(item)

    return {
        "version": version,
        "description": description,
        "economy": economy,
        "items": normalized_items,
    }


def summarize_items_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Return a compact audit summary for an item config."""
    normalized = normalize_items_config(config)
    categories = sorted({item["category"] for item in normalized["items"]})
    return {
        "version": normalized["version"],
        "item_count": len(normalized["items"]),
        "initial_gold": normalized["economy"]["initial_gold"],
        "exam_income": normalized["economy"]["exam_income"],
        "categories": categories,
    }


def diff_item_configs(
    old_config: Mapping[str, Any],
    new_config: Mapping[str, Any],
) -> list[str]:
    """Return item/economy paths whose values changed between two configs."""
    old = normalize_items_config(old_config)
    new = normalize_items_config(new_config)
    changed: list[str] = []

    for field in ("version", "description"):
        if old.get(field) != new.get(field):
            changed.append(field)
    if old["economy"]["initial_gold"] != new["economy"]["initial_gold"]:
        changed.append("economy.initial_gold")
    for field in _ECONOMY_EXAM_FIELDS:
        if (
            old["economy"]["exam_income"][field]
            != new["economy"]["exam_income"][field]
        ):
            changed.append(f"economy.exam_income.{field}")

    old_items = {item["id"]: item for item in old["items"]}
    new_items = {item["id"]: item for item in new["items"]}
    for item_id in sorted(old_items.keys() - new_items.keys()):
        changed.append(f"items.{item_id}.deleted")
    for item_id in sorted(new_items.keys() - old_items.keys()):
        changed.append(f"items.{item_id}.created")
    for item_id in sorted(old_items.keys() & new_items.keys()):
        old_item = old_items[item_id]
        new_item = new_items[item_id]
        for field in ("name", "category", "description", "price", "sell_price"):
            if old_item[field] != new_item[field]:
                changed.append(f"items.{item_id}.{field}")
        if old_item["tags"] != new_item["tags"]:
            changed.append(f"items.{item_id}.tags")
        effect_ids = set(old_item["effects"]) | set(new_item["effects"])
        for effect_id in sorted(effect_ids):
            if old_item["effects"].get(effect_id, 0) != new_item["effects"].get(
                effect_id,
                0,
            ):
                changed.append(f"items.{item_id}.effects.{effect_id}")
    return changed


def write_items_config_atomic(
    path: Path,
    config: Mapping[str, Any],
    replace_func: ReplaceFunc = os.replace,
) -> None:
    """Validate and atomically replace `items.json` on disk."""
    normalized = normalize_items_config(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        replace_func(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def publish_items_config(
    path: Path,
    config: Mapping[str, Any],
    reload_func: Callable[[str], Any],
) -> None:
    """Write an item config and immediately reload runtime readers."""
    write_items_config_atomic(path, config)
    reload_func(str(path))


def latest_items_update_snapshot(session: Session) -> ItemAuditSnapshot | None:
    """Return the latest restorable pre-update item config from audit logs."""
    log = (
        session.query(AdminAuditLog)
        .filter(
            AdminAuditLog.action == "items_update",
            AdminAuditLog.target_type == "items",
        )
        .order_by(AdminAuditLog.id.desc())
        .first()
    )
    if not log or not log.details:
        return None
    old_config = log.details.get("old_config")
    if not isinstance(old_config, dict):
        return None
    return ItemAuditSnapshot(
        log_id=int(log.id),
        old_config=normalize_items_config(old_config),
    )


def _build_economy_from_form(form_data: Mapping[str, Any]) -> dict[str, Any]:
    exam_income = {
        field: _parse_int(
            form_data,
            f"economy__exam_income__{field}",
            f"期末金币 {field}",
            0,
            100_000,
        )
        for field in _ECONOMY_EXAM_FIELDS
    }
    return {
        "initial_gold": _parse_int(
            form_data,
            "economy__initial_gold",
            "初始金币",
            0,
            100_000,
        ),
        "exam_income": exam_income,
    }


def _build_item_from_form(
    form_data: Mapping[str, Any],
    prefix: str,
) -> dict[str, Any]:
    effects: dict[str, int] = {}
    for field in build_item_effect_fields():
        name = f"{prefix}__effect__{field.id}"
        delta = _parse_int(
            form_data,
            name,
            f"{field.label} 加成",
            field.minimum,
            field.maximum,
            default=0,
        )
        if delta:
            effects[field.id] = delta
    price = _parse_int(form_data, f"{prefix}__price", "价格", 1, 999_999)

    return {
        "id": _parse_text(form_data, f"{prefix}__id", "道具 ID", 64),
        "name": _parse_text(form_data, f"{prefix}__name", "道具名称", 80),
        "category": _parse_text(form_data, f"{prefix}__category", "分类", 40),
        "description": _parse_text(
            form_data,
            f"{prefix}__description",
            "说明",
            280,
        ),
        "price": price,
        "sell_price": _parse_int(
            form_data,
            f"{prefix}__sell_price",
            "出售价格",
            0,
            999_999,
            default=price // 2,
        ),
        "tags": _parse_tags(str(form_data.get(f"{prefix}__tags") or "")),
        "effects": effects,
    }


def _normalize_economy(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ItemConfigError("economy 必须是对象")
    exam_income_raw = raw.get("exam_income")
    if not isinstance(exam_income_raw, Mapping):
        raise ItemConfigError("economy.exam_income 必须是对象")

    exam_income = {
        field: _normalize_int(
            exam_income_raw.get(field),
            f"economy.exam_income.{field}",
            0,
            100_000,
        )
        for field in _ECONOMY_EXAM_FIELDS
    }
    if exam_income["min"] > exam_income["max"]:
        raise ItemConfigError("期末金币 min 不能大于 max")
    return {
        "initial_gold": _normalize_int(
            raw.get("initial_gold"),
            "economy.initial_gold",
            0,
            100_000,
        ),
        "exam_income": exam_income,
    }


def _normalize_item(raw_item: Any, label: str) -> dict[str, Any]:
    if not isinstance(raw_item, Mapping):
        raise ItemConfigError(f"{label} 必须是对象")

    item_id = _normalize_text(raw_item.get("id"), f"{label} ID", 64)
    if not _ITEM_ID_RE.fullmatch(item_id):
        raise ItemConfigError(f"{label} ID 必须是 snake_case 小写标识")

    price = _normalize_int(raw_item.get("price"), f"{label} 价格", 1, 999_999)
    sell_price = _normalize_int(
        raw_item.get("sell_price", price // 2),
        f"{label} 出售价格",
        0,
        999_999,
    )
    if sell_price > price:
        raise ItemConfigError(f"{label} 出售价格不能高于购买价格")

    effects = _normalize_effects(raw_item.get("effects"), label)
    if not effects:
        raise ItemConfigError(f"{label} 至少需要一个非 0 加成")

    return {
        "id": item_id,
        "name": _normalize_text(raw_item.get("name"), f"{label} 名称", 80),
        "category": _normalize_text(raw_item.get("category"), f"{label} 分类", 40),
        "description": _normalize_text(
            raw_item.get("description"),
            f"{label} 说明",
            280,
        ),
        "price": price,
        "sell_price": sell_price,
        "tags": _normalize_tags(raw_item.get("tags"), label),
        "effects": effects,
    }


def _normalize_effects(raw_effects: Any, label: str) -> dict[str, int]:
    if not isinstance(raw_effects, Mapping):
        raise ItemConfigError(f"{label} effects 必须是对象")
    allowed = stat_definitions.item_effect_fields
    normalized: dict[str, int] = {}
    for raw_field, raw_delta in raw_effects.items():
        field = str(raw_field).strip()
        if field not in allowed:
            raise ItemConfigError(f"{label} 不支持道具加成字段：{field}")
        stat = _stat(field)
        delta = _normalize_int(
            raw_delta,
            f"{label} {stat.label} 加成",
            -50,
            50,
        )
        if delta:
            normalized[field] = delta
    return dict(sorted(normalized.items()))


def _normalize_tags(raw_tags: Any, label: str) -> list[str]:
    if raw_tags is None:
        return []
    if not isinstance(raw_tags, list):
        raise ItemConfigError(f"{label} tags 必须是数组")
    return _validate_tags([str(tag).strip() for tag in raw_tags])


def _parse_tags(raw_tags: str) -> list[str]:
    pieces = re.split(r"[,，\n]", raw_tags)
    return _validate_tags([piece.strip() for piece in pieces])


def _validate_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        if not tag:
            continue
        if len(tag) > 20:
            raise ItemConfigError("标签不能超过 20 个字符")
        if tag not in cleaned:
            cleaned.append(tag)
    if len(cleaned) > 8:
        raise ItemConfigError("单个道具最多 8 个标签")
    return cleaned


def _parse_text(
    form_data: Mapping[str, Any],
    name: str,
    label: str,
    max_length: int,
    *,
    required: bool = True,
) -> str:
    if name not in form_data:
        raise ItemConfigError(f"缺少字段：{label}")
    return _normalize_text(
        form_data.get(name),
        label,
        max_length,
        required=required,
    )


def _normalize_text(
    raw_value: Any,
    label: str,
    max_length: int,
    *,
    required: bool = True,
) -> str:
    value = str(raw_value or "").strip()
    if required and not value:
        raise ItemConfigError(f"{label} 不能为空")
    if len(value) > max_length:
        raise ItemConfigError(f"{label} 不能超过 {max_length} 个字符")
    return value


def _parse_int(
    form_data: Mapping[str, Any],
    name: str,
    label: str,
    minimum: int,
    maximum: int,
    *,
    default: int | None = None,
) -> int:
    if name not in form_data:
        if default is not None:
            return default
        raise ItemConfigError(f"缺少字段：{label}")
    raw_value = form_data.get(name)
    if (raw_value is None or str(raw_value).strip() == "") and default is not None:
        return default
    return _normalize_int(raw_value, label, minimum, maximum)


def _normalize_int(
    raw_value: Any,
    label: str,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(str(raw_value).strip())
    except (TypeError, ValueError) as exc:
        raise ItemConfigError(f"{label} 必须是整数") from exc
    if value < minimum:
        raise ItemConfigError(f"{label} 不能小于 {minimum}")
    if value > maximum:
        raise ItemConfigError(f"{label} 不能大于 {maximum}")
    return value


def _has_new_item(form_data: Mapping[str, Any]) -> bool:
    return any(
        str(form_data.get(f"new__{field}") or "").strip()
        for field in ("id", "name", "category", "description", "price", "tags")
    )


def _checkbox_enabled(value: Any) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def _fill_new_item_defaults(
    form: dict[str, str],
    effect_fields: list[ItemEffectField],
) -> None:
    defaults = {
        "new__id": "",
        "new__name": "",
        "new__category": "",
        "new__description": "",
        "new__price": "",
        "new__sell_price": "",
        "new__tags": "",
    }
    form.update(defaults)
    for field in effect_fields:
        form[f"new__effect__{field.id}"] = "0"


def _stat(stat_id: str) -> StatDefinition:
    stat = stat_definitions.by_id.get(stat_id)
    if stat is None:
        raise ItemConfigError(f"未知属性：{stat_id}")
    return stat
