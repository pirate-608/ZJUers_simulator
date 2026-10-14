"""Opt-in Compose smoke using real Redis, PostgreSQL, and the running WebSocket.

Run inside the Compose backend with RUN_GAME_INTEGRATION=1. Every test owns a
unique Redis namespace/account and deletes only the state it created.
"""

import asyncio
import json
import os
from uuid import uuid4

import pytest
from jose import jwt
from redis.asyncio import Redis
from sqlalchemy import delete, select
from websockets import connect

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.game.balance import balance
from app.models.game_save import GameSave
from app.models.user import User
from app.repositories.redis_repo import RedisRepository
from app.schemas.game_state import PlayerStats
from app.schemas.holiday import HolidayEvent, HolidayState
from app.services.game_service import GameService
from app.services.world_service import WorldService

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_GAME_INTEGRATION") != "1", reason="Compose-only smoke is opt-in"
)


@pytest.mark.asyncio(loop_scope="module")
async def test_real_redis_commit_and_holiday_choice_are_atomic_and_idempotent():
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    repo = RedisRepository(f"semester_smoke_{uuid4().hex}", redis)
    try:
        stats = PlayerStats.build_initial("tester").model_dump()
        stats.update(major_abbr="CS", semester_idx=1, exam_completed=1, energy=40)
        await repo.set_game_data(
            stats, {"old": 90}, {"old": 2}, items_state={"owned": ["planner"]}
        )
        await repo.set_semester_summary({"semester_idx": 1})
        holiday = HolidayState.pending(2)
        new_stats = dict(
            semester_idx=2, exam_completed=0, elapsed_game_time=0, energy=70
        )
        assert await repo.commit_semester_transition(
            1, new_stats, {"new": 0}, {"new": 1}, holiday
        )
        assert not await repo.commit_semester_transition(
            1, new_stats, {"bad": 1}, {"bad": 1}, holiday
        )
        snapshot = await repo.get_snapshot()
        assert snapshot.courses == {"new": 0.0}
        assert snapshot.stats.exam_completed == 0
        assert await repo.get_semester_summary() is None
        assert (await repo.get_items_state())["owned"] == ["planner"]
        holiday.status = "ready"
        holiday.event = HolidayEvent(
            id=holiday.token,
            semester_idx=2,
            title="假期",
            desc="回顾",
            options=[
                {"id": "A", "text": "休息", "effects": {"energy": 5}},
                {"id": "B", "text": "交流", "effects": {"eq": 1}},
            ],
        )
        assert await repo.update_holiday_if_current(holiday)
        await repo.set_current_event(holiday.event.model_dump())
        assert await repo.consume_event_choice("stale", "A") is None
        assert await repo.consume_event_choice(holiday.token, "invalid") is None
        results = await asyncio.gather(
            repo.consume_event_choice(holiday.token, "A"),
            repo.consume_event_choice(holiday.token, "A"),
        )
        assert sum(result is not None for result in results) == 1
        assert (await repo.get_snapshot()).stats.energy == 75
        assert (await repo.get_holiday_state()).status == "resolved"
        assert await repo.get_current_event() is None
        assert await redis.ttl(repo.keys["holiday"]) > 0
    finally:
        await repo.delete_all()
        await redis.aclose()


async def receive_type(socket, expected, timeout=8):
    async with asyncio.timeout(timeout):
        while True:
            payload = json.loads(await socket.recv())
            assert payload["type"] != "auth_error", payload
            if payload["type"] == expected:
                return payload


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("automatic", [False, True])
async def test_live_socket_exam_transition_holiday_and_save_exit(automatic):
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    user = User(username=f"测试{uuid4().hex[:12]}")
    async with AsyncSessionLocal() as db:
        db.add(user)
        await db.commit()
        await db.refresh(user)
    repo = RedisRepository(str(user.id), redis)
    try:
        service = GameService(str(user.id), repo, WorldService())
        await service.assign_major_and_init("CS", username=user.username)
        await repo.update_stats({"energy": 180, "sanity": 180})
        await repo.set_active_save_slot(4)
        snapshot = await repo.get_snapshot()
        for course in snapshot.courses:
            await redis.hset(repo.keys["courses"], course, "100")
        if automatic:
            await repo.update_stats(
                {"elapsed_game_time": balance.get_semester_duration(1) - 1}
            )
        token = jwt.encode(
            {"sub": str(user.id), "username": user.username},
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )
        async with connect("ws://127.0.0.1:8000/ws/game") as socket:
            await socket.send(json.dumps({"token": token, "load_save_slot": 4}))
            init = await receive_type(socket, "init")
            assert init["data"]["semester_idx"] == 1
            await socket.send(json.dumps({"action": "set_mode", "mode": "library"}))
            await receive_type(socket, "mode_changed")
            await asyncio.sleep(0.06)
            if not automatic:
                await socket.send(json.dumps({"action": "exam"}))
            summary = await receive_type(socket, "semester_summary")
            assert summary["data"]["semester_idx"] == 1
            await asyncio.sleep(0.06)
            await socket.send(
                json.dumps({"action": "next_semester", "expected_semester_idx": 1})
            )
            confirmation = await receive_type(socket, "new_semester")
            assert confirmation["data"]["stats"]["semester_idx"] == 2
            assert confirmation["data"]["stats"]["exam_completed"] == 0
            assert all(
                progress == 0 for progress in confirmation["data"]["courses"].values()
            )
            holiday = (await receive_type(socket, "random_event"))["data"]
            assert holiday["kind"] == "holiday"
        # Reconnect while the unanswered event exists: it must retain its token,
        # not restore the previous term or create a second holiday.
        async with connect("ws://127.0.0.1:8000/ws/game") as socket:
            await socket.send(json.dumps({"token": token, "load_save_slot": 4}))
            restored = await receive_type(socket, "init")
            assert restored["data"]["semester_idx"] == 2
            repeated = (await receive_type(socket, "random_event"))["data"]
            assert repeated["id"] == holiday["id"]
            holiday = repeated
            await socket.send(json.dumps({"action": "set_mode", "mode": "library"}))
            await receive_type(socket, "mode_changed")
            await asyncio.sleep(0.06)
            await socket.send(
                json.dumps(
                    {
                        "action": "event_choice",
                        "event_id": holiday["id"],
                        "option_id": holiday["options"][0]["id"],
                    }
                )
            )
            feedback = await receive_type(socket, "feedback")
            assert feedback["data"]["changes"]
            await asyncio.sleep(0.06)
            await socket.send(json.dumps({"action": "save_and_exit"}))
            result = await receive_type(socket, "save_result")
            assert result["success"] is True
            await receive_type(socket, "exit_confirmed")
        assert not await repo.exists()
        async with AsyncSessionLocal() as db:
            save = (
                await db.execute(
                    select(GameSave).where(
                        GameSave.user_id == user.id, GameSave.save_slot == 4
                    )
                )
            ).scalar_one()
            assert save.semester_index == 2
            assert save.stats_data["_holiday_state"]["status"] == "resolved"
            assert save.stats_data["exam_completed"] == 0
    finally:
        await repo.delete_all()
        # Wait for any already accepted autosave before deleting this test account.
        await asyncio.sleep(0.1)
        async with AsyncSessionLocal() as db:
            await db.execute(delete(GameSave).where(GameSave.user_id == user.id))
            await db.execute(delete(User).where(User.id == user.id))
            await db.commit()
        await redis.aclose()
