"""Runtime hardening tests for the real-time game engine."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.game.balance import balance
from app.game.engine import GameEngine


class _Snapshot:
    """Minimal game-state snapshot used by engine unit tests."""

    def __init__(self, stats: dict, courses=None, course_states=None):
        self.stats = SimpleNamespace(model_dump=lambda: dict(stats))
        self.courses = courses or {}
        self.course_states = course_states or {}


@pytest.mark.asyncio
async def test_paused_engine_rejects_gameplay_actions_without_mutating_state():
    repo = Mock()
    repo.set_course_state = AsyncMock()
    repo.get_snapshot = AsyncMock(return_value=_Snapshot({"exam_completed": 0}))
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore[arg-type]
    engine.is_running = False
    engine.emit = AsyncMock()
    engine._track_task = Mock()
    engine._handle_item_buy = AsyncMock()
    engine._handle_item_sell = AsyncMock()
    engine._handle_final_exam = AsyncMock()
    engine._handle_event_choice = AsyncMock()

    for action in (
        {"action": "relax", "target": "walk"},
        {"action": "exam"},
        {"action": "event_choice", "choice_id": "A"},
        {"action": "dingtalk_reply", "contact_id": "c1", "option_id": "opt_1"},
        {"action": "item_buy", "item_id": "planner"},
        {"action": "item_sell", "item_id": "planner"},
        {"action": "change_course_state", "target": "CS1001", "value": 2},
    ):
        await engine.process_action(action)

    repo.set_course_state.assert_not_awaited()
    engine._track_task.assert_not_called()
    engine._handle_item_buy.assert_not_awaited()
    engine._handle_item_sell.assert_not_awaited()
    engine._handle_final_exam.assert_not_awaited()
    engine._handle_event_choice.assert_not_awaited()
    assert engine.emit.await_count == 7


@pytest.mark.asyncio
async def test_next_semester_is_allowed_when_exam_summary_is_complete():
    repo = Mock()
    repo.get_snapshot = AsyncMock(return_value=_Snapshot({"exam_completed": 1}))
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore[arg-type]
    engine.is_running = False
    engine.emit = AsyncMock()
    engine._next_semester = AsyncMock()
    engine.check_and_trigger_gameover = AsyncMock(return_value=False)

    await engine.process_action({"action": "next_semester"})

    engine._next_semester.assert_awaited_once()


@pytest.mark.asyncio
async def test_next_semester_is_rejected_before_exam_summary():
    repo = Mock()
    repo.get_snapshot = AsyncMock(return_value=_Snapshot({"exam_completed": 0}))
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore[arg-type]
    engine.is_running = False
    engine.emit = AsyncMock()
    engine._next_semester = AsyncMock()

    await engine.process_action({"action": "next_semester"})

    engine._next_semester.assert_not_awaited()
    engine.emit.assert_awaited_once_with(
        "toast",
        {"message": "期末结算完成后才能进入下学期", "level": "warning"},
    )


@pytest.mark.asyncio
async def test_run_loop_uses_balance_tick_interval_for_sleep_and_elapsed(monkeypatch):
    repo = Mock()
    repo.update_stat = AsyncMock(return_value=7)
    repo.get_snapshot = AsyncMock(
        return_value=_Snapshot(
            {
                "semester_idx": 1,
                "elapsed_game_time": 7,
                "course_info_json": "[]",
                "iq": 100,
                "stress": 0,
            }
        )
    )
    repo.get_items_state = AsyncMock(
        return_value={"version": 1, "owned": [], "updated_at": 0}
    )
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore[arg-type]
    engine.speed_multiplier = 2.0
    engine.is_running = True
    engine.check_and_trigger_gameover = AsyncMock(return_value=True)
    slept: list[float] = []

    async def fake_sleep(seconds: float):
        slept.append(seconds)

    patched_config = {
        **balance.raw,
        "tick": {**balance.raw.get("tick", {}), "interval_seconds": 7},
    }
    monkeypatch.setattr(balance, "_config", patched_config)
    monkeypatch.setattr("app.game.engine.asyncio.sleep", fake_sleep)

    await engine.run_loop()

    assert slept == [3.5]
    repo.update_stat.assert_awaited_once_with("elapsed_game_time", 7)
