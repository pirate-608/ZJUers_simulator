import copy
import json
import os
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.admin import AdminAuditLog

ReplaceFunc = Callable[
    [str | bytes | os.PathLike[str], str | bytes | os.PathLike[str]], None
]


class BalanceConfigError(ValueError):
    """Raised when an admin-submitted balance config is invalid."""


@dataclass(frozen=True)
class BalanceField:
    name: str
    label: str
    path: tuple[str | int, ...]
    value_type: type[int] | type[float] | type[str]
    minimum: float | None = None
    maximum: float | None = None
    step: str | None = None
    help_text: str = ""

    @property
    def input_type(self) -> str:
        return "text" if self.value_type is str else "number"


@dataclass(frozen=True)
class BalanceSection:
    title: str
    description: str
    fields: list[BalanceField]


@dataclass(frozen=True)
class BalanceAuditSnapshot:
    log_id: int
    old_config: dict[str, Any]


def _field_name(path: Sequence[str | int]) -> str:
    return "__".join(str(part) for part in path)


def _get_path(config: Mapping[str, Any] | Sequence[Any], path: Sequence[str | int]):
    current: Any = config
    for part in path:
        if isinstance(part, int):
            if not isinstance(current, Sequence) or isinstance(current, (str, bytes)):
                raise BalanceConfigError(
                    f"配置路径 {'.'.join(map(str, path))} 不是列表"
                )
            try:
                current = current[part]
            except IndexError as exc:
                raise BalanceConfigError(
                    f"配置路径 {'.'.join(map(str, path))} 不存在"
                ) from exc
            continue

        if not isinstance(current, Mapping) or part not in current:
            raise BalanceConfigError(f"配置路径 {'.'.join(map(str, path))} 不存在")
        current = current[part]
    return current


def _set_path(
    config: dict[str, Any] | list[Any],
    path: Sequence[str | int],
    value: Any,
):
    current: Any = config
    for part in path[:-1]:
        current = current[part]
    current[path[-1]] = value


def _num(
    section: str,
    label: str,
    path: tuple[str | int, ...],
    value_type: type[int] | type[float],
    minimum: float | None,
    maximum: float | None,
    step: str | None = None,
    help_text: str = "",
) -> BalanceField:
    return BalanceField(
        name=_field_name(path),
        label=label,
        path=path,
        value_type=value_type,
        minimum=minimum,
        maximum=maximum,
        step=step or ("1" if value_type is int else "0.01"),
        help_text=help_text or section,
    )


def _text(
    label: str,
    path: tuple[str | int, ...],
    max_length: int,
    help_text: str = "",
) -> BalanceField:
    return BalanceField(
        name=_field_name(path),
        label=label,
        path=path,
        value_type=str,
        minimum=0,
        maximum=max_length,
        help_text=help_text,
    )


def build_balance_sections(config: Mapping[str, Any]) -> list[BalanceSection]:
    """Build editable field definitions from the current game_balance schema."""

    sections = _make_balance_sections(config)
    validate_balance_config(config, sections)
    return sections


