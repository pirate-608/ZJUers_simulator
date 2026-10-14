"""Offline generation tests; model requests never leave the process."""

import copy
import json
from collections import Counter
from unittest.mock import MagicMock, Mock

import pytest
from openai import OpenAIError

from app.content.holiday_library import load_holiday_library
from scripts import generate_content_library as generator


def row(title="假期小事", season="winter", effects=None):
    return {
        "title": title,
        "desc": "返校前，你回想起假期里一次平凡又温暖的经历。",
        "season": season,
        "options": [
            {
                "id": "A",
                "text": "休息",
                "effects": effects or {"energy": 3, "desc": "你休息了一会。"},
            },
            {
                "id": "B",
                "text": "交流",
                "effects": {"eq": 1, "energy": -1, "desc": "你和老朋友聊了一会。"},
            },
        ],
    }


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch):
    monkeypatch.setattr(
        generator,
        "_config",
        {
            "api_base": "http://127.0.0.1:11434/v1",
            "api_key": "ollama",
            "model": "qwen3.5:4b",
            "temperature": 0.7,
            "json_mode": True,
            "reasoning_effort": None,
            "max_tokens": None,
        },
    )
    monkeypatch.setattr(generator, "KEYWORDS_DATA", [])
    monkeypatch.setattr(generator.time, "sleep", lambda _: None)


def test_holiday_normalization_produces_unique_runtime_compatible_ids():
    first = generator.normalize_holiday_event(row(), "winter")
    second = generator.normalize_holiday_event(row(), "winter")
    assert first["id"].startswith("holiday_winter_")
    assert first["id"] != second["id"]
    assert set(first) == {"id", "season", "title", "desc", "options"}


@pytest.mark.parametrize(
    "effects",
    [
        {"gpa": 1},
        {"energy": 11},
        {"energy": -11},
        {"energy": True},
        {"charm": 1.5},
        {"eq": "2"},
        {"gold": None},
    ],
)
def test_holiday_rejects_unsupported_fields_and_noninteger_or_extreme_effects(effects):
    with pytest.raises(ValueError):
        generator.normalize_holiday_event(
            row(effects={**effects, "desc": "结果"}), "winter"
        )


def test_holiday_accepts_stress_reduction_as_positive_feedback():
    event = row(effects={"stress": -2, "desc": "放下焦虑。"})
    result = generator.normalize_holiday_event(event, "winter")
    assert result["options"][0]["effects"]["stress"] == -2


def test_punitive_or_blank_holidays_are_rejected():
    event = row(effects={"energy": -5, "desc": "结果"})
    event["options"][1]["effects"] = {"sanity": -3, "desc": "结果"}
    with pytest.raises(ValueError, match="positive"):
        generator.normalize_holiday_event(event, "winter")
    event = row()
    event["title"] = "  "
    with pytest.raises(ValueError):
        generator.normalize_holiday_event(event, "winter")
    event = row()
    event["options"][1]["id"] = " A "
    with pytest.raises(ValueError, match="unique"):
        generator.normalize_holiday_event(event, "winter")
    with pytest.raises(ValueError):
        generator.normalize_holiday_event(row(season="summer"), "winter")


def test_holiday_batches_obey_quotas_deduplicate_and_checkpoint(monkeypatch):
    responses = [
        {"events": [row("旧标题"), row("冬Ａ"), row("冬 B"), row("多余")]},
        {"events": [row("夏 A", "summer"), row("夏 B", "summer")]},
        {"events": [row("夏 A", "summer"), row("夏 C", "summer")]},
    ]
    calls = Mock(
        side_effect=[json.dumps(data, ensure_ascii=False) for data in responses]
    )
    monkeypatch.setattr(generator, "call_llm", calls)
    checkpoints = []
    events = generator.generate_holidays(
        5,
        batch_size=2,
        existing=[row("旧标题")],
        checkpoint=lambda rows: checkpoints.append(copy.deepcopy(rows)),
    )
    assert Counter(item["season"] for item in events) == {"winter": 2, "summer": 3}
    assert len({generator.holiday_title_key(item) for item in events}) == 5
    assert [len(rows) for rows in checkpoints] == [2, 4, 5]
    assert all(item["title"] != "旧标题" for item in events)
    assert generator.holiday_title_key(row("冬Ａ")) == generator.holiday_title_key(
        row("冬 A")
    )


