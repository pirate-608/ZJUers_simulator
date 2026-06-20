import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

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


def test_dingtalk_state_compacts_contact_list_without_dropping_open_rounds():
    old_closed = DingTalkContact(
        contact_id="old",
        sender="旧联系人",
        role="roommate",
        last_message_at=1,
    )
    open_contact = DingTalkContact(
        contact_id="open",
        sender="进行中",
        role="teacher",
        last_message_at=2,
        round=DingTalkRoundState(round_id="r1", status="open"),
    )
    new_closed = DingTalkContact(
        contact_id="new",
        sender="新联系人",
        role="friend",
        last_message_at=3,
    )
    state = DingTalkState(
        contacts={
            "old": old_closed,
            "open": open_contact,
            "new": new_closed,
        }
    )

    state.compact(max_contacts=2)

    assert set(state.contacts) == {"open", "new"}


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

    async def get_items_state(self):
        return {"version": 1, "owned": [], "updated_at": 0}

    async def update_stat_safe(self, field, delta, min_val=0, max_val=200):
        self.effects.append((field, delta))
        return 100 + delta


class _RelaxRepo:
    def __init__(self, stats):
        self.stats = dict(stats)
        self.effects: list[tuple[str, int, int]] = []
        self.cooldowns: list[str] = []
        self.action_counts: list[str] = []

    async def get_snapshot(self):
        stats = self.stats
        return SimpleNamespace(
            stats=SimpleNamespace(model_dump=lambda: dict(stats)),
            courses={},
            course_states={},
        )

    async def get_items_state(self):
        return {"version": 1, "owned": [], "updated_at": 0}

    async def update_stat_safe(self, field, delta, min_val=0, max_val=200):
        current = int(self.stats.get(field, 0))
        new_value = max(min_val, min(max_val, current + int(delta)))
        self.stats[field] = new_value
        self.effects.append((field, int(delta), new_value))
        return new_value

    async def set_cooldown(self, target, timestamp):
        del timestamp
        self.cooldowns.append(target)

    async def get_cooldown_timestamp(self, target):
        del target
        return None

    async def increment_action_count(self, action_type):
        self.action_counts.append(action_type)
        return len(self.action_counts)


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

@pytest.mark.asyncio
async def test_random_event_result_is_discarded_when_paused_during_generation():
    repo = Mock()
    repo.get_event_history = AsyncMock(return_value=[])
    repo.get_snapshot = AsyncMock(return_value=_StatsSnapshot())
    repo.get_items_state = AsyncMock(
        return_value={"version": 1, "owned": [], "updated_at": 0}
    )
    repo.add_event_to_history = AsyncMock()
    repo.set_current_event = AsyncMock()
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())
    engine.mode = "ai"
    engine.llm_available = True
    engine.is_running = True
    engine.emit = AsyncMock()

    async def pause_and_return_event(*args, **kwargs):
        del args, kwargs
        engine.is_running = False
        return {"title": "突发", "desc": "暂停后才生成", "options": []}

    with patch(
        "app.game.engine.generate_random_event",
        new=AsyncMock(side_effect=pause_and_return_event),
    ):
        await engine._trigger_random_event()

    repo.add_event_to_history.assert_not_awaited()
    repo.set_current_event.assert_not_awaited()
    engine.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_dingtalk_result_is_discarded_when_paused_during_generation():
    repo = _Repo(DingTalkState())
    engine = GameEngine(
        "1",
        repo=repo,
        save_service=Mock(),
        game_service=Mock(),
        llm_override={"api_key": "custom", "model": "generic"},
    )
    engine.is_running = True
    engine.emit = AsyncMock()

    async def pause_and_return_message(*args, **kwargs):
        del args, kwargs
        engine.is_running = False
        return {
            "contact": {
                "contact_id": "dt_new",
                "sender": "新联系人",
                "role": "roommate",
                "is_replyable": True,
            },
            "content": "暂停后才到的消息",
            "reply_options": ["好"],
        }

    with patch(
        "app.game.engine.generate_dingtalk_message",
        new=AsyncMock(side_effect=pause_and_return_message),
    ):
        await engine._trigger_dingtalk_message()

    assert repo.state.contacts == {}
    engine.emit.assert_not_awaited()


