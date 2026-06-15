import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.game.engine import GameEngine
from app.schemas.dingtalk import (
    DINGTALK_MAX_MESSAGES_PER_CONTACT,
    DingTalkContact,
    DingTalkMessage,
    DingTalkReplyOption,
    DingTalkRoundState,
    DingTalkState,
    build_contact_id,
    is_replyable_role,
    normalize_dingtalk_role,
)


def test_contact_id_is_stable_for_same_character():
    first = build_contact_id("【室友】", "roommate")
    second = build_contact_id("【室友】", "roommate")

    assert first == second
    assert first.startswith("dt_")


def test_replyable_roles_match_product_contract():
    assert is_replyable_role("roommate")
    assert is_replyable_role("classmate")
    assert is_replyable_role("friend")
    assert is_replyable_role("teaching_assistant")
    assert is_replyable_role("teacher")
    assert is_replyable_role("crush")
    assert not is_replyable_role("system")
    assert not is_replyable_role("counselor")


def test_role_aliases_keep_legacy_student_messages_replyable():
    assert normalize_dingtalk_role("student") == "classmate"
    assert normalize_dingtalk_role("同学") == "classmate"
    assert normalize_dingtalk_role("室友") == "roommate"
    assert is_replyable_role("student")
    assert build_contact_id("小明", "student") == build_contact_id("小明", "classmate")


def test_dingtalk_state_compacts_contact_history():
    contact = DingTalkContact(
        contact_id="dt_test",
        sender="【室友】",
        role="roommate",
        is_replyable=True,
        messages=[
            DingTalkMessage(
                message_id=f"m{i}",
                speaker="npc",
                content=str(i),
                created_at=i,
            )
            for i in range(DINGTALK_MAX_MESSAGES_PER_CONTACT + 5)
        ],
    )
    state = DingTalkState(contacts={contact.contact_id: contact})

    state.compact()

    messages = state.contacts["dt_test"].messages
    assert len(messages) == DINGTALK_MAX_MESSAGES_PER_CONTACT
    assert messages[0].content == "5"


class _StatsSnapshot:
    def __init__(self):
        self.stats = SimpleNamespace(
            model_dump=lambda: {
                "username": "tester",
                "major": "计算机科学与技术",
                "semester": "大一秋冬",
                "sanity": 60,
                "stress": 30,
                "gpa": "3.5",
            }
        )


class _Repo:
    def __init__(self, state: DingTalkState):
        self.state = state
        self.effects: list[tuple[str, int]] = []

    async def get_dingtalk_state(self):
        return self.state

    async def set_dingtalk_state(self, state):
        self.state = DingTalkState.from_raw(state)

    async def get_snapshot(self):
        return _StatsSnapshot()

    async def update_stat_safe(self, field, delta, min_val=0, max_val=200):
        self.effects.append((field, delta))
        return 100 + delta


@pytest.mark.asyncio
async def test_engine_dingtalk_reply_closes_round_and_applies_effects():
    contact = DingTalkContact(
        contact_id=build_contact_id("【室友】", "roommate"),
        sender="【室友】",
        role="roommate",
        is_replyable=True,
        messages=[
            DingTalkMessage(
                message_id="m1",
                speaker="npc",
                content="你在吗？",
                created_at=1,
                round_id="r1",
            )
        ],
        pending_options=[DingTalkReplyOption(option_id="opt_1", text="在的")],
        round=DingTalkRoundState(
            round_id="r1",
            status="open",
            player_reply_count=2,
        ),
    )
    repo = _Repo(DingTalkState(contacts={contact.contact_id: contact}))
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock()) # type: ignore
    engine.emit = AsyncMock()
    engine._push_update = AsyncMock()
    engine._generate_dingtalk_reply_result = AsyncMock(
        return_value={
            "content": "那太好了。",
            "settlement": {
                "desc": "室友的回应让你放松了一点。",
                "effects": {"sanity": 2, "forbidden": 99},
            },
        }
    )

    await engine._handle_dingtalk_reply(
        {"contact_id": contact.contact_id, "option_id": "opt_1"}
    )

    saved_contact = repo.state.contacts[contact.contact_id]
    assert saved_contact.round.status == "closed"
    assert saved_contact.pending_options == []
    assert [m.speaker for m in saved_contact.messages[-2:]] == ["player", "npc"]
    assert repo.effects == [("sanity", 2)]
    engine._push_update.assert_awaited()


