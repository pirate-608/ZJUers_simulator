"""Game-balance configuration loader.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.

Notes:
    This singleton reads `world/game_balance.json` and stays separate from
    system/environment settings in `app.core.config`.
"""
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class GameBalance:
    """Singleton loader for gameplay balance values."""
    _instance: Optional['GameBalance'] = None
    _config: Dict[str, Any] = {}
    _config_path: Path | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._config:
            self.load()

    @staticmethod
    def resolve_config_path(config_path: str | Path | None = None) -> Path:
        """Resolve the active game_balance.json path across local and Docker runs."""
        if config_path is not None:
            return Path(config_path)

        candidates = [
            Path("world/game_balance.json"),
            Path("/app/world/game_balance.json"),
            (
                Path(__file__).resolve().parent.parent.parent
                / "world"
                / "game_balance.json"
            ),
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def load(self, config_path: str | Path | None = None):
        """Load and validate the balance file path enough for runtime use."""
        try:
            path = self.resolve_config_path(config_path)
            if not path.exists():
                logger.error("配置文件不存在: %s", path)
                raise FileNotFoundError(f"配置文件不存在: {path}")

            with open(path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            self._config_path = path

            logger.info(
                "Game balance loaded: version=%s",
                self._config.get("version", "unknown"),
            )
        except Exception as e:
            logger.error("Failed to load game balance: %s", e)
            raise

    def reload(self, config_path: str | Path | None = None):
        """Hot-reload balance values after admin or world-data edits."""
        self._config = {}
        self.load(config_path or self._config_path)
        logger.info("Game balance reloaded")

    @property
    def raw(self) -> Dict[str, Any]:
        """Raw loaded balance dictionary."""
        return self._config

    @property
    def config_path(self) -> Path:
        """Path of the currently loaded balance file."""
        return self._config_path or self.resolve_config_path()

    @property
    def version(self) -> str:
        """Balance configuration version."""
        return self._config.get("version", "unknown")

    @property
    def tick_interval(self) -> int:
        """Tick interval in seconds."""
        return self._config.get("tick", {}).get("interval_seconds", 3)

    @property
    def base_energy_drain(self) -> float:
        """Base energy drain per tick before course-state weighting."""
        return self._config.get("tick", {}).get("base_energy_drain", 0.8)

    @property
    def base_mastery_growth(self) -> float:
        """Base course mastery growth before stat modifiers."""
        return self._config.get("tick", {}).get("base_mastery_growth", 0.5)

    @property
    def semester_config(self) -> Dict:
        """Semester duration and speed-mode configuration."""
        return self._config.get("semester", {})

    def get_semester_duration(self, semester_index: int) -> int:
        """Return configured duration for a semester index."""
        duration_map = self.semester_config.get("duration_by_index", {})
        default_duration = self.semester_config.get("default_duration_seconds", 360)
        return duration_map.get(str(semester_index), default_duration)

    @property
    def speed_modes(self) -> Dict:
        """Available speed-mode definitions."""
        return self.semester_config.get("speed_modes", {
            "1.0": {"label": "正常速度", "multiplier": 1.0}
        })

    @property
    def course_states(self) -> Dict[str, Dict]:
        """Course strategy configuration."""
        return self._config.get("course_states", {})

    def get_course_state_coeffs(self) -> Dict[int, Dict]:
        """Return course strategy coefficients keyed by integer state."""
        return {
            int(k): v
            for k, v in self.course_states.items()
        }

    @property
    def sanity_stress_modifiers(self) -> Dict:
        """Sanity and stress modifier configuration."""
        return self._config.get("sanity_stress_modifiers", {})

    def get_growth_modifiers(self) -> Dict:
        """Learning-growth modifier parameters."""
        return self.sanity_stress_modifiers.get("growth", {})

    def get_exam_modifiers(self) -> Dict:
        """Final-exam score modifier parameters."""
        return self.sanity_stress_modifiers.get("exam", {})

    @property
    def relax_actions(self) -> Dict[str, Dict]:
        """Relax-action configuration."""
        return self._config.get("relax_actions", {})

    def get_relax_action(self, action: str) -> Dict:
        """Return one relax-action configuration."""
        return self.relax_actions.get(action, {})

    def get_cooldown(self, action: str) -> int:
        """Return relax-action cooldown in seconds."""
        return self.relax_actions.get(action, {}).get("cooldown_seconds", 0)

    @property
    def events(self) -> Dict:
        """Random-event and DingTalk trigger configuration."""
        return self._config.get("events", {})

    def get_random_event_config(self) -> Dict:
        """Random-event trigger configuration."""
        return self.events.get("random_event", {})

    def get_dingtalk_config(self) -> Dict:
        """DingTalk trigger and contact-limit configuration."""
        return self.events.get("dingtalk", {})

    @property
    def dingtalk_max_contacts(self) -> int:
        """Maximum DingTalk contacts kept in the inbox."""
        try:
            value = int(self.get_dingtalk_config().get("max_contacts", 12))
        except (TypeError, ValueError):
            value = 12
        return max(1, value)

    @property
    def dingtalk_reuse_closed_contact_probability(self) -> float:
        """Probability of reusing a closed DingTalk contact."""
        try:
            value = float(
                self.get_dingtalk_config().get(
                    "reuse_closed_contact_probability", 0.7
                )
            )
        except (TypeError, ValueError):
            value = 0.7
        return max(0.0, min(1.0, value))

    @property
    def exam_config(self) -> Dict:
        """Final-exam settlement configuration."""
        return self._config.get("exam", {})

    @property
    def fail_threshold(self) -> int:
        """Score below which a course is considered failed."""
        return self.exam_config.get("fail_threshold", 60)

    @property
    def fail_sanity_penalty(self) -> int:
        """Sanity penalty applied per failed course."""
        return self.exam_config.get("fail_sanity_penalty_per_course", -10)

    @property
    def pass_all_bonus(self) -> int:
        """Sanity bonus when all courses pass."""
        return self.exam_config.get("pass_all_sanity_bonus", 10)

    @property
    def game_over_config(self) -> Dict:
        """Game Over threshold configuration."""
        return self._config.get("game_over", {})


balance = GameBalance()
