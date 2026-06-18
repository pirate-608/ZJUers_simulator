import json
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from app.game.engine import GameEngine
from app.game.items import ItemCatalog
from app.schemas.game_state import PlayerStats
from app.services.save_service import SaveService


def _test_config_path(name: str) -> Path:
    root = Path("..") / "pytest-temp" / "item-configs"
    root.mkdir(parents=True, exist_ok=True)
    return root / name


def _write_items_config(path: Path, items_payload: list[dict], economy=None):
    path.write_text(
        json.dumps(
            {
                "version": "test",
                "economy": economy or {"initial_gold": 50},
                "items": items_payload,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_item_catalog_loads_valid_items_and_default_sell_price():
    config_path = _test_config_path("valid-items.json")
    _write_items_config(
        config_path,
        [
            {
                "id": "planner",
                "name": "Planner",
                "price": 80,
                "tags": ["study"],
                "effects": {"iq": 4, "stress": -2},
            }
        ],
        economy={
            "initial_gold": 120,
            "exam_income": {
                "base": 10,
                "gpa_multiplier": 30,
                "pass_all_bonus": 20,
                "failed_penalty_per_course": 15,
                "min": 0,
                "max": 200,
            },
        },
    )

    catalog = ItemCatalog()
    catalog.load(config_path)

    item = catalog.get_item("planner")
    assert item is not None
    assert item["sell_price"] == 40
    assert catalog.initial_gold == 120
    assert catalog.calculate_exam_gold(4.0, 0) == 150


def test_item_catalog_falls_back_to_empty_when_config_is_invalid():
    config_path = _test_config_path("invalid-items.json")
    _write_items_config(
        config_path,
        [
            {"id": "dup", "name": "A", "price": 10, "effects": {"iq": 1}},
            {"id": "dup", "name": "B", "price": 10, "effects": {"iq": 1}},
        ],
    )

    catalog = ItemCatalog()
    catalog.load(config_path)

    assert catalog.public_items == []
    assert catalog.initial_gold == 0


class _Snapshot:
    def __init__(self, stats: dict):
        self.stats = PlayerStats.from_redis(stats)
        self.courses = {}
        self.course_states = {}
        self.achievements = []


class _ItemRepo:
    def __init__(self):
        self.items_state = {"version": 1, "owned": [], "updated_at": 1}
        self.stats = {
            "username": "tester",
            "semester": "大一秋冬",
            "semester_idx": 1,
            "energy": 100,
            "sanity": 80,
            "stress": 0,
            "iq": 100,
            "eq": 100,
            "luck": 50,
            "gold": 100,
        }

    async def get_items_state(self):
        return self.items_state

    async def set_items_state(self, state):
        self.items_state = state

    async def get_snapshot(self):
        return _Snapshot(self.stats)

    async def update_stat_safe(self, field, delta, min_val=0, max_val=200):
        current = int(self.stats.get(field, 0))
        new_value = max(min_val, min(max_val, current + int(delta)))
        self.stats[field] = new_value
        return new_value


@pytest.fixture
def item_catalog():
    config_path = _test_config_path("engine-items.json")
    _write_items_config(
        config_path,
        [
            {
                "id": "planner",
                "name": "Planner",
                "price": 80,
                "sell_price": 30,
                "effects": {"iq": 4, "stress": -2},
            }
        ],
    )
    catalog = ItemCatalog()
    catalog.load(config_path)
    return catalog


@pytest.mark.asyncio
async def test_engine_buys_and_sells_items_without_writing_passive_stats(
    monkeypatch, item_catalog
):
    monkeypatch.setattr("app.game.engine.items", item_catalog)
    repo = _ItemRepo()
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore[arg-type]
    engine.is_running = True
    engine._push_update = AsyncMock()
    engine._push_items_state = AsyncMock()
    engine._emit_feedback = AsyncMock()
    engine.emit = AsyncMock()

    await engine._handle_item_buy({"item_id": "planner"})

    assert repo.stats["gold"] == 20
    assert repo.stats["iq"] == 100
    assert repo.items_state["owned"] == ["planner"]
    effective = await engine._effective_stats(repo.stats)
    assert effective["iq"] == 104
    assert effective["stress"] == 0

    await engine._handle_item_sell({"item_id": "planner"})

    assert repo.stats["gold"] == 50
    assert repo.stats["iq"] == 100
    assert repo.items_state["owned"] == []


@pytest.mark.asyncio
async def test_engine_rejects_duplicate_buy_and_insufficient_gold(
    monkeypatch, item_catalog
):
    monkeypatch.setattr("app.game.engine.items", item_catalog)
    repo = _ItemRepo()
    repo.items_state["owned"] = ["planner"]
    repo.stats["gold"] = 10
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore[arg-type]
    engine.is_running = True
    engine.emit = AsyncMock()

    await engine._handle_item_buy({"item_id": "planner"})

    engine.emit.assert_awaited()
    assert repo.stats["gold"] == 10
    assert repo.items_state["owned"] == ["planner"]


@pytest.mark.asyncio
async def test_save_service_loads_items_state_into_redis():
    save = Mock()
    save.stats_data = {"username": "tester", "semester_idx": 1, "gold": 70}
    save.courses_data = {}
    save.course_states_data = {}
    save.achievements_data = []
    save.dingtalk_data = {}
    save.items_data = {"version": 1, "owned": ["qiushi_planner"], "updated_at": 99}

    result = Mock()
    result.scalars.return_value.first.return_value = save
    db = Mock()
    db.execute = AsyncMock(return_value=result)
    db.rollback = AsyncMock()
    repo = Mock()
    repo.set_game_data = AsyncMock()
    repo.set_dingtalk_state = AsyncMock()

    loaded = await SaveService.load_from_db("1", repo, db)

    assert loaded is True
    kwargs = repo.set_game_data.await_args.kwargs
    assert kwargs["items_state"]["owned"] == ["qiushi_planner"]
    repo.set_dingtalk_state.assert_awaited()
