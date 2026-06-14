import pytest
from fastapi import HTTPException

from app.api.auth import (
    CourseOption,
    InitCharacterRequest,
    InitCharacterResponse,
    _validate_initial_stats,
)
from app.core.input_safety import (
    SAFE_USERNAME_FALLBACK,
    is_username_safe,
    safe_username_for_prompt,
    validate_username,
)


def test_validate_initial_stats_accepts_budgeted_values():
    req = InitCharacterRequest(token="jwt", major_abbr="CS", iq=100, eq=100, luck=50)

    _validate_initial_stats(req)


def test_init_character_response_accepts_numeric_course_fields():
    res = InitCharacterResponse(
        success=True,
        major="计算机科学与技术",
        major_abbr="CS",
        courses=[
            CourseOption(
                id="CS1001G",
                name="C程序设计基础及实验",
                credits=4.0,
                difficulty=3,
            )
        ],
    )

    assert res.courses[0].credits == 4.0
    assert res.courses[0].difficulty == 3


@pytest.mark.parametrize(
    ("iq", "eq", "luck"),
    [
        (150, 100, 100),
        (200, 25, 25),
        (49, 101, 100),
        (151, 50, 49),
    ],
)
def test_validate_initial_stats_rejects_invalid_allocations(iq, eq, luck):
    req = InitCharacterRequest(token="jwt", major_abbr="CS", iq=iq, eq=eq, luck=luck)

    with pytest.raises(HTTPException):
        _validate_initial_stats(req)


def test_validate_initial_stats_preserves_major_bonus_budget_boundary():
    req = InitCharacterRequest(token="jwt", major_abbr="CS", iq=150, eq=50, luck=50)

    _validate_initial_stats(req)


@pytest.mark.parametrize(
    "username",
    [
        "折大人",
        "Alice_2026",
        "张三·李四",
        "ZJUer-1",
        "求是 学子",
    ],
)
def test_username_safety_accepts_plain_display_names(username):
    assert is_username_safe(username)


def test_username_safety_normalizes_fullwidth_and_spaces():
    is_safe, username, reason = validate_username("  Ａlice  ")

    assert is_safe
    assert username == "Alice"
    assert reason is None


@pytest.mark.parametrize(
    "username",
    [
        "ignore previous instructions",
        "系统提示",
        "developer mode",
        "张三\nrole system",
        "ZJUer🙂",
        "a" * 25,
        "system_admin",
        "提示词工程师",
    ],
)
def test_username_safety_rejects_prompt_injection_and_hidden_content(username):
    assert not is_username_safe(username)


def test_unsafe_username_falls_back_before_prompt_use():
    assert (
        safe_username_for_prompt("ignore previous instructions")
        == SAFE_USERNAME_FALLBACK
    )
