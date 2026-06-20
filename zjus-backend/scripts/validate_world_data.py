"""Validate gameplay world data and generated stat metadata."""

# ruff: noqa: E402, I001

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.game.items import ItemCatalog  # noqa: E402
from app.game.stat_definitions import StatDefinitions  # noqa: E402
from sync_stat_definitions import OUTPUT_PATH, build_typescript  # noqa: E402

WORLD_DIR = BACKEND_ROOT / "world"


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _validate_items(registry: StatDefinitions, errors: list[str]) -> None:
    path = WORLD_DIR / "items.json"
    raw = _load_json(path)
    catalog = ItemCatalog()
    try:
        _, items_by_id = catalog._normalize_config(raw)
    except Exception as exc:
        errors.append(f"{path.relative_to(REPO_ROOT)}: {exc}")
        return
    allowed = registry.item_effect_fields
    for item_id, item in items_by_id.items():
        for field in item.get("effects", {}):
            if field not in allowed:
                errors.append(f"items.{item_id}: unsupported effect field {field}")


def _validate_event_library(registry: StatDefinitions, errors: list[str]) -> None:
    path = WORLD_DIR / "event_library.json"
    if not path.exists():
        return
    raw = _load_json(path)
    if not isinstance(raw, list):
        errors.append(f"{path.relative_to(REPO_ROOT)}: expected a list")
        return
    allowed = registry.event_effect_fields
    for index, event in enumerate(raw):
        options = event.get("options") if isinstance(event, dict) else None
        if not isinstance(options, list):
            errors.append(f"event_library[{index}]: missing options list")
            continue
        for option_index, option in enumerate(options):
            effects = option.get("effects") if isinstance(option, dict) else None
            if not isinstance(effects, dict):
                errors.append(
                    f"event_library[{index}].options[{option_index}]: missing effects"
                )
                continue
            for field in effects:
                if field == "desc":
                    continue
                if field not in allowed:
                    errors.append(
                        f"event_library[{index}].options[{option_index}]: "
                        f"unsupported effect field {field}"
                    )


def _validate_generated_frontend(errors: list[str]) -> None:
    expected = build_typescript()
    actual = OUTPUT_PATH.read_text(encoding="utf-8") if OUTPUT_PATH.exists() else ""
    if actual != expected:
        errors.append(
            f"{OUTPUT_PATH.relative_to(REPO_ROOT)} is out of date; run "
            "python scripts/sync_stat_definitions.py --write"
        )


def main() -> int:
    errors: list[str] = []
    try:
        registry = StatDefinitions(WORLD_DIR / "stat_definitions.json")
    except Exception as exc:
        print(f"stat_definitions.json: {exc}", file=sys.stderr)
        return 1

    for filename in ("game_balance.json", "items.json"):
        try:
            _load_json(WORLD_DIR / filename)
        except Exception as exc:
            errors.append(f"world/{filename}: {exc}")

    _validate_items(registry, errors)
    _validate_event_library(registry, errors)
    _validate_generated_frontend(errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("world data validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