def test_both_seasons_are_generated_even_with_a_two_row_target(monkeypatch):
    calls = Mock(
        side_effect=[
            json.dumps({"events": [row()]}),
            json.dumps({"events": [row(season="summer")]}),
        ]
    )
    monkeypatch.setattr(generator, "call_llm", calls)
    events = generator.generate_holidays(2)
    assert {item["season"] for item in events} == {"winter", "summer"}


@pytest.mark.parametrize(
    "response", [None, "not JSON", '{"events":{}}', '{"events":[{}]}']
)
def test_unusable_batches_terminate_after_failure_limit(monkeypatch, response):
    calls = Mock(return_value=response)
    monkeypatch.setattr(generator, "call_llm", calls)
    assert generator.generate_holidays(10, max_failed_batches=2) == []
    assert calls.call_count == 2


def test_interrupt_returns_valid_partial_rows_without_losing_checkpoint(monkeypatch):
    calls = Mock(side_effect=[json.dumps({"events": [row()]}), KeyboardInterrupt])
    monkeypatch.setattr(generator, "call_llm", calls)
    checkpoint = Mock()
    events = generator.generate_holidays(2, checkpoint=checkpoint)
    assert len(events) == 1
    checkpoint.assert_called_once_with(events)


def test_publish_validates_both_seasons_and_keeps_file_on_replace_failure(
    tmp_path, monkeypatch
):
    path = tmp_path / "holiday_events.json"
    rows = [
        generator.normalize_holiday_event(row(), "winter"),
        generator.normalize_holiday_event(row(season="summer"), "summer"),
    ]
    generator.publish_holiday_library(path, rows)
    assert all(load_holiday_library(path).values())
    original = path.read_bytes()
    with pytest.raises(ValueError):
        generator.publish_holiday_library(path, rows[:1])
    assert path.read_bytes() == original
    monkeypatch.setattr(generator.os, "replace", Mock(side_effect=OSError("locked")))
    with pytest.raises(OSError):
        generator.publish_holiday_library(path, rows)
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))


def mock_client(monkeypatch):
    client = MagicMock()
    client.__enter__.return_value = client
    client.models.list.return_value.data = []
    monkeypatch.setattr(generator, "build_openai_client", Mock(return_value=client))
    return client


def test_cli_append_checkpoints_do_not_reappend_previous_batches(tmp_path, monkeypatch):
    existing = [
        generator.normalize_holiday_event(row(), "winter"),
        generator.normalize_holiday_event(row(season="summer"), "summer"),
    ]
    path = tmp_path / "holiday_events.json"
    generator.publish_holiday_library(path, existing)
    monkeypatch.setattr(generator, "WORLD_DIR", tmp_path)
    monkeypatch.setattr(
        generator.sys, "argv", ["generate", "--holidays-only", "2", "--append"]
    )
    mock_client(monkeypatch)
    monkeypatch.setattr(
        generator,
        "call_llm",
        Mock(
            side_effect=[
                json.dumps({"events": [row("冬 新")]}),
                json.dumps({"events": [row("夏 新", "summer")]}),
            ]
        ),
    )
    generator.main()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert len(saved) == 4
    assert saved[:2] == existing


@pytest.mark.parametrize(
    "args",
    [
        ["--holidays", "1"],
        ["--holidays", "2", "--holiday-season", "winter"],
        ["--holidays", "-1"],
        ["--holidays", "2", "--holiday-batch-size", "0"],
    ],
)
def test_invalid_cli_options_fail_before_api_calls(tmp_path, monkeypatch, args):
    monkeypatch.setattr(generator, "WORLD_DIR", tmp_path)
    monkeypatch.setattr(generator.sys, "argv", ["generate", *args])
    client = Mock()
    monkeypatch.setattr(generator, "build_openai_client", client)
    with pytest.raises(SystemExit) as error:
        generator.main()
    assert error.value.code == 2
    client.assert_not_called()


