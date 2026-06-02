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

    with patch("app.services.game_service.SaveService.load_from_db", new=AsyncMock(return_value=False)):
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


@pytest.mark.asyncio
async def test_engine_next_semester_autosaves_selected_slot():
    repo = Mock()
    repo.get_snapshot = AsyncMock()
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


class _AsyncContext:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, exc_type, exc, tb):
        return False
