"""Create a stat definition template and maintenance checklist."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = BACKEND_ROOT / "world" / "stat_definitions.json"


def _load_config() -> dict[str, Any]:
    with open(WORLD_PATH, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict):
        raise ValueError("stat_definitions.json must be an object")
    return raw


def _write_config(config: dict[str, Any]) -> None:
    WORLD_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _template(args: argparse.Namespace) -> dict[str, Any]:
    stat_id = args.stat_id.strip()
    if not re.fullmatch(r"[a-z][a-z0-9_]*", stat_id):
        raise ValueError("stat id must match [a-z][a-z0-9_]*")
    return {
        "id": stat_id,
        "label": args.label or stat_id,
        "icon": args.icon or "✨",
        "default": args.default,
        "min": args.minimum,
        "max": args.maximum,
        "positive_endpoint": args.positive_endpoint,
        "allocatable": args.allocatable,
        "allow_item_effect": args.allow_item_effect,
        "allow_event_effect": args.allow_event_effect,
        "llm_context": args.llm_context,
        "show_in_character_create": args.allocatable,
        "show_in_hud": args.show_in_hud,
    }


def _print_checklist(stat_id: str) -> None:
    print("\nManual review checklist:")
    print("- Run: python scripts/sync_stat_definitions.py --write")
    print("- Run: python scripts/validate_world_data.py")
    print("- If allocatable, regenerate OpenAPI and update frontend tests")
    print("- Check HUD/feedback layout if show_in_hud is true")
    print("- Check LLM prompts and world event/item data if effects are enabled")
    print(f"- Search for '{stat_id}' to confirm no bespoke behavior is needed")


def add_stat(args: argparse.Namespace) -> int:
    config = _load_config()
    stats = config.get("stats")
    if not isinstance(stats, list):
        raise ValueError("stat_definitions.json must contain a stats array")
    stat = _template(args)
    exists = any(
        existing.get("id") == stat["id"]
        for existing in stats
        if isinstance(existing, dict)
    )
    if exists:
        raise ValueError(f"stat already exists: {stat['id']}")

    if args.write:
        stats.append(stat)
        _write_config(config)
        print(f"added {stat['id']} to {WORLD_PATH}")
    else:
        print(json.dumps(stat, ensure_ascii=False, indent=2))
        print("\nDry run only. Add --write to update stat_definitions.json.")
    _print_checklist(stat["id"])
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    add = subparsers.add_parser("add", help="prepare a new stat definition")
    add.add_argument("stat_id")
    add.add_argument("--label", default="")
    add.add_argument("--icon", default="")
    add.add_argument("--default", type=int, default=0)
    add.add_argument("--minimum", type=int, default=0)
    add.add_argument("--maximum", type=int, default=200)
    add.add_argument(
        "--positive-endpoint",
        choices=["max", "min", "none"],
        default="max",
    )
    add.add_argument("--allocatable", action="store_true")
    add.add_argument("--allow-item-effect", action="store_true")
    add.add_argument("--allow-event-effect", action="store_true")
    add.add_argument("--llm-context", action="store_true")
    add.add_argument("--show-in-hud", action="store_true")
    add.add_argument("--write", action="store_true")
    add.set_defaults(func=add_stat)

    args = parser.parse_args()
    try:
        return args.func(args)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
