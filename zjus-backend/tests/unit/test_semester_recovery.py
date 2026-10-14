"""Regression coverage for nonblocking term commits and resumable holidays."""

import asyncio
import copy
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.content.holiday_library import load_holiday_library, pick_holiday_event
from app.game.engine import GameEngine, GameMode
from app.schemas.dingtalk import DingTalkState
from app.schemas.game_state import GameStateSnapshot, PlayerStats
from app.schemas.holiday import HolidayEvent, HolidayState
from app.services.game_service import GameService
from app.services.save_service import SaveService


class MemoryRepo:
    """Stateful repository double; real Lua is checked separately in Compose."""

    user_id = "912345678"

    def __init__(self, idx=1, completed=1):
        self.stats = PlayerStats.build_initial("tester").model_dump()
        self.stats.update(semester_idx=idx, exam_completed=completed, major_abbr="CS")
        self.courses = {"old": 90.0}
        self.states = {"old": 2}
        self.holiday = HolidayState()
        self.event = None
        self.summary = None
        self.get_event_history = AsyncMock(return_value=[])

    async def get_snapshot(self):
        return GameStateSnapshot(
            stats=PlayerStats.from_redis(self.stats),
            courses=self.courses.copy(),
            course_states=self.states.copy(),
            achievements=[],
        )

    async def commit_semester_transition(self, idx, stats, courses, states, holiday):
        if self.stats["semester_idx"] != idx or self.stats["exam_completed"] != 1:
            return False
        self.stats.update(stats)
        if courses is not None:
            self.courses, self.states = courses.copy(), states.copy()
        self.holiday, self.event, self.summary = (
            holiday.model_copy(deep=True),
            None,
            None,
        )
        return True

    async def get_holiday_state(self):
        return self.holiday.model_copy(deep=True)

    async def update_holiday_if_current(self, state):
        if (
            self.holiday.token != state.token
            or self.holiday.status != "pending"
            or self.stats["semester_idx"] != state.semester_idx
            or self.stats["exam_completed"]
        ):
            return False
        self.holiday = state.model_copy(deep=True)
        return True

    async def get_current_event(self):
        return copy.deepcopy(self.event)

    async def set_current_event(self, event):
        self.event = copy.deepcopy(event)

    async def get_semester_summary(self):
        return copy.deepcopy(self.summary)

    async def get_dingtalk_state(self):
        return DingTalkState()

    async def get_items_state(self):
        return {"version": 1, "owned": [], "updated_at": 0}


@asynccontextmanager
async def fake_db():
    yield Mock()


def make_engine(repo):
    world = Mock()
    world.get_semester_courses = AsyncMock(
        return_value=[
            {"id": "new", "name": "数据结构", "credits": 4},
        ]
    )
    service = GameService(repo.user_id, repo, world=world)
    engine = GameEngine(repo.user_id, repo, SaveService(), service, db_factory=fake_db)
    engine.emit = AsyncMock()
    engine._push_update = AsyncMock()
    engine.start = Mock(side_effect=lambda: setattr(engine, "is_running", True))
    return engine


@pytest.mark.asyncio
async def test_new_term_ack_precedes_slow_autosave_and_ai():
    repo = MemoryRepo()
    engine = make_engine(repo)
    blocker = asyncio.Event()
    writing = asyncio.Event()

    async def persist(values, db):
        writing.set()
        await blocker.wait()
        assert values["stats_data"]["exam_completed"] == 0
        assert values["courses_data"] == {"new": 0.0}
        return True

    with patch.object(SaveService, "persist_snapshot", side_effect=persist):
        await engine.process_action(
            {"action": "next_semester", "expected_semester_idx": 1}
        )
        await asyncio.wait_for(engine._transition_task, 1)
        await asyncio.wait_for(writing.wait(), 1)
        assert engine.is_running
        assert repo.stats["semester_idx"] == 2
        assert repo.stats["elapsed_game_time"] == 0
        assert repo.holiday.status == "pending"
        assert engine.emit.await_args_list[0].args[0] == "new_semester"
        engine._restore_semester_summary = AsyncMock()
        engine._restore_holiday_event = AsyncMock()
        await asyncio.wait_for(engine.process_action({"action": "get_state"}), 1)
        blocker.set()
        assert await SaveService.wait_for_pending(repo.user_id, 1)
    engine.shutdown()


@pytest.mark.asyncio
async def test_duplicate_transition_is_deduplicated_while_commit_pending():
    engine = make_engine(MemoryRepo())
    gate = asyncio.Event()

    async def transition(_):
        await gate.wait()

    engine._next_semester = AsyncMock(side_effect=transition)
    await engine.process_action({"action": "next_semester"})
    await asyncio.sleep(0)
    await engine.process_action({"action": "next_semester"})
    engine._next_semester.assert_awaited_once()
    assert engine.emit.await_args.args[1]["level"] == "info"
    gate.set()
    await engine._transition_task


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [ValueError("prepare"), RuntimeError("redis")])
async def test_transition_failure_reports_action_and_preserves_retry(failure):
    repo = MemoryRepo()
    engine = make_engine(repo)
    engine.game_service.process_semester_transition = AsyncMock(side_effect=failure)
    await engine._next_semester(1)
    assert repo.stats["semester_idx"] == 1
    assert engine.emit.await_args.args[1]["action"] == "next_semester"
    assert not engine.is_running


