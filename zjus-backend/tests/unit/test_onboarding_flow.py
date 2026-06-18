from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.game.engine import GameEngine
from app.services.game_service import GameService


class DummyRepo:
    def __init__(self, exists_result=False):
        self.exists_result = exists_result
        self.data = {"stats": {"username": "tester"}}
        self.set_game_data = AsyncMock()

    async def exists(self):
        return self.exists_result

    async def get_all_game_data(self):
        return self.data


@pytest.mark.asyncio
async def test_prepare_game_context_requires_selected_save_when_forced():
    repo = DummyRepo(exists_result=True)
    service = GameService("1", repo, world=Mock())

    with patch(
        "app.services.game_service.SaveService.load_from_db",
        new=AsyncMock(return_value=False),
    ):
        result = await service.prepare_game_context(
            "tester",
            db=Mock(),
            save_slot=2,
            force_load_save=True,
        )

    assert result["status"] == "missing_save"


@pytest.mark.asyncio
async def test_prepare_game_context_loads_selected_save_before_redis_state():
    repo = DummyRepo(exists_result=True)
    service = GameService("1", repo, world=Mock())

    with patch(
        "app.services.game_service.SaveService.load_from_db",
        new=AsyncMock(return_value=True),
    ) as load_from_db:
        result = await service.prepare_game_context(
            "tester",
            db=Mock(),
            save_slot=3,
            force_load_save=True,
        )

    assert result["status"] == "loaded"
    load_from_db.assert_awaited_once()
    assert load_from_db.await_args.kwargs["save_slot"] == 3


@pytest.mark.asyncio
async def test_assign_major_and_init_resets_existing_redis_state():
    repo = DummyRepo(exists_result=True)
    world = Mock()
    world.get_major_by_abbr = AsyncMock(
        return_value={
            "major_info": {
                "name": "计算机科学与技术",
                "abbr": "CS",
                "iq_buff": 15,
                "stress_base": 10,
            },
            "course_plan": [],
            "initial_courses": [
                {
                    "id": "CS1001",
                    "name": "C程序设计基础及实验",
                    "credits": 4.0,
                    "difficulty": 3,
                }
            ],
        }
    )
    service = GameService("1", repo, world=world)

    await service.assign_major_and_init(
        "CS",
        stat_overrides={"iq": 100, "eq": 100, "luck": 50},
        username="tester",
    )

    repo.set_game_data.assert_awaited_once()
    stats = repo.set_game_data.await_args.kwargs["stats"]
    assert stats["iq"] == 115
    assert stats["eq"] == 100
    assert stats["luck"] == 50
    assert stats["initial_major_abbr"] == "CS"
    assert stats["initial_iq"] == 100
    assert stats["initial_eq"] == 100
    assert stats["initial_luck"] == 50


@pytest.mark.asyncio
async def test_reset_courses_for_new_semester_recovers_energy_halfway_to_full():
    repo = Mock()
    repo.get_snapshot = AsyncMock(
        return_value=_Snapshot({"major_abbr": "CS", "energy": 20})
    )
    repo.update_courses_and_states = AsyncMock()
    world = Mock()
    world.get_semester_courses = AsyncMock(
        return_value=[{"id": "CS2001", "name": "数据结构"}]
    )
    service = GameService("1", repo, world=world)

    result = await service.reset_courses_for_new_semester(2)

    stats_update = repo.update_courses_and_states.await_args.kwargs["stats_update"]
    assert stats_update["semester"] == "大一春夏"
    assert stats_update["energy"] == 60
    assert result["energy_recovery"] == {"before": 20, "after": 60}


@pytest.mark.asyncio
async def test_engine_restart_rebuilds_initial_profile_and_emits_complete_init():
    repo = Mock()
    repo.get_snapshot = AsyncMock(
        side_effect=[
            _Snapshot(
                {
                    "username": "tester",
                    "major_abbr": "CS",
                    "initial_major_abbr": "CS",
                    "initial_iq": 100,
                    "initial_eq": 110,
                    "initial_luck": 40,
                    "semester_idx": 2,
                    "elapsed_game_time": 120,
                }
            ),
            _Snapshot(
                {
                    "username": "tester",
                    "major_abbr": "CS",
                    "initial_major_abbr": "CS",
                    "initial_iq": 100,
                    "initial_eq": 110,
                    "initial_luck": 40,
                    "semester": "大一秋冬",
                    "semester_idx": 1,
                    "elapsed_game_time": 0,
                    "course_info_json": "[]",
                },
                courses={"CS1001": 0.0},
                course_states={"CS1001": 1},
            ),
        ]
    )
    repo.get_dingtalk_state = AsyncMock(
        return_value=Mock(model_dump=Mock(return_value={"contacts": {}}))
    )
    repo.get_items_state = AsyncMock(
        return_value={"version": 1, "owned": [], "updated_at": 0}
    )
    repo.get_cooldown_timestamp = AsyncMock(return_value=None)
    repo.set_game_data = AsyncMock()

    game_service = Mock()
    game_service.assign_major_and_init = AsyncMock()
    engine = GameEngine(
        "1",
        repo=repo,
        save_service=Mock(),
        game_service=game_service,
        db_factory=lambda: _AsyncContext(Mock()),
        save_slot=1,
    )
    engine.stop = Mock()
    engine.start = Mock()
    engine.emit = AsyncMock()

    await engine.process_action({"action": "restart"})

    game_service.assign_major_and_init.assert_awaited_once_with(
        "CS",
        stat_overrides={"iq": 100, "eq": 110, "luck": 50},
        username="tester",
    )
    engine.emit.assert_awaited_once()
    event_type, payload = engine.emit.await_args.args
    assert event_type == "init"
    assert payload["data"]["semester"] == "大一秋冬"
    assert payload["courses"] == {"CS1001": 0.0}
    assert payload["course_states"] == {"CS1001": 1}
    assert payload["semester_time_left"] > 0
    assert payload["dingtalk_state"] == {"contacts": {}}
    assert payload["items_state"]["owned"] == []
    engine.start.assert_called_once()