def test_engine_reusable_dingtalk_contact_prefers_stale_contacts():
    contacts = {
        "newest": DingTalkContact(
            contact_id="newest",
            sender="最近联系人",
            role="roommate",
            last_message_at=30,
        ),
        "oldest": DingTalkContact(
            contact_id="oldest",
            sender="很久没聊",
            role="friend",
            last_message_at=10,
        ),
        "middle": DingTalkContact(
            contact_id="middle",
            sender="普通联系人",
            role="teacher",
            last_message_at=20,
        ),
    }
    engine = GameEngine("1", repo=Mock(), save_service=Mock(), game_service=Mock())  # type: ignore

    with (
        patch("app.game.engine.random.random", return_value=0.0),
        patch(
            "app.game.engine.random.choices",
            return_value=[contacts["oldest"]],
        ) as choices_mock,
    ):
        selected = engine._choose_reusable_dingtalk_contact(contacts)

    assert selected == contacts["oldest"]
    ordered_contacts = choices_mock.call_args.args[0]
    assert [contact.contact_id for contact in ordered_contacts] == [
        "oldest",
        "middle",
        "newest",
    ]
    assert choices_mock.call_args.kwargs["weights"] == [3, 2, 1]


@pytest.mark.asyncio
async def test_store_new_dingtalk_contact_does_not_double_apply_reuse_probability():
    existing = DingTalkContact(
        contact_id="dt_existing",
        sender="老联系人",
        role="roommate",
        is_replyable=True,
        last_message_at=1,
    )
    repo = _Repo(DingTalkState(contacts={existing.contact_id: existing}))
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore

    with patch("app.game.engine.random.random", return_value=0.0):
        contact = await engine._store_dingtalk_npc_message(
            {
                "contact": {
                    "contact_id": "dt_new",
                    "sender": "新联系人",
                    "role": "classmate",
                    "is_replyable": True,
                },
                "content": "今天自习室还有座位吗？",
                "reply_options": ["我看看"],
            }
        )

    assert contact is not None
    assert contact.contact_id == "dt_new"
    assert set(repo.state.contacts) == {"dt_existing", "dt_new"}


@pytest.mark.asyncio
async def test_engine_reuses_existing_dingtalk_contact_when_contact_cap_is_reached():
    contacts = {
        f"dt_{idx}": DingTalkContact(
            contact_id=f"dt_{idx}",
            sender=f"联系人{idx}",
            role="roommate",
            is_replyable=True,
            last_message_at=idx,
        )
        for idx in range(12)
    }
    repo = _Repo(DingTalkState(contacts=contacts))
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore

    contact = await engine._store_dingtalk_npc_message(
        {
            "contact": {
                "contact_id": "dt_new",
                "sender": "新联系人",
                "role": "roommate",
                "is_replyable": True,
            },
            "content": "今天一起复习吗？",
            "reply_options": ["好呀"],
        }
    )

    assert contact is not None
    assert contact.contact_id in contacts
    assert len(repo.state.contacts) == 12
    assert "dt_new" not in repo.state.contacts
    stored_message = repo.state.contacts[contact.contact_id].messages[-1]
    assert stored_message.content == "今天一起复习吗？"


@pytest.mark.asyncio
async def test_relax_positive_overflow_transfers_to_energy():
    repo = _RelaxRepo({"energy": 190, "sanity": 80, "stress": 0, "charm": 50})
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore
    engine.emit = AsyncMock()
    engine._push_update = AsyncMock()

    await engine._handle_relax("walk")

    assert repo.stats["stress"] == 0
    assert repo.stats["energy"] == 200
    assert ("walk" in repo.cooldowns)
    assert ("walk" in repo.action_counts)


@pytest.mark.asyncio
async def test_gym_can_gain_charm_from_balance_probability():
    repo = _RelaxRepo({"energy": 100, "sanity": 80, "stress": 30, "charm": 50})
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())  # type: ignore
    engine.emit = AsyncMock()
    engine._push_update = AsyncMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr("app.game.engine.random.random", lambda: 0.0)
        await engine._handle_relax("gym")

    assert repo.stats["charm"] == 51


@pytest.mark.asyncio
async def test_check_achievements_returns_user_visible_payload():
    repo = Mock()
    repo.get_snapshot = AsyncMock(
        return_value=SimpleNamespace(
            stats=SimpleNamespace(
                model_dump=lambda: {
                    "highest_gpa": "4.6",
                    "sanity": 80,
                    "eq": 80,
                    "charm": 80,
                }
            )
        )
    )
    repo.get_items_state = AsyncMock(
        return_value={"version": 1, "owned": [], "updated_at": 0}
    )
    repo.get_action_counts = AsyncMock(return_value={})
    repo.get_unlocked_achievements = AsyncMock(return_value=set())
    repo.unlock_achievement = AsyncMock()
    engine = GameEngine("1", repo=repo, save_service=Mock(), game_service=Mock())
    engine.emit = AsyncMock()

    unlocked = await engine._check_achievements()

    assert unlocked == [
        {
            "code": "gpa_king",
            "name": "卷王之王",
            "desc": "单学期 GPA 达到 4.5",
            "icon": "👑",
        }
    ]
    engine.emit.assert_awaited_with("achievement_unlocked", {"data": unlocked[0]})