@pytest.mark.asyncio
async def test_graduation_keeps_final_courses_and_queues_final_state():
    repo = MemoryRepo(idx=8)
    engine = make_engine(repo)
    engine._schedule_autosave = AsyncMock()
    engine._emit_graduation = AsyncMock()
    await engine._next_semester(8)
    assert repo.stats["semester_idx"] == 9
    assert repo.courses == {"old": 90.0}
    engine._schedule_autosave.assert_awaited_once()
    engine._emit_graduation.assert_awaited_once()
    engine.start.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", [GameMode.LIBRARY, GameMode.HYBRID])
async def test_non_ai_holidays_use_seasonal_world_library(mode):
    repo = MemoryRepo(idx=2, completed=0)
    repo.holiday = HolidayState.pending(2)
    engine = make_engine(repo)
    engine.mode, engine.is_running = mode, True
    engine._schedule_autosave = AsyncMock()
    with patch("app.game.engine.generate_random_event", new=AsyncMock()) as generate:
        await engine._prepare_holiday_event(await repo.get_holiday_state())
        generate.assert_not_awaited()
    assert repo.holiday.status == "ready"
    assert repo.event["kind"] == "holiday"
    assert repo.event["id"] == repo.holiday.token


@pytest.mark.asyncio
async def test_ai_holiday_timeout_falls_back_without_blocking_term(monkeypatch):
    repo = MemoryRepo(idx=3, completed=0)
    repo.holiday = HolidayState.pending(3)
    engine = make_engine(repo)
    engine.mode, engine.is_running, engine.llm_available = GameMode.AI, True, True
    engine.llm_override = {"api_key": "private"}
    engine._schedule_autosave = AsyncMock()
    monkeypatch.setattr("app.game.engine.DEFAULT_LLM_TIMEOUT_SECONDS", 0.01)

    async def slow(*args, **kwargs):
        assert kwargs["context"] == "holiday_summer"
        assert kwargs["llm_override"] == engine.llm_override
        await asyncio.Event().wait()

    with patch("app.game.engine.generate_random_event", side_effect=slow):
        await asyncio.wait_for(
            engine._prepare_holiday_event(await repo.get_holiday_state()), 1
        )
    assert repo.event["kind"] == "holiday"
    assert engine.mode == GameMode.HYBRID


@pytest.mark.asyncio
async def test_pause_defers_holiday_until_resume_and_deduplicates_delivery():
    repo = MemoryRepo(idx=2, completed=0)
    repo.holiday = HolidayState.pending(2)
    engine = make_engine(repo)
    engine.mode = GameMode.LIBRARY
    engine._schedule_autosave = AsyncMock()
    await engine._prepare_holiday_event(await repo.get_holiday_state())
    engine.emit.assert_not_awaited()
    assert repo.holiday.status == "ready"
    engine.is_running = True
    await engine._restore_holiday_event()
    await engine._restore_holiday_event()
    assert engine.emit.await_count == 1
    await engine._restore_holiday_event(force_delivery=True)
    assert engine.emit.await_count == 2
    repo.holiday.status = "resolved"
    await engine._restore_holiday_event(force_delivery=True)
    assert engine.emit.await_count == 2


@pytest.mark.asyncio
async def test_late_holiday_after_restart_cannot_publish():
    repo = MemoryRepo(idx=2, completed=0)
    old_state = HolidayState.pending(2)
    repo.holiday = HolidayState.pending(2)
    engine = make_engine(repo)
    engine.mode, engine.is_running = GameMode.LIBRARY, True
    engine._schedule_autosave = AsyncMock()
    await engine._prepare_holiday_event(old_state)
    engine.emit.assert_not_awaited()
    assert repo.event is None


@pytest.mark.asyncio
async def test_current_holiday_suppresses_regular_random_event():
    repo = MemoryRepo(idx=2, completed=0)
    repo.holiday = HolidayState.pending(2)
    engine = make_engine(repo)
    engine.is_running = True
    await engine._trigger_random_event()
    engine.emit.assert_not_awaited()
    repo.get_event_history.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_event_id_or_option_never_consumes_current_event():
    repo = MemoryRepo(idx=2, completed=0)
    event = pick_holiday_event("winter")
    event.id = "current"
    repo.event = event.model_dump()
    repo.consume_event_choice = AsyncMock()
    engine = make_engine(repo)
    engine._emit_feedback = AsyncMock()
    await engine._apply_event_choice(
        {"option_id": "not-an-option", "event_id": "current"}
    )
    await engine._apply_event_choice({"option_id": "A", "event_id": "stale"})
    repo.consume_event_choice.assert_not_awaited()