@pytest.mark.asyncio
async def test_engine_next_semester_autosaves_selected_slot():
    repo = Mock()
    repo.get_snapshot = AsyncMock()
    repo.get_items_state = AsyncMock(
        return_value={"version": 1, "owned": [], "updated_at": 0}
    )
    save_service = Mock()
    game_service = Mock()
    game_service.process_semester_transition = AsyncMock(
        return_value={"status": "graduated", "semester_idx": 9, "stats": {}}
    )
    engine = GameEngine(
        "1",
        repo=repo,
        save_service=save_service,
        game_service=game_service,
        db_factory=lambda: _AsyncContext(Mock()),
        save_slot=4,
    )
    engine.emit = AsyncMock()

    with patch("app.core.llm.generate_wenyan_report", new=AsyncMock(return_value="ok")):
        await engine._next_semester()

    assert game_service.process_semester_transition.await_args.kwargs["save_slot"] == 4


@pytest.mark.asyncio
async def test_dingtalk_uses_general_llm_when_custom_llm_has_no_rp_key():
    repo = Mock()
    repo.get_snapshot = AsyncMock(
        return_value=_Snapshot({"sanity": 80, "stress": 20, "gpa": "3.5"})
    )
    repo.get_items_state = AsyncMock(
        return_value={"version": 1, "owned": [], "updated_at": 0}
    )
    engine = GameEngine(
        "1",
        repo=repo,
        save_service=Mock(),
        game_service=Mock(),
        llm_override={"api_key": "general-key", "model": "generic"},
    )
    engine.is_running = True
    engine._store_dingtalk_npc_message = AsyncMock(return_value=None)

    with (
        patch(
            "app.core.dingtalk_llm.generate_dingtalk_via_m2her",
            new=AsyncMock(return_value={"content": "rp"}),
        ) as m2her,
        patch(
            "app.game.engine.generate_dingtalk_message",
            new=AsyncMock(return_value={"content": "generic"}),
        ) as generic,
    ):
        await engine._trigger_dingtalk_message()

    m2her.assert_not_awaited()
    generic.assert_awaited_once()
    assert generic.await_args.kwargs["llm_override"] == {
        "api_key": "general-key",
        "model": "generic",
    }


@pytest.mark.asyncio
async def test_dingtalk_uses_custom_rp_key_before_general_llm():
    repo = Mock()
    repo.get_snapshot = AsyncMock(
        return_value=_Snapshot({"sanity": 80, "stress": 20, "gpa": "3.5"})
    )
    repo.get_items_state = AsyncMock(
        return_value={"version": 1, "owned": [], "updated_at": 0}
    )
    rp_override = {"api_key": "rp-key", "model": "M2-her"}
    engine = GameEngine(
        "1",
        repo=repo,
        save_service=Mock(),
        game_service=Mock(),
        llm_override={"api_key": "general-key", "model": "generic"},
        rp_llm_override=rp_override,
    )
    engine.is_running = True
    engine._store_dingtalk_npc_message = AsyncMock(return_value=None)

    with (
        patch(
            "app.core.dingtalk_llm.generate_dingtalk_via_m2her",
            new=AsyncMock(return_value={"content": "rp"}),
        ) as m2her,
        patch(
            "app.game.engine.generate_dingtalk_message",
            new=AsyncMock(return_value={"content": "generic"}),
        ) as generic,
    ):
        await engine._trigger_dingtalk_message()

    m2her.assert_awaited_once()
    assert m2her.await_args.kwargs["llm_override"] == rp_override
    generic.assert_not_awaited()


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Snapshot:
    def __init__(self, stats, courses=None, course_states=None):
        self.stats = _Stats(stats)
        self.courses = courses or {}
        self.course_states = course_states or {}


class _Stats:
    def __init__(self, data):
        self.data = data

    def model_dump(self):
        return dict(self.data)
