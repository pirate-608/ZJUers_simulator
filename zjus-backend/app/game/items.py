"""Item catalog and passive bonus helpers."""

import json
import logging
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ALLOWED_ITEM_EFFECTS = {
    "energy",
    "sanity",
    "stress",
    "iq",
    "eq",
    "luck",
    "reputation",
    "efficiency",
}


class ItemCatalog:
    """Loads item economy data from world/items.json."""

    _config: dict[str, Any] = {}
    _items_by_id: dict[str, dict[str, Any]] = {}
    _config_path: Path | None = None

    @staticmethod
    def resolve_config_path(config_path: str | Path | None = None) -> Path:
        if config_path is not None:
            return Path(config_path)

        candidates = [
            Path("world/items.json"),
            Path("/app/world/items.json"),
            Path(__file__).resolve().parent.parent.parent / "world" / "items.json",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def __init__(self):
        if not self._config:
            self.load()

    def load(self, config_path: str | Path | None = None):
        path = self.resolve_config_path(config_path)
        self._config_path = path
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            self._config, self._items_by_id = self._normalize_config(raw)
            logger.info(
                "Item catalog loaded: version=%s items=%s",
                self.version,
                len(self._items_by_id),
            )
        except Exception as exc:
            logger.error("Failed to load item catalog from %s: %s", path, exc)
            self._config = {
                "version": "empty",
                "economy": {"initial_gold": 0, "exam_income": {}},
                "items": [],
            }
            self._items_by_id = {}

    def reload(self, config_path: str | Path | None = None):
        self._config = {}
        self._items_by_id = {}
        self.load(config_path or self._config_path)

    @property
    def version(self) -> str:
        return str(self._config.get("version") or "unknown")

    @property
    def economy(self) -> dict[str, Any]:
        value = self._config.get("economy")
        return value if isinstance(value, dict) else {}

    @property
    def initial_gold(self) -> int:
        return self._to_int(self.economy.get("initial_gold"), 0, minimum=0)

    @property
    def public_items(self) -> list[dict[str, Any]]:
        return [self._public_item(item) for item in self._items_by_id.values()]

    def get_item(self, item_id: str) -> dict[str, Any] | None:
        return self._items_by_id.get(item_id)

    def public_catalog(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "economy": {
                "initial_gold": self.initial_gold,
                "exam_income": self.economy.get("exam_income", {}),
            },
            "items": self.public_items,
        }

    def normalize_state(self, state: dict[str, Any] | None = None) -> dict[str, Any]:
        raw_owned = (state or {}).get("owned")
        owned: list[str] = []
        if isinstance(raw_owned, list):
            for raw_item_id in raw_owned:
                item_id = str(raw_item_id or "").strip()
                if item_id and item_id in self._items_by_id and item_id not in owned:
                    owned.append(item_id)

        updated_at = self._to_int((state or {}).get("updated_at"), 0, minimum=0)
        return {
            "version": 1,
            "owned": owned,
            "updated_at": updated_at or int(time.time()),
        }

    def calculate_bonuses(self, state: dict[str, Any] | None) -> dict[str, int]:
        normalized = self.normalize_state(state)
        bonuses: dict[str, int] = {}
        for item_id in normalized["owned"]:
            item = self.get_item(item_id)
            if not item:
                continue
            effects = item.get("effects", {})
            if not isinstance(effects, dict):
                continue
            for field, value in effects.items():
                if field not in ALLOWED_ITEM_EFFECTS:
                    continue
                delta = self._to_int(value, 0, minimum=-50, maximum=50)
                if delta:
                    bonuses[field] = bonuses.get(field, 0) + delta
        return bonuses

    def state_payload(self, state: dict[str, Any] | None) -> dict[str, Any]:
        normalized = self.normalize_state(state)
        return {
            **self.public_catalog(),
            "owned": normalized["owned"],
            "bonuses": self.calculate_bonuses(normalized),
            "updated_at": normalized["updated_at"],
        }

    def apply_bonuses_to_stats(
        self, stats: dict[str, Any], state: dict[str, Any] | None
    ) -> dict[str, Any]:
        effective = dict(stats)
        bonuses = self.calculate_bonuses(state)
        for field, delta in bonuses.items():
            current = self._to_number(effective.get(field), 0)
            effective[field] = self._clamp_effective_stat(field, current + delta)
        effective["item_bonuses"] = bonuses
        return effective

    def calculate_exam_gold(self, term_gpa: float, failed_count: int) -> int:
        cfg = self.economy.get("exam_income")
        cfg = cfg if isinstance(cfg, dict) else {}
        base = self._to_int(cfg.get("base"), 0)
        gpa_multiplier = self._to_int(cfg.get("gpa_multiplier"), 0)
        pass_all_bonus = self._to_int(cfg.get("pass_all_bonus"), 0)
        failed_penalty = self._to_int(cfg.get("failed_penalty_per_course"), 0)
        minimum = self._to_int(cfg.get("min"), 0)
        maximum = self._to_int(cfg.get("max"), 999999, minimum=minimum)
        raw = int(round(base + term_gpa * gpa_multiplier))
        if failed_count <= 0:
            raw += pass_all_bonus
        else:
            raw -= failed_count * failed_penalty
        return max(minimum, min(maximum, raw))

    def build_buy_state(
        self, current_state: dict[str, Any] | None, item_id: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
        item = self.get_item(item_id)
        if item is None:
            return None, None, "未知道具"
        state = self.normalize_state(current_state)
        if item_id in state["owned"]:
            return None, item, "已经拥有该道具"
        state["owned"].append(item_id)
        state["updated_at"] = int(time.time())
        return state, item, None

    def build_sell_state(
        self, current_state: dict[str, Any] | None, item_id: str
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None, str | None]:
        item = self.get_item(item_id)
        if item is None:
            return None, None, "未知道具"
        state = self.normalize_state(current_state)
        if item_id not in state["owned"]:
            return None, item, "尚未拥有该道具"
        state["owned"] = [
            owned_id for owned_id in state["owned"] if owned_id != item_id
        ]
        state["updated_at"] = int(time.time())
        return state, item, None

    def _normalize_config(
        self, raw: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        if not isinstance(raw, dict):
            raise ValueError("items config must be an object")
        raw_items = raw.get("items")
        if not isinstance(raw_items, list):
            raise ValueError("items config must contain an items array")

        items_by_id: dict[str, dict[str, Any]] = {}
        normalized_items: list[dict[str, Any]] = []
        for raw_item in raw_items:
            item = self._normalize_item(raw_item)
            item_id = item["id"]
            if item_id in items_by_id:
                raise ValueError(f"duplicate item id: {item_id}")
            items_by_id[item_id] = item
            normalized_items.append(item)

        economy = raw.get("economy")
        config = {
            "version": str(raw.get("version") or "1.0.0"),
            "economy": economy if isinstance(economy, dict) else {},
            "items": normalized_items,
        }
        return config, items_by_id

    def _normalize_item(self, raw_item: Any) -> dict[str, Any]:
        if not isinstance(raw_item, dict):
            raise ValueError("item must be an object")

        item_id = str(raw_item.get("id") or "").strip()
        if not item_id:
            raise ValueError("item id is required")
        price = self._to_int(raw_item.get("price"), 0, minimum=0)
        sell_price_raw = raw_item.get("sell_price")
        sell_price = (
            self._to_int(sell_price_raw, price // 2, minimum=0)
            if sell_price_raw is not None
            else price // 2
        )
        effects = raw_item.get("effects")
        effects = effects if isinstance(effects, dict) else {}
        normalized_effects: dict[str, int] = {}
        for field, raw_delta in effects.items():
            if field not in ALLOWED_ITEM_EFFECTS:
                raise ValueError(f"unsupported item effect field: {field}")
            delta = self._to_int(raw_delta, 0, minimum=-50, maximum=50)
            if delta:
                normalized_effects[field] = delta

        tags = raw_item.get("tags")
        tag_list = [
            str(tag).strip()
            for tag in tags
            if str(tag).strip()
        ] if isinstance(tags, list) else []

        return {
            "id": item_id,
            "name": str(raw_item.get("name") or item_id),
            "category": str(raw_item.get("category") or "通用"),
            "description": str(raw_item.get("description") or ""),
            "price": price,
            "sell_price": sell_price,
            "tags": tag_list,
            "effects": normalized_effects,
        }

    @staticmethod
    def _public_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "description": item["description"],
            "price": item["price"],
            "sell_price": item["sell_price"],
            "tags": item["tags"],
            "effects": item["effects"],
        }

    @staticmethod
    def _to_int(
        value: Any,
        default: int,
        *,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        if minimum is not None:
            parsed = max(minimum, parsed)
        if maximum is not None:
            parsed = min(maximum, parsed)
        return parsed

    @staticmethod
    def _to_number(value: Any, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp_effective_stat(field: str, value: float) -> int | float:
        bounded_fields = {
            "energy",
            "sanity",
            "stress",
            "iq",
            "eq",
            "luck",
            "reputation",
            "efficiency",
        }
        if field in bounded_fields:
            return int(max(0, min(300, round(value))))
        return value


items = ItemCatalog()
