import json

import pytest

from app.game.stat_definitions import StatDefinitions


def test_stat_definitions_load_current_world_config():
    registry = StatDefinitions()

    assert registry.initial_budget == 300
    assert registry.allocatable_ids == ["iq", "eq", "luck", "charm"]
    assert registry.initial_default_stats() == {
        "iq": 100,
        "eq": 100,
        "luck": 50,
        "charm": 50,
    }
    assert "charm" in registry.item_effect_fields
    assert "gold" not in registry.item_effect_fields
    assert "gold" in registry.event_effect_fields


def test_normalize_initial_allocations_rejects_unknown_field():
    registry = StatDefinitions()

    with pytest.raises(ValueError, match="不支持"):
        registry.normalize_initial_allocations(
            {"iq": 100, "eq": 100, "luck": 50, "charm": 50, "power": 1}
        )


def test_normalize_initial_allocations_rejects_bad_budget():
    registry = StatDefinitions()

    with pytest.raises(ValueError, match="初始总点数"):
        registry.normalize_initial_allocations(
            {"iq": 100, "eq": 100, "luck": 60, "charm": 60}
        )


def test_invalid_config_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "stat_definitions.json"
    path.write_text(
        json.dumps(
            {
                "version": "bad",
                "initial_budget": 100,
                "stats": [
                    {
                        "id": "iq",
                        "label": "IQ",
                        "default": 50,
                        "min": 0,
                        "max": 100,
                        "allocatable": True,
                        "show_in_character_create": True,
                    },
                    {
                        "id": "iq",
                        "label": "IQ",
                        "default": 50,
                        "min": 0,
                        "max": 100,
                        "allocatable": True,
                        "show_in_character_create": True,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duplicate stat ids"):
        StatDefinitions(path)