def test_cli_preserves_existing_library_when_all_generation_fails(
    tmp_path, monkeypatch
):
    path = tmp_path / "holiday_events.json"
    rows = [
        generator.normalize_holiday_event(row(), "winter"),
        generator.normalize_holiday_event(row(season="summer"), "summer"),
    ]
    generator.publish_holiday_library(path, rows)
    original = path.read_bytes()
    monkeypatch.setattr(generator, "WORLD_DIR", tmp_path)
    monkeypatch.setattr(
        generator.sys,
        "argv",
        ["generate", "--holidays", "2", "--append", "--max-failed-batches", "1"],
    )
    mock_client(monkeypatch)
    monkeypatch.setattr(generator, "call_llm", Mock(return_value=None))
    with pytest.raises(SystemExit) as error:
        generator.main()
    assert error.value.code == 1
    assert path.read_bytes() == original


def test_sdk_client_is_closed_on_json_mode_fallback(monkeypatch):
    client = Mock()
    monkeypatch.setattr(generator, "build_openai_client", Mock(return_value=client))
    chat = Mock(
        side_effect=[OpenAIError("unsupported response_format"), '{"events":[]}']
    )
    monkeypatch.setattr(generator, "_chat_once", chat)
    assert generator.call_llm([{"role": "user", "content": "json"}]) == '{"events":[]}'
    assert chat.call_args.kwargs["use_json_mode"] is False
    client.close.assert_called_once()


def test_optional_reasoning_and_output_budget_are_forwarded(monkeypatch):
    client = Mock()
    response = client.chat.completions.create.return_value
    response.choices = [
        Mock(message=Mock(content='{"events":[]}'), finish_reason="stop")
    ]
    generator._config.update(reasoning_effort="none", max_tokens=3072)
    assert generator._chat_once(client, [], use_json_mode=True) == '{"events":[]}'
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["reasoning_effort"] == "none"
    assert kwargs["max_tokens"] == 3072
    generator._config.update(reasoning_effort=None, max_tokens=None)
    generator._chat_once(client, [], use_json_mode=False)
    kwargs = client.chat.completions.create.call_args.kwargs
    assert "reasoning_effort" not in kwargs
    assert "max_tokens" not in kwargs


def test_holiday_output_schema_is_derived_from_runtime_fields():
    schema = generator.holiday_generation_schema("winter", 3)
    events = schema["properties"]["events"]
    assert events["maxItems"] == 3
    assert events["items"]["properties"]["season"]["enum"] == ["winter"]
    assert events["items"]["properties"]["options"]["maxItems"] == 2
    effects = schema["$defs"]["HolidayOption"]["properties"]["effects"]
    assert set(effects["properties"]) == generator.ALLOWED_EVENT_EFFECT_FIELDS
    assert effects["properties"]["energy"]["maximum"] == 10
    client = Mock()
    client.chat.completions.create.return_value.choices = []
    generator._chat_once(client, [], use_json_mode=True, json_schema=schema)
    assert (
        client.chat.completions.create.call_args.kwargs["response_format"]["type"]
        == "json_schema"
    )


def test_thinking_only_response_is_not_published_as_event_text(capsys):
    client = Mock()
    response = client.chat.completions.create.return_value
    response.choices = [Mock(message=Mock(content=""), finish_reason="length")]
    assert generator._chat_once(client, [], use_json_mode=True) == ""
    assert "--reasoning-effort none" in capsys.readouterr().out


def test_extract_json_preserves_urls_inside_valid_fenced_json():
    raw = '```json\n{"events":[{"desc":"参考 https://example.org/holiday"}]}\n```'
    assert (
        generator.extract_json(raw)["events"][0]["desc"]
        == "参考 https://example.org/holiday"
    )


def test_legacy_event_and_cc98_generation_still_use_compatible_api(monkeypatch):
    monkeypatch.setattr(
        generator, "call_llm", Mock(return_value=json.dumps({"events": [row()]}))
    )
    assert len(generator.generate_events(1)) == 1
    monkeypatch.setattr(
        generator, "call_llm", Mock(return_value=json.dumps({"posts": ["假期快乐！"]}))
    )
    assert len(generator.generate_cc98_posts(1)) == 1