def _make_balance_sections(config: Mapping[str, Any]) -> list[BalanceSection]:
    sections: list[BalanceSection] = [
        BalanceSection(
            "基础信息",
            "配置版本和后台备注。版本仅用于识别当前配置，不参与运行计算。",
            [
                _text("版本号", ("version",), 40, "例如 1.3.1"),
                _text("说明", ("description",), 240, "短说明，便于审计和回滚时辨认"),
            ],
        ),
        BalanceSection(
            "学期与速度",
            "学期时长单位为秒；速度档位 v1 只编辑既有 1x/1.5x/2x。",
            [
                *[
                    _num(
                        "semester",
                        f"第 {idx} 学期时长",
                        ("semester", "duration_by_index", str(idx)),
                        int,
                        60,
                        7200,
                    )
                    for idx in range(1, 9)
                ],
                _num(
                    "semester",
                    "默认学期时长",
                    ("semester", "default_duration_seconds"),
                    int,
                    60,
                    7200,
                ),
                _text("学期说明", ("semester", "description"), 240),
                *[
                    field
                    for speed in ("1.0", "1.5", "2.0")
                    for field in (
                        _text(
                            f"{speed} 标签",
                            ("semester", "speed_modes", speed, "label"),
                            40,
                        ),
                        _num(
                            "speed",
                            f"{speed} 倍率",
                            ("semester", "speed_modes", speed, "multiplier"),
                            float,
                            0.1,
                            5.0,
                            "0.1",
                        ),
                    )
                ],
            ],
        ),
        BalanceSection(
            "Tick 基础参数",
            "影响主循环节奏、精力消耗和基础掌握度增长。",
            [
                _num("tick", "Tick 间隔秒数", ("tick", "interval_seconds"), int, 1, 60),
                _num(
                    "tick",
                    "基础精力消耗",
                    ("tick", "base_energy_drain"),
                    float,
                    0,
                    100,
                ),
                _num(
                    "tick",
                    "基础掌握增长",
                    ("tick", "base_mastery_growth"),
                    float,
                    0,
                    100,
                ),
            ],
        ),
        BalanceSection(
            "课程策略",
            "只编辑摆/摸/卷三个既有策略，不支持新增策略。",
            [
                field
                for state in ("0", "1", "2")
                for field in (
                    _text(
                        f"策略 {state} 名称",
                        ("course_states", state, "name"),
                        20,
                    ),
                    _text(
                        f"策略 {state} 图标",
                        ("course_states", state, "emoji"),
                        8,
                    ),
                    _num(
                        "course_state",
                        f"策略 {state} 掌握增长",
                        ("course_states", state, "growth"),
                        float,
                        0,
                        100,
                    ),
                    _num(
                        "course_state",
                        f"策略 {state} 精力消耗",
                        ("course_states", state, "drain"),
                        float,
                        0,
                        100,
                    ),
                )
            ],
        ),
        BalanceSection(
            "心态与压力修正",
            "影响学习增长与考试结算。",
            [
                _num(
                    "growth",
                    "低心态临界值",
                    (
                        "sanity_stress_modifiers",
                        "growth",
                        "sanity",
                        "critical_low",
                        "threshold",
                    ),
                    int,
                    0,
                    100,
                ),
                _num(
                    "growth",
                    "低心态临界系数",
                    (
                        "sanity_stress_modifiers",
                        "growth",
                        "sanity",
                        "critical_low",
                        "factor",
                    ),
                    float,
                    0,
                    5,
                ),
                _num(
                    "growth",
                    "低心态斜率",
                    ("sanity_stress_modifiers", "growth", "sanity", "low_slope"),
                    float,
                    0,
                    5,
                    "0.001",
                ),
                _num(
                    "growth",
                    "高心态斜率",
                    ("sanity_stress_modifiers", "growth", "sanity", "high_slope"),
                    float,
                    0,
                    5,
                    "0.001",
                ),
                _num(
                    "growth",
                    "优秀心态阈值",
                    (
                        "sanity_stress_modifiers",
                        "growth",
                        "sanity",
                        "excellent",
                        "threshold",
                    ),
                    int,
                    0,
                    100,
                ),
                _num(
                    "growth",
                    "优秀心态系数",
                    (
                        "sanity_stress_modifiers",
                        "growth",
                        "sanity",
                        "excellent",
                        "factor",
                    ),
                    float,
                    0,
                    5,
                ),
                _num(
                    "growth",
                    "压力最佳下限",
                    ("sanity_stress_modifiers", "growth", "stress", "optimal_range", 0),
                    int,
                    0,
                    100,
                ),
                _num(
                    "growth",
                    "压力最佳上限",
                    ("sanity_stress_modifiers", "growth", "stress", "optimal_range", 1),
                    int,
                    0,
                    100,
                ),
                _num(
                    "growth",
                    "压力最佳系数",
                    ("sanity_stress_modifiers", "growth", "stress", "optimal_factor"),
                    float,
                    0,
                    5,
                ),
                _num(
                    "growth",
                    "压力非最佳系数",
                    (
                        "sanity_stress_modifiers",
                        "growth",
                        "stress",
                        "suboptimal_factor",
                    ),
                    float,
                    0,
                    5,
                ),
                _num(
                    "growth",
                    "压力极端系数",
                    ("sanity_stress_modifiers", "growth", "stress", "extreme_factor"),
                    float,
                    0,
                    5,
                ),
                _num(
                    "exam",
                    "考试低心态斜率",
                    ("sanity_stress_modifiers", "exam", "sanity", "low_slope"),
                    float,
                    0,
                    5,
                ),
                _num(
                    "exam",
                    "考试高心态斜率",
                    ("sanity_stress_modifiers", "exam", "sanity", "high_slope"),
                    float,
                    0,
                    5,
                ),
                _num(
                    "exam",
                    "考试优秀心态奖励",
                    ("sanity_stress_modifiers", "exam", "sanity", "excellent_bonus"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "exam",
                    "考试最佳压力奖励",
                    ("sanity_stress_modifiers", "exam", "stress", "optimal_bonus"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "exam",
                    "考试非最佳压力惩罚",
                    ("sanity_stress_modifiers", "exam", "stress", "suboptimal_penalty"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "exam",
                    "考试极端压力惩罚",
                    ("sanity_stress_modifiers", "exam", "stress", "extreme_penalty"),
                    int,
                    -100,
                    100,
                ),
            ],
        ),
        BalanceSection(
            "休闲动作",
            "只编辑现有动作和 CC98 现有效果，不支持新增动作或效果。",
            [
                *[
                    field
                    for action, label in (
                        ("gym", "健身"),
                        ("game", "游戏"),
                        ("walk", "散步"),
                        ("cc98", "CC98"),
                    )
                    for field in (
                        _text(
                            f"{label} 显示名",
                            ("relax_actions", action, "label"),
                            40,
                        ),
                        _num(
                            "relax",
                            f"{label} 冷却秒数",
                            ("relax_actions", action, "cooldown_seconds"),
                            int,
                            0,
                            3600,
                        ),
                    )
                ],
                _num(
                    "relax",
                    "健身精力成本",
                    ("relax_actions", "gym", "energy_cost"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "relax",
                    "健身精力恢复",
                    ("relax_actions", "gym", "energy_gain"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "relax",
                    "健身心态变化",
                    ("relax_actions", "gym", "sanity_gain"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "relax",
                    "健身压力变化",
                    ("relax_actions", "gym", "stress_change"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "relax",
                    "健身最低精力",
                    ("relax_actions", "gym", "min_energy_required"),
                    int,
                    0,
                    100,
                ),
                _num(
                    "relax",
                    "游戏精力成本",
                    ("relax_actions", "game", "energy_cost"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "relax",
                    "游戏心态变化",
                    ("relax_actions", "game", "sanity_gain"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "relax",
                    "散步压力变化",
                    ("relax_actions", "walk", "stress_change"),
                    int,
                    -100,
                    100,
                ),
                *[
                    field
                    for idx in range(
                        len(_get_path(config, ("relax_actions", "cc98", "effects")))
                    )
                    for field in (
                        _num(
                            "cc98",
                            f"CC98 效果 {idx + 1} 权重",
                            ("relax_actions", "cc98", "effects", idx, "weight"),
                            float,
                            0,
                            1,
                            "0.01",
                        ),
                        _num(
                            "cc98",
                            f"CC98 效果 {idx + 1} 心态",
                            ("relax_actions", "cc98", "effects", idx, "sanity"),
                            int,
                            -100,
                            100,
                        ),
                        _num(
                            "cc98",
                            f"CC98 效果 {idx + 1} 压力",
                            ("relax_actions", "cc98", "effects", idx, "stress"),
                            int,
                            -100,
                            100,
                        ),
                    )
                ],
            ],
        ),
        BalanceSection(
            "事件与钉钉",
            "触发概率范围为 0 到 1。",
            [
                _num(
                    "event",
                    "随机事件检查 tick 间隔",
                    ("events", "random_event", "check_interval_ticks"),
                    int,
                    1,
                    1000,
                ),
                _num(
                    "event",
                    "随机事件触发概率",
                    ("events", "random_event", "trigger_probability"),
                    float,
                    0,
                    1,
                    "0.01",
                ),
                _num(
                    "event",
                    "钉钉检查 tick 间隔",
                    ("events", "dingtalk", "check_interval_ticks"),
                    int,
                    1,
                    1000,
                ),
                _num(
                    "event",
                    "钉钉触发概率",
                    ("events", "dingtalk", "trigger_probability"),
                    float,
                    0,
                    1,
                    "0.01",
                ),
            ],
        ),
        BalanceSection(
            "考试与结束",
            "控制挂科阈值、考试奖惩和 Game Over 阈值。",
            [
                _num("exam", "挂科阈值", ("exam", "fail_threshold"), int, 0, 100),
                _num(
                    "exam",
                    "每门挂科心态惩罚",
                    ("exam", "fail_sanity_penalty_per_course"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "exam",
                    "全通过心态奖励",
                    ("exam", "pass_all_sanity_bonus"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "game_over",
                    "心态 Game Over 阈值",
                    ("game_over", "sanity_threshold"),
                    int,
                    -100,
                    100,
                ),
                _num(
                    "game_over",
                    "精力 Game Over 阈值",
                    ("game_over", "energy_threshold"),
                    int,
                    -100,
                    100,
                ),
            ],
        ),
    ]
    return sections


def config_to_form_data(config: Mapping[str, Any]) -> dict[str, str]:
    form: dict[str, str] = {}
    for field in iter_balance_fields(config):
        value = _get_path(config, field.path)
        form[field.name] = str(value)
    return form


def iter_balance_fields(config: Mapping[str, Any]) -> Iterable[BalanceField]:
    for section in build_balance_sections(config):
        yield from section.fields


def build_config_from_form(
    original_config: Mapping[str, Any],
    form_data: Mapping[str, Any],
) -> dict[str, Any]:
    next_config = copy.deepcopy(dict(original_config))
    fields = list(iter_balance_fields(original_config))
    errors: list[str] = []

    for field in fields:
        if field.name not in form_data:
            errors.append(f"缺少字段：{field.label}")
            continue
        raw_value = str(form_data[field.name]).strip()
        try:
            value = parse_field_value(field, raw_value)
        except BalanceConfigError as exc:
            errors.append(str(exc))
            continue
        _set_path(next_config, field.path, value)

    if errors:
        raise BalanceConfigError("；".join(errors))
    validate_balance_config(
        next_config,
        sections=build_balance_sections(original_config),
    )
    return next_config


def parse_field_value(field: BalanceField, raw_value: str) -> int | float | str:
    if field.value_type is str:
        if raw_value == "":
            raise BalanceConfigError(f"{field.label} 不能为空")
        if field.maximum is not None and len(raw_value) > int(field.maximum):
            raise BalanceConfigError(
                f"{field.label} 不能超过 {int(field.maximum)} 个字符"
            )
        return raw_value

    try:
        if field.value_type is int:
            value: int | float = int(raw_value)
        else:
            value = float(raw_value)
    except ValueError as exc:
        raise BalanceConfigError(f"{field.label} 必须是数字") from exc

    if field.minimum is not None and value < field.minimum:
        raise BalanceConfigError(f"{field.label} 不能小于 {field.minimum:g}")
    if field.maximum is not None and value > field.maximum:
        raise BalanceConfigError(f"{field.label} 不能大于 {field.maximum:g}")
    return value


def validate_balance_config(
    config: Mapping[str, Any],
    sections: list[BalanceSection] | None = None,
) -> None:
    sections = sections or _make_balance_sections(config)
    for section in sections:
        for field in section.fields:
            value = _get_path(config, field.path)
            parse_field_value(field, str(value))

    stress_range = _get_path(
        config, ("sanity_stress_modifiers", "growth", "stress", "optimal_range")
    )
    if stress_range[0] > stress_range[1]:
        raise BalanceConfigError("压力最佳下限不能大于压力最佳上限")

    cc98_effects = _get_path(config, ("relax_actions", "cc98", "effects"))
    if not isinstance(cc98_effects, list) or not cc98_effects:
        raise BalanceConfigError("CC98 至少需要保留一个效果")
    weight_sum = sum(float(item.get("weight", 0)) for item in cc98_effects)
    if not 0.99 <= weight_sum <= 1.01:
        raise BalanceConfigError("CC98 效果权重之和必须等于 1")


def summarize_balance_config(config: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": config.get("version"),
        "tick_interval": _get_path(config, ("tick", "interval_seconds")),
        "base_energy_drain": _get_path(config, ("tick", "base_energy_drain")),
        "base_mastery_growth": _get_path(config, ("tick", "base_mastery_growth")),
        "semester_durations": _get_path(config, ("semester", "duration_by_index")),
        "random_event_probability": _get_path(
            config, ("events", "random_event", "trigger_probability")
        ),
        "dingtalk_probability": _get_path(
            config, ("events", "dingtalk", "trigger_probability")
        ),
        "relax_cooldowns": {
            action: data.get("cooldown_seconds")
            for action, data in _get_path(config, ("relax_actions",)).items()
        },
    }


def diff_balance_configs(
    old_config: Mapping[str, Any],
    new_config: Mapping[str, Any],
) -> list[str]:
    changed: list[str] = []
    for field in iter_balance_fields(old_config):
        old_value = _get_path(old_config, field.path)
        new_value = _get_path(new_config, field.path)
        if old_value != new_value:
            changed.append(".".join(str(part) for part in field.path))
    return changed


def write_balance_config_atomic(
    path: Path,
    config: Mapping[str, Any],
    replace_func: ReplaceFunc = os.replace,
) -> None:
    validate_balance_config(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    tmp_path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        replace_func(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def publish_balance_config(
    path: Path,
    config: Mapping[str, Any],
    reload_func: Callable[[str], Any],
) -> None:
    write_balance_config_atomic(path, config)
    reload_func(str(path))


def latest_balance_update_snapshot(session: Session) -> BalanceAuditSnapshot | None:
    log = (
        session.query(AdminAuditLog)
        .filter(
            AdminAuditLog.action == "balance_update",
            AdminAuditLog.target_type == "game_balance",
        )
        .order_by(AdminAuditLog.id.desc())
        .first()
    )
    if not log or not log.details:
        return None
    old_config = log.details.get("old_config")
    if not isinstance(old_config, dict):
        return None
    validate_balance_config(old_config)
    return BalanceAuditSnapshot(log_id=int(log.id), old_config=old_config)