@pytest.mark.asyncio
async def test_save_queue_is_fifo_immutable_and_survives_cancelled_observer():
    gate = asyncio.Event()
    written = []
    started = asyncio.Event()

    async def persist(values, db):
        if not written:
            started.set()
            await gate.wait()
        written.append(values["stats_data"]["semester_idx"])
        return True

    values = {"user_id": 912345677, "save_slot": 4, "stats_data": {"semester_idx": 2}}
    with patch.object(SaveService, "persist_snapshot", side_effect=persist):
        first = SaveService.enqueue_snapshot(values, fake_db)
        values["stats_data"]["semester_idx"] = 3
        second = SaveService.enqueue_snapshot(values, fake_db)
        await started.wait()

        async def observe():
            return await asyncio.shield(first)

        observer = asyncio.create_task(observe())
        await asyncio.sleep(0)
        observer.cancel()
        with pytest.raises(asyncio.CancelledError):
            await observer
        assert not first.cancelled()
        gate.set()
        assert await second
    assert written == [2, 3]


@pytest.mark.asyncio
async def test_save_timeout_warns_without_manual_exit_confirmation(monkeypatch):
    monkeypatch.setattr(SaveService, "SAVE_TIMEOUT_SECONDS", 0.01)

    async def stuck(values, db):
        await asyncio.Event().wait()

    engine = make_engine(MemoryRepo())
    with patch.object(SaveService, "persist_snapshot", side_effect=stuck):
        task = SaveService.enqueue_snapshot(
            {"user_id": 912345676, "save_slot": 1}, fake_db
        )
        await engine._observe_autosave(task)
    assert engine.emit.await_args.args[0] == "toast"
    assert engine.emit.await_args.args[1]["action"] == "semester_autosave"


@pytest.mark.asyncio
async def test_reconnect_restores_transcript_without_exam_recalculation():
    repo = MemoryRepo(idx=2)
    repo.summary = {"semester_idx": 2, "cgpa": 3.5, "courses": []}
    engine = make_engine(repo)
    await engine._restore_semester_summary()
    assert engine.emit.await_args.args == ("semester_summary", {"data": repo.summary})
    repo.summary = None
    await engine._restore_semester_summary()
    assert engine.emit.await_args.args[1]["data"]["semester_idx"] == 2


@pytest.mark.asyncio
async def test_resume_does_not_restart_ticking_after_exam():
    engine = make_engine(MemoryRepo(idx=2))
    await engine.process_action({"action": "resume"})
    engine.start.assert_not_called()
    assert engine.emit.await_args.args[0] == "semester_summary"


@pytest.mark.asyncio
async def test_same_slot_reconnect_prefers_active_state_over_older_db_save():
    repo = Mock()
    repo.exists = AsyncMock(return_value=True)
    repo.get_active_save_slot = AsyncMock(return_value=4)
    repo.get_all_game_data = AsyncMock(return_value={"stats": {"semester_idx": 3}})
    service = GameService("1", repo, world=Mock())
    with patch.object(SaveService, "load_from_db", new=AsyncMock()) as load:
        result = await service.prepare_game_context(
            "tester", db=Mock(), save_slot=4, force_load_save=True
        )
        load.assert_not_awaited()
    assert result["data"]["stats"]["semester_idx"] == 3


def test_holiday_library_and_effect_validation():
    assert all(load_holiday_library().values())
    invalid = pick_holiday_event("winter").model_dump()
    invalid["options"][0]["effects"] = {"gpa": 10}
    with pytest.raises(ValueError):
        HolidayEvent.model_validate(invalid)
    assert HolidayState.from_raw(None).status == "none"


@pytest.mark.asyncio
async def test_holiday_metadata_is_saved_and_restored_without_becoming_player_stats():
    repo = MemoryRepo(idx=2, completed=0)
    repo.holiday = HolidayState.pending(2)
    values = await SaveService.capture_snapshot(repo, 3)
    assert values["stats_data"]["_holiday_state"]["status"] == "pending"
    save = Mock(**values)
    result = Mock()
    result.scalars.return_value.first.return_value = save
    db = Mock(execute=AsyncMock(return_value=result), rollback=AsyncMock())
    target = Mock(
        set_game_data=AsyncMock(),
        set_dingtalk_state=AsyncMock(),
        set_holiday_state=AsyncMock(),
        set_semester_summary=AsyncMock(),
        set_active_save_slot=AsyncMock(),
    )
    assert await SaveService.load_from_db(repo.user_id, target, db, 3)
    assert target.set_holiday_state.await_args.args[0].status == "pending"
    assert "_holiday_state" not in target.set_game_data.await_args.kwargs["stats"]