@pytest.mark.asyncio
async def test_engine_emits_player_dingtalk_reply_before_generating_npc_reply():
    contact = DingTalkContact(
        contact_id=build_contact_id("【室友】", "roommate"),
        sender="【室友】",
        role="roommate",
        is_replyable=True,
        messages=[
            DingTalkMessage(
                message_id="m1",
                speaker="npc",
                content="你在吗？",
                created_at=1,
                round_id="r1",
            )
        ],
        pending_options=[DingTalkReplyOption(option_id="opt_1", text="在的")],
        round=DingTalkRoundState(
            round_id="r1",
            status="open",
            player_reply_count=0,
        ),
    )
    repo = _Repo(DingTalkState(contacts={contact.contact_id: contact}))
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore
    engine.emit = AsyncMock()

    async def generate_after_player_update(*args, **kwargs):
        del args, kwargs
        saved_contact = repo.state.contacts[contact.contact_id]
        assert [m.speaker for m in saved_contact.messages] == ["npc", "player"]
        assert saved_contact.pending_options == []
        assert engine.emit.await_count == 1
        first_emit = engine.emit.await_args_list[0]
        assert first_emit.args[0] == "dingtalk_thread_update"
        assert first_emit.args[1]["contact"]["messages"][-1]["speaker"] == "player"
        return {
            "content": "我看到了。",
            "reply_options": [{"option_id": "opt_1", "text": "好"}],
        }

    engine._generate_dingtalk_reply_result = AsyncMock(
        side_effect=generate_after_player_update
    )

    await engine._handle_dingtalk_reply(
        {"contact_id": contact.contact_id, "option_id": "opt_1"}
    )

    assert engine.emit.await_args_list[1].args[0] == "dingtalk_thread_update"
    final_contact = repo.state.contacts[contact.contact_id]
    assert [m.speaker for m in final_contact.messages] == ["npc", "player", "npc"]


@pytest.mark.asyncio
async def test_engine_schedules_dingtalk_reply_without_blocking_actions():
    repo = _Repo(DingTalkState())
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_reply(data):
        del data
        started.set()
        await release.wait()

    engine._handle_dingtalk_reply = slow_reply  # type: ignore[method-assign]

    await asyncio.wait_for(
        engine.process_action(
            {"action": "dingtalk_reply", "contact_id": "c", "option_id": "o"}
        ),
        timeout=0.05,
    )
    await asyncio.wait_for(started.wait(), timeout=0.05)

    release.set()
    await asyncio.gather(*list(engine._background_tasks))


@pytest.mark.asyncio
async def test_engine_schedules_relax_action_and_deduplicates_inflight_target():
    repo = _Repo(DingTalkState())
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore
    engine.emit = AsyncMock()
    engine.check_and_trigger_gameover = AsyncMock(return_value=False)
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_relax(target):
        assert target == "cc98"
        started.set()
        await release.wait()

    engine._handle_relax = slow_relax  # type: ignore[method-assign]

    await asyncio.wait_for(
        engine.process_action({"action": "relax", "target": "cc98"}),
        timeout=0.05,
    )
    await asyncio.wait_for(started.wait(), timeout=0.05)
    assert "cc98" in engine._relax_inflight

    await engine.process_action({"action": "relax", "target": "cc98"})
    engine.emit.assert_awaited_with(
        "toast",
        {"message": "该休闲动作正在结算中，请稍等", "level": "info"},
    )

    release.set()
    await asyncio.gather(*list(engine._background_tasks))
    assert "cc98" not in engine._relax_inflight
    engine.check_and_trigger_gameover.assert_awaited()
