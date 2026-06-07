import asyncio
import hashlib
import json
import logging
import math
import random
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Literal, Optional

from sqlalchemy import update

from app.content.event_library import pick_cc98_post, pick_random_event
from app.core.database import AsyncSessionLocal
from app.core.events import GameEvent
from app.core.llm import (
    generate_cc98_post,
    generate_dingtalk_message,
    generate_random_event,
)
from app.game.balance import balance  # 游戏数值配置
from app.models.user import User
from app.repositories.redis_repo import RedisRepository
from app.schemas.dingtalk import (
    DingTalkContact,
    DingTalkMessage,
    DingTalkReplyOption,
    DingTalkRoundState,
    build_contact_id,
    is_replyable_role,
    new_message_id,
    now_ts,
)
from app.services.game_service import GameService
from app.services.save_service import SaveService

logger = logging.getLogger(__name__)


class GameMode:
    LIBRARY = "library"
    AI = "ai"
    HYBRID = "hybrid"

    @classmethod
    def from_str(cls, s: str):
        s = s.lower()
        if s == "ai":
            return cls.AI
        if s == "library":
            return cls.LIBRARY
        return cls.HYBRID


class GameEngine:
    async def emit(self, event_type: str, data: dict, msg: str | None = None):
        if msg:
            await self.event_queue.put(
                GameEvent(
                    user_id=self.user_id,
                    event_type="event",
                    data={"data": {"desc": msg}},
                )
            )
        await self.event_queue.put(
            GameEvent(user_id=self.user_id, event_type=event_type, data=data)
        )

    async def _emit_feedback(
        self,
        title: str,
        message: str,
        kind: str = "info",
        auto_close_ms: int = 3000,
    ):
        await self.emit(
            "feedback",
            {
                "data": {
                    "title": title,
                    "message": message,
                    "kind": kind,
                    "auto_close_ms": auto_close_ms,
                }
            },
        )

    def resume(self):
        if not self.is_running:
            self.start()
            # 推送最新状态和通知消息
            asyncio.create_task(self._push_update())
            asyncio.create_task(self.emit("resumed", {"msg": "游戏已继续。"}))

    def pause(self):
        self.is_running = False
        # 可选：通知前端已暂停
        asyncio.create_task(self.emit("paused", {"msg": "游戏已暂停，可随时继续。"}))

    def __init__(
        self,
        user_id: str,
        repo: RedisRepository,
        save_service: SaveService,
        game_service: GameService,
        db_factory: Callable[[], Any] = AsyncSessionLocal,
        llm_override: Optional[dict[str, Any]] = None,
        save_slot: int = 1,
    ):
        self.user_id = user_id
        self.repo = repo
        self.save_service = save_service
        self.game_service = game_service
        self.db_factory = db_factory
        self.llm_override = llm_override
        self.save_slot = save_slot
        self.event_queue: asyncio.Queue[GameEvent] = asyncio.Queue()
        self.is_running = False
        self._run_task: asyncio.Task | None = None
        self._background_tasks: set[asyncio.Task] = set()
        self._random_event_inflight = False
        self._dingtalk_inflight = False
        self._dingtalk_state_lock = asyncio.Lock()
        self._ttl_refresh_interval_seconds = 600
        self._last_ttl_refresh = 0.0
        # ✨ 新增：倍速乘数，默认为 1.0
        self.speed_multiplier = 1.0

        # 内容生成模式
        self.mode: str = GameMode.HYBRID
        self.llm_available: bool = True
        self._llm_probed: bool = False

        # 预设成就路径
        self.achievement_path = Path("/app/world/achievements.json")
        if not self.achievement_path.exists():
            self.achievement_path = (
                Path(__file__).resolve().parent.parent.parent
                / "world"
                / "achievements.json"
            )

        # ========== 从配置文件加载数值参数 ==========
        # 状态定义: 0=摆(Lay Flat), 1=摸(Chill), 2=卷(Hardcore)
        self.COURSE_STATE_COEFFS = balance.get_course_state_coeffs()
        self.BASE_ENERGY_DRAIN = balance.base_energy_drain
        self.BASE_MASTERY_GROWTH = balance.base_mastery_growth

    def _make_dingtalk_message(
        self,
        speaker: Literal["npc", "player", "system"],
        content: str,
        round_id: str | None = None,
    ) -> DingTalkMessage:
        return DingTalkMessage(
            message_id=new_message_id(),
            speaker=speaker,
            content=str(content or "").strip(),
            created_at=now_ts(),
            round_id=round_id,
        )

    def _coerce_dingtalk_options(
        self, raw_options: Any, role: str
    ) -> list[DingTalkReplyOption]:
        if not is_replyable_role(role):
            return []
        options: list[DingTalkReplyOption] = []
        if isinstance(raw_options, list):
            for idx, item in enumerate(raw_options[:3]):
                if isinstance(item, DingTalkReplyOption):
                    options.append(item)
                    continue
                if isinstance(item, str):
                    text = item.strip()
                elif isinstance(item, dict):
                    text = str(item.get("text") or item.get("content") or "").strip()
                else:
                    text = ""
                if text:
                    option_id = (
                        str(item.get("option_id"))
                        if isinstance(item, dict) and item.get("option_id")
                        else f"opt_{idx + 1}"
                    )
                    options.append(
                        DingTalkReplyOption(option_id=option_id, text=text[:80])
                    )
        if options:
            return options
        fallback = {
            "roommate": ["哈哈收到", "我马上看看", "你先别急"],
            "classmate": ["可以，我看一下", "等我整理一下资料", "我也有点懵"],
            "friend": ["晚上再说？", "可以啊", "你这也太会了"],
            "teaching_assistant": ["谢谢助教提醒", "我有个问题想问", "我会尽快完成"],
            "teacher": ["谢谢老师", "我会提前准备", "我还有一个问题"],
            "crush": ["还好，你呢？", "我也在想这个", "要不要一起去？"],
        }.get(role, ["好的收到", "我想想怎么回", "可以再说详细点吗"])
        return [
            DingTalkReplyOption(option_id=f"opt_{idx + 1}", text=text)
            for idx, text in enumerate(fallback[:3])
        ]

    def _normalize_dingtalk_payload(
        self, msg_data: dict[str, Any]
    ) -> tuple[dict[str, Any], str, list[DingTalkReplyOption]]:
        contact_raw = msg_data.get("contact")
        contact = contact_raw if isinstance(contact_raw, dict) else {}
        sender = str(contact.get("sender") or msg_data.get("sender") or "未知")
        role = str(contact.get("role") or msg_data.get("role") or "unknown")
        contact_id = str(
            contact.get("contact_id") or build_contact_id(sender, role)
        )
        is_urgent = bool(contact.get("is_urgent", msg_data.get("is_urgent", False)))
        content = ""
        message_raw = msg_data.get("message")
        if isinstance(message_raw, dict):
            content = str(message_raw.get("content") or "").strip()
        if not content:
            content = str(msg_data.get("content") or "").strip()
        options = self._coerce_dingtalk_options(msg_data.get("reply_options"), role)
        if not is_replyable_role(role):
            options = []
        return (
            {
                "contact_id": contact_id,
                "sender": sender,
                "role": role,
                "is_replyable": is_replyable_role(role),
                "is_urgent": is_urgent,
            },
            content,
            options,
        )

    async def _emit_dingtalk_contact_update(self, contact: DingTalkContact):
        await self.emit(
            "dingtalk_thread_update",
            {"contact": contact.model_dump()},
        )

    async def _store_dingtalk_npc_message(
        self, msg_data: dict[str, Any]
    ) -> DingTalkContact | None:
        contact_meta, content, options = self._normalize_dingtalk_payload(msg_data)
        if not content:
            return None
        async with self._dingtalk_state_lock:
            state = await self.repo.get_dingtalk_state()
            contact = state.contacts.get(contact_meta["contact_id"])
            if contact and contact.round.status == "open":
                return None
            if not contact:
                contact = DingTalkContact(**contact_meta)
            else:
                contact.sender = contact_meta["sender"]
                contact.role = contact_meta["role"]
                contact.is_replyable = bool(contact_meta["is_replyable"])
                contact.is_urgent = bool(contact_meta["is_urgent"])

            round_id = None
            if contact.is_replyable and options:
                contact.round = DingTalkRoundState(
                    round_id=f"dtr_{new_message_id()[4:]}",
                    status="open",
                    player_reply_count=0,
                )
                round_id = contact.round.round_id
                contact.pending_options = options
            else:
                contact.pending_options = []
                contact.round = DingTalkRoundState()

            message = self._make_dingtalk_message("npc", content, round_id=round_id)
            contact.messages.append(message)
            contact.unread_count += 1
            contact.last_message_at = message.created_at
            contact.trim_messages()
            state.contacts[contact.contact_id] = contact
            await self.repo.set_dingtalk_state(state)
            return contact

    def _fallback_dingtalk_reply_result(
        self, contact: DingTalkContact, reply_count: int
    ) -> dict[str, Any]:
        if reply_count >= 3:
            return {
                "content": "嗯嗯，那这事先这样。之后有情况再和你说。",
                "settlement": {
                    "desc": f"你和{contact.sender}聊了一会儿，心情有些变化。",
                    "effects": {"sanity": 1},
                },
            }
        return {
            "content": "收到，我懂你的意思了。",
            "reply_options": self._coerce_dingtalk_options([], contact.role),
        }

    async def _generate_dingtalk_reply_result(
        self,
        contact: DingTalkContact,
        player_reply: str,
        reply_count: int,
        stats: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.llm_override:
            try:
                from app.core.dingtalk_llm import (
                    generate_dingtalk_reply_via_m2her,
                    get_character_by_contact_id,
                )

                character = get_character_by_contact_id(contact.contact_id) or {
                    "name": contact.sender,
                    "role": contact.role,
                    "content": f"你是{contact.sender}。",
                    "examples": [],
                }
                history = [m.model_dump() for m in contact.messages]
                generated = await generate_dingtalk_reply_via_m2her(
                    character, stats, history, player_reply, reply_count
                )
                if generated:
                    return generated
            except Exception as e:
                logger.warning("M2-her dingtalk reply fallback: %s", e)
        return self._fallback_dingtalk_reply_result(contact, reply_count)

    def _sanitize_dingtalk_effects(
        self, settlement: Any
    ) -> tuple[str, dict[str, int]]:
        if not isinstance(settlement, dict):
            return "这轮对话没有产生明显影响。", {}
        desc = str(settlement.get("desc") or "这轮对话产生了一些影响。").strip()
        effects_raw = settlement.get("effects")
        effects_raw = effects_raw if isinstance(effects_raw, dict) else {}
        effects: dict[str, int] = {}
        for key, value in effects_raw.items():
            max_delta = self._ALLOWED_EFFECT_FIELDS.get(str(key))
            if max_delta is None:
                continue
            try:
                delta = int(value)
            except (TypeError, ValueError):
                continue
            effects[str(key)] = max(-max_delta, min(max_delta, delta))
        return desc, effects

    async def _apply_dingtalk_settlement(
        self, contact: DingTalkContact, settlement: Any
    ) -> dict[str, Any]:
        desc, effects = self._sanitize_dingtalk_effects(settlement)
        applied: dict[str, dict[str, int]] = {}
        for field, delta in effects.items():
            if delta == 0:
                continue
            new_value = await self.repo.update_stat_safe(field, delta)
            applied[field] = {"delta": delta, "value": new_value}
        message = desc if applied else "这轮对话平静结束，没有明显数值变化。"
        await self.emit("event", {"data": {"desc": f"钉钉：{message}"}})
        await self._emit_feedback(
            "钉钉对话",
            message,
            kind="info",
            auto_close_ms=3500,
        )
        await self.emit(
            "dingtalk_effect",
            {
                "contact_id": contact.contact_id,
                "summary": message,
                "effects": applied,
            },
        )
        await self._push_update()
        return {"summary": message, "effects": applied}

    def _track_task(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)
        return task

    def start(self):
        if self.is_running and self._run_task and not self._run_task.done():
            return
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
        self.is_running = True
        self._run_task = asyncio.create_task(self.run_loop())

    async def check_and_trigger_gameover(self) -> bool:
        """检测精力/心态是否归零并触发game over"""
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        if not stats:
            return False
        try:
            # 使用 get(..., 100) 确保即便 Key 不存在也能逻辑运行
            sanity = int(stats.get("sanity", 100))
            energy = int(stats.get("energy", 100))

            reason = ""
            if sanity <= 0:
                reason = "心态崩了，天台风好大..."
            elif energy <= 0:
                reason = "精力耗尽，远去的救护车..."

            if reason:
                await self.emit(
                    "game_over",
                    {"reason": reason, "restartable": True},
                )
                self.stop()
                return True
        except (ValueError, TypeError):
            pass
        return False

    def _sanity_stress_growth_factor(self, sanity, stress):
        """
        心态修正：50为基准，低于50负面影响，极低(<20)最大-40%；高于50正面提升，最佳(80+)+20%
        压力修正：40-70为最佳区间，区间内+30%，区间外-15%，极端（<20或>90）-40%
        """
        # 从配置加载参数
        growth_mod = balance.get_growth_modifiers()
        sanity_cfg = growth_mod.get("sanity", {})
        stress_cfg = growth_mod.get("stress", {})

        # 心态修正
        critical_threshold = sanity_cfg.get("critical_low", {}).get("threshold", 20)
        critical_factor = sanity_cfg.get("critical_low", {}).get("factor", 0.6)
        low_slope = sanity_cfg.get("low_slope", 0.013)
        high_slope = sanity_cfg.get("high_slope", 0.007)
        excellent_threshold = sanity_cfg.get("excellent", {}).get("threshold", 80)
        excellent_factor = sanity_cfg.get("excellent", {}).get("factor", 1.2)

        if sanity < critical_threshold:
            sanity_factor = critical_factor
        elif sanity < 50:
            sanity_factor = 1 - (50 - sanity) * low_slope
        elif sanity >= excellent_threshold:
            sanity_factor = excellent_factor
        elif sanity > 50:
            sanity_factor = 1 + (sanity - 50) * high_slope
        else:
            sanity_factor = 1.0

        # 压力修正
        optimal_range = stress_cfg.get("optimal_range", [40, 70])
        optimal_factor = stress_cfg.get("optimal_factor", 1.3)
        suboptimal_factor = stress_cfg.get("suboptimal_factor", 0.85)
        extreme_factor = stress_cfg.get("extreme_factor", 0.6)

        if optimal_range[0] <= stress <= optimal_range[1]:
            stress_factor = optimal_factor
        elif 20 <= stress < optimal_range[0] or optimal_range[1] < stress <= 90:
            stress_factor = suboptimal_factor
        else:
            stress_factor = extreme_factor

        return sanity_factor * stress_factor

    def _sanity_stress_exam_factor(self, sanity, stress):
        """
        心态修正：50为基准，低于50分数线性下滑，最低-15分，高于50最多+6分
        压力修正：40-70区间+6分，区间外-5分，极端（<20或>90）-10分
        """
        # 从配置加载参数
        exam_mod = balance.get_exam_modifiers()
        sanity_cfg = exam_mod.get("sanity", {})
        stress_cfg = exam_mod.get("stress", {})

        # 心态
        low_slope = sanity_cfg.get("low_slope", 0.3)
        high_slope = sanity_cfg.get("high_slope", 0.12)
        excellent_bonus = sanity_cfg.get("excellent_bonus", 6)

        if sanity < 50:
            sanity_bonus = (sanity - 50) * low_slope
        elif sanity >= 80:
            sanity_bonus = excellent_bonus
        elif sanity > 50:
            sanity_bonus = (sanity - 50) * high_slope
        else:
            sanity_bonus = 0

        # 压力
        optimal_bonus = stress_cfg.get("optimal_bonus", 6)
        suboptimal_penalty = stress_cfg.get("suboptimal_penalty", -5)
        extreme_penalty = stress_cfg.get("extreme_penalty", -10)

        if 40 <= stress <= 70:
            stress_bonus = optimal_bonus
        elif 20 <= stress < 40 or 70 < stress <= 90:
            stress_bonus = suboptimal_penalty
        else:
            stress_bonus = extreme_penalty

        return sanity_bonus + stress_bonus

    async def run_loop(self):
        """核心循环：基于状态的资源分配计算"""
        logger.info(f"State-based Game loop started for {self.user_id}")

        tick_count = 0
        try:
            while self.is_running:
                # ✨ 核心：真实的睡眠时间被倍速缩短！
                # 例如 2.0 倍速下，真实世界只睡 1.5 秒
                await asyncio.sleep(3.0 / self.speed_multiplier)
                if not self.is_running:
                    break
                tick_count += 1

                # ✨ 核心：但游戏内的虚拟时间，永远坚定地往前走 3 秒！
                # 注意：不能用 update_stat_safe，
                # 因为它的 max_val 默认值 200 会截断计时器
                elapsed = await self.repo.update_stat("elapsed_game_time", 3)

                # 动态获取当前学期时长上限
                snapshot_for_time = await self.repo.get_snapshot()
                sem_idx = int(snapshot_for_time.stats.semester_idx or 1)
                sem_duration = balance.get_semester_duration(sem_idx)
                if elapsed >= sem_duration:
                    logger.info(
                        "Semester time exceeded for %s, triggering final exam.",
                        self.user_id,
                    )
                    self.stop()
                    await self._handle_final_exam()
                    break

                # 低频 TTL 刷新：仅对活跃玩家做防线更新
                now_ts = asyncio.get_running_loop().time()
                if (
                    now_ts - self._last_ttl_refresh
                    >= self._ttl_refresh_interval_seconds
                ):
                    await self.repo.touch_ttl()
                    self._last_ttl_refresh = now_ts

                # 1. 基础检查
                if await self.check_and_trigger_gameover():
                    break

                # 2. 获取计算所需数据 (并行获取以提升性能)
                snapshot = await self.repo.get_snapshot()
                stats = snapshot.stats.model_dump()
                course_states_raw = snapshot.course_states

                # 解析课程信息
                try:
                    course_info = json.loads(stats.get("course_info_json", "[]"))
                except (TypeError, json.JSONDecodeError):
                    course_info = []

                # 如果没有课程（如假期），只自然恢复或轻微消耗
                if not course_info:
                    logger.warning(
                        "[%s] course_info is EMPTY, skipping mastery growth",
                        self.user_id,
                    )
                    await self.repo.update_stat_safe("energy", 1)  # 假期回血
                    await self._push_update()
                    continue

                # 3. 核心算法：加权计算
                # -------------------------------------------------
                total_credits = sum(c.get("credits", 1.0) for c in course_info)
                if total_credits <= 0:
                    total_credits = 1.0

                total_drain_factor = 0.0
                mastery_updates = {}

                # 遍历每门课，计算这一跳的进度和对总精力的负担
                for course in course_info:
                    c_id = str(course.get("id"))
                    credits = float(course.get("credits", 1.0))
                    # 获取该课当前状态 (默认1:摸)
                    state_val = int(course_states_raw.get(c_id, 1))
                    coeffs = self.COURSE_STATE_COEFFS.get(
                        state_val, self.COURSE_STATE_COEFFS[1]
                    )
                    # A. 计算擅长度增量
                    iq_buff = (int(stats.get("iq", 100)) - 100) * 0.01
                    # 仅在摸/卷状态下引入心态压力修正
                    if state_val in (1, 2):
                        sanity = int(stats.get("sanity", 80))
                        stress = int(stats.get("stress", 40))
                        factor = self._sanity_stress_growth_factor(sanity, stress)
                    else:
                        factor = 1.0
                    actual_growth = (
                        self.BASE_MASTERY_GROWTH
                        * coeffs["growth"]
                        * (1 + iq_buff)
                        * factor
                    )
                    if actual_growth > 0:
                        mastery_updates[c_id] = actual_growth
                    # B. 计算精力消耗权重
                    weight = credits / total_credits
                    total_drain_factor += weight * coeffs["drain"]

                # 4. 执行更新
                # -------------------------------------------------
                # 批量更新课程进度
                if mastery_updates:
                    await self.repo.batch_update_course_mastery(mastery_updates)
                    if tick_count <= 3:  # 只在前几个 tick 打印诊断信息
                        logger.info(
                            "[%s] tick#%s mastery_updates: %s",
                            self.user_id,
                            tick_count,
                            mastery_updates,
                        )
                else:
                    if tick_count <= 3:
                        logger.warning(
                            "[%s] tick#%s mastery_updates is EMPTY",
                            self.user_id,
                            tick_count,
                        )

                # 结算总精力消耗
                # 最终消耗 = 基础消耗 * 加权系数（保留浮点数精度）
                final_energy_cost_float = self.BASE_ENERGY_DRAIN * total_drain_factor

                # 修复：只有drain系数真正接近0（全摆烂）才回血
                # 避免"全摸"状态因int截断误判为摆烂
                if final_energy_cost_float < 0.3:  # 真正的摆烂阈值
                    await self.repo.update_stat_safe("energy", 2)
                    await self.repo.update_stat_safe("stress", -2)  # 摆烂降压
                else:
                    # 向上取整，确保至少消耗1点精力
                    final_energy_cost = max(1, math.ceil(final_energy_cost_float))
                    await self.repo.update_stat_safe("energy", -final_energy_cost)
                    # 卷多了压力大：如果消耗系数高，增加压力
                    if total_drain_factor > 1.5:
                        await self.repo.update_stat_safe("stress", 1)

                # 5. 随机事件与成就 (从配置读取频率) - 仅在游戏运行时触发
                if self.is_running:
                    event_cfg = balance.get_random_event_config()
                    event_interval = event_cfg.get("check_interval_ticks", 5)
                    event_probability = event_cfg.get("trigger_probability", 0.4)

                    if tick_count % event_interval == 0:
                        if random.random() < event_probability:
                            if not self._random_event_inflight:
                                self._track_task(self._trigger_random_event())
                        await self._check_achievements()

                    # [新增] 6. 钉钉消息 (从配置读取频率) - 仅在游戏运行时触发
                    dingtalk_cfg = balance.get_dingtalk_config()
                    dingtalk_interval = dingtalk_cfg.get("check_interval_ticks", 10)
                    dingtalk_probability = dingtalk_cfg.get("trigger_probability", 0.3)

                    if (
                        tick_count % dingtalk_interval == 0
                        and random.random() < dingtalk_probability
                    ):
                        if not self._dingtalk_inflight:
                            self._track_task(self._trigger_dingtalk_message())

                await self._push_update()

        except Exception as e:
            logger.error(f"Engine Loop Error: {e}", exc_info=True)
            self.stop()

    async def process_action(self, action_data: dict):
        action = action_data.get("action")
        target = action_data.get("target")  # 通常是 course_id
        value = action_data.get("value")  # 新增: 状态值 0/1/2
        if action in {"start", "get_state"}:
            await self._push_update()
            return
        if action == "pause":
            self.pause()
            return
        if action == "resume":
            self.resume()
            return
        if action == "restart":
            self.stop()
            initial_stats = self._build_initial_stats("ZJUer")
            await self.repo.set_game_data(initial_stats)
            await self.emit("init", {"data": initial_stats})
            self.start()
            return

        # ✨ 新增：真正接管全局倍速
        if action == "set_speed":
            try:
                speed = float(action_data.get("speed", 1.0))
            except (TypeError, ValueError):
                return
            if speed < 0.5 or speed > 5.0:
                return
            self.speed_multiplier = speed
            return

        # 切换内容生成模式
        if action == "set_mode":
            raw = action_data.get("mode", "hybrid")
            new_mode = GameMode.from_str(raw)
            if new_mode == GameMode.AI and self._llm_probed and not self.llm_available:
                await self.emit(
                    "toast",
                    {"message": "LLM API 不可用，已保持在当前模式", "level": "warning"},
                )
            else:
                self.mode = new_mode
                await self.emit(
                    "mode_changed",
                    {"mode": self.mode, "llm_available": self.llm_available},
                )
            # 首次收到 mode 相关请求时触发后台探测
            if not self._llm_probed:
                self._llm_probed = True
                self._track_task(self._probe_llm())
            return

        # [新增] 切换课程状态指令
        if action == "change_course_state":
            if target and value is not None:
                # 更新 Redis 状态
                await self.repo.set_course_state(target, int(value))
                # 立即推送一次更新，让前端看到精力预估变化(可选，run_loop也会推)
                await self._push_update()
            return

        if action == "dingtalk_mark_read":
            contact_id = str(action_data.get("contact_id") or "").strip()
            if not contact_id:
                return
            state = await self.repo.mark_dingtalk_read(contact_id)
            contact = state.contacts.get(contact_id)
            if contact:
                await self._emit_dingtalk_contact_update(contact)
            return

        if action == "dingtalk_reply":
            await self._handle_dingtalk_reply(action_data)
            return

        # [保留] 其它一次性动作 (Relax/Event)
        try:
            if action == "relax":
                if not isinstance(target, str) or not target:
                    await self._push_update("请选择一个有效的休闲动作。")
                    return
                await self._handle_relax(target)
            elif action == "exam":
                await self._handle_final_exam()
            elif action == "event_choice":
                await self._handle_event_choice(action_data)
            elif action == "next_semester":
                await self._next_semester()

            await self.check_and_trigger_gameover()
        except Exception as e:
            logger.error(f"Action Error {action}: {e}")

    async def _handle_dingtalk_reply(self, data: dict[str, Any]):
        contact_id = str(data.get("contact_id") or "").strip()
        option_id = str(data.get("option_id") or "").strip()
        if not contact_id or not option_id:
            await self.emit(
                "toast",
                {"message": "无效的钉钉回复", "level": "warning"},
            )
            return

        async with self._dingtalk_state_lock:
            state = await self.repo.get_dingtalk_state()
            contact = state.contacts.get(contact_id)
            if not contact or not contact.is_replyable:
                await self.emit(
                    "toast",
                    {"message": "该联系人暂不支持回复", "level": "warning"},
                )
                return
            if contact.round.status != "open":
                await self.emit(
                    "toast",
                    {"message": "当前没有可回复的钉钉消息", "level": "warning"},
                )
                return

            option = next(
                (opt for opt in contact.pending_options if opt.option_id == option_id),
                None,
            )
            if option is None:
                await self.emit(
                    "toast",
                    {"message": "回复选项已过期", "level": "warning"},
                )
                return

            round_id = contact.round.round_id or f"dtr_{new_message_id()[4:]}"
            contact.round.round_id = round_id
            contact.round.status = "open"
            contact.round.player_reply_count += 1
            contact.pending_options = []
            player_message = self._make_dingtalk_message(
                "player", option.text, round_id=round_id
            )
            contact.messages.append(player_message)
            contact.last_message_at = player_message.created_at
            contact.trim_messages()
            state.contacts[contact_id] = contact
            await self.repo.set_dingtalk_state(state)

        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        reply_count = contact.round.player_reply_count
        result = await self._generate_dingtalk_reply_result(
            contact, option.text, reply_count, stats
        )

        async with self._dingtalk_state_lock:
            state = await self.repo.get_dingtalk_state()
            contact = state.contacts.get(contact_id)
            if contact is None:
                return
            npc_content = str(result.get("content") or "").strip()
            if npc_content:
                npc_message = self._make_dingtalk_message(
                    "npc", npc_content, round_id=contact.round.round_id
                )
                contact.messages.append(npc_message)
                contact.unread_count += 1
                contact.last_message_at = npc_message.created_at
            if reply_count >= 3:
                contact.pending_options = []
                contact.round.status = "closed"
            else:
                contact.pending_options = self._coerce_dingtalk_options(
                    result.get("reply_options"), contact.role
                )
            contact.trim_messages()
            state.contacts[contact_id] = contact
            await self.repo.set_dingtalk_state(state)

        await self._emit_dingtalk_contact_update(contact)
        if reply_count >= 3:
            await self._apply_dingtalk_settlement(contact, result.get("settlement"))

    async def _handle_final_exam(self):
        """期末考试结算逻辑"""
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        if int(stats.get("exam_completed", 0) or 0):
            await self._push_update("本学期已经结算过期末考试，请开启新学期。")
            return
        self.stop()
        await self.repo.update_stats({"exam_completed": 1})
        stats["exam_completed"] = 1
        course_mastery = snapshot.courses
        logger.info(
            f"[{self.user_id}] EXAM: course_mastery from Redis = {course_mastery}"
        )

        try:
            raw_json = stats.get("course_info_json", "[]")
            course_info = json.loads(raw_json)
            logger.info(f"[{self.user_id}] EXAM: parsed {len(course_info)} courses")
        except Exception as parse_err:
            logger.error(
                f"[{self.user_id}] EXAM: Failed to parse course_info_json: {parse_err}"
            )
            course_info = []

        total_credits, total_gp, failed_count = 0, 0, 0
        courses_result = []  # 前端 TranscriptModal 需要的 courses 数组

        sanity = int(stats.get("sanity", 50))
        luck = int(stats.get("luck", 50))

        for course in course_info:
            c_id = str(course.get("id"))
            mastery = float(course_mastery.get(c_id, 0))
            credits = float(course.get("credits", 1))
            # 考试表现计算公式：擅长度占大头，心态和运气波动
            sanity = int(stats.get("sanity", 50))
            stress = int(stats.get("stress", 40))
            exam_bonus = self._sanity_stress_exam_factor(sanity, stress)
            luck_bonus = random.uniform(-2, 5) + (luck - 50) / 20
            final_score = max(0, min(100, mastery * 0.9 + exam_bonus + luck_bonus + 10))

            # 5分制绩点计算：绩点 = 分数 / 10 - 5，最低0分
            gp = max(0.0, round(final_score / 10 - 5, 2))
            fail_threshold = balance.fail_threshold
            if final_score < fail_threshold:
                failed_count += 1

            total_credits += credits
            total_gp += gp * credits
            # 按前端 TranscriptModal.vue 期望的字段名
            courses_result.append(
                {
                    "name": course.get("name", "未知课程"),
                    "credit": credits,
                    "progress": round(mastery, 1),
                    "grade": round(final_score, 1),
                    "gpa": round(gp, 2),
                }
            )

        term_gpa = round(total_gp / total_credits, 2) if total_credits > 0 else 0.0
        # 尝试读取累计 GPA，如果没有就用当期 GPA
        cgpa = float(stats.get("highest_gpa", 0) or 0)
        if term_gpa > cgpa:
            cgpa = term_gpa

        # 结果反馈（从配置读取惩罚/奖励）
        msg = f"期末考试结束！GPA: {term_gpa}"
        if failed_count > 0:
            penalty = balance.fail_sanity_penalty * failed_count
            await self.repo.update_stat_safe("sanity", penalty)
            msg += f" | 挂了 {failed_count} 门！"
        else:
            bonus = balance.pass_all_bonus
            await self.repo.update_stat_safe("sanity", bonus)

        # 将当期 GPA 和累计 GPA 写回 Redis stats（HudBar 实时读取）
        await self.repo.update_stats(
            {
                "gpa": str(term_gpa),
                "highest_gpa": str(cgpa),
            }
        )

        # 异步更新持久化数据库
        asyncio.create_task(self._update_db_highest_gpa(cgpa))

        # 发送结算弹窗 — 字段名严格匹配前端 TranscriptModal.vue
        await self.emit(
            "semester_summary",
            {
                "data": {
                    "term_gpa": term_gpa,
                    "cgpa": cgpa,
                    "gold_earned": 0,
                    "failed_count": failed_count,
                    "courses": courses_result,
                }
            },
        )

        await self._push_update(msg)

    async def _update_db_highest_gpa(self, gpa: float):
        """内部方法：持久化最高 GPA 到数据库"""
        try:
            async with AsyncSessionLocal() as db:
                stmt = (
                    update(User)
                    .where(User.id == int(self.user_id))
                    .values(highest_gpa=str(gpa))
                )
                await db.execute(stmt)
                await db.commit()
            await self.repo.update_stats({"highest_gpa": str(gpa)})
        except Exception as e:
            logger.error(f"DB Update Failed: {e}")

    async def _handle_study_action(self, action_type: str, course_id: str):
        snapshot = await self.repo.get_snapshot()
        stats = snapshot.stats.model_dump()
        iq = int(stats.get("iq", 90))
        msg = "你暂时没有采取有效的学习动作。"

        try:
            course_info = json.loads(stats.get("course_info_json", "[]"))
        except (TypeError, json.JSONDecodeError):
            course_info = []

        difficulty = 1.0
        for c in course_info:
            if str(c.get("id")) == str(course_id):
                difficulty = float(c.get("difficulty", 1.0))
                break

        mastery_delta = 0
        if action_type == "study":
            # 提升了学习收益率
            efficiency = 4.0 + (iq - 100) * 0.1
            mastery_delta = max(1.0, efficiency / (1 + difficulty))
            await self.repo.update_stat_safe("energy", -5)
            await self.repo.update_stat_safe("stress", 2)
            await self.repo.update_stat_safe("sanity", -1)
            msg = f"你埋头苦读，感觉知识暴涨！(擅长度 +{mastery_delta:.1f}%)"
        elif action_type == "fish":
            mastery_delta = 0.2
            await self.repo.update_stat_safe("energy", -1)
            await self.repo.update_stat_safe("stress", -1)
            await self.repo.update_stat_safe("sanity", 1)
            msg = "你在课上摸鱼，虽然学得慢，但心情不错。"
        elif action_type == "skip":
            await self.repo.update_stat_safe("energy", 2)
            await self.repo.update_stat_safe("stress", -3)
            await self.repo.update_stat_safe("sanity", 2)
            msg = "逃课一时爽，一直逃课一直爽！"

        if mastery_delta > 0:
            await self.repo.update_course_mastery(course_id, mastery_delta)

        await self._push_update(msg)

    async def _handle_relax(self, target: str):
        # 检查冷却时间
        remaining_cd = await self._check_cooldown(target)
        if remaining_cd > 0:
            msg = f"该操作还在冷却中，请等待 {remaining_cd} 秒后再试。"
            await self._push_update(msg)
            return

        # 从配置读取摸鱼动作参数
        action_cfg = balance.get_relax_action(target)
        if not action_cfg:
            msg = f"未知的休闲动作: {target}"
            await self._push_update(msg)
            return

        msg = ""
        if target == "gym":
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()
            current_energy = int(stats.get("energy", 0))
            min_energy = action_cfg.get("min_energy_required", 30)

            if current_energy < min_energy:
                msg = "你太累了，现在去健身只会晕过去..."
            else:
                # 从配置读取数值
                energy_cost = action_cfg.get("energy_cost", -30)
                energy_gain = action_cfg.get("energy_gain", 40)
                sanity_gain = action_cfg.get("sanity_gain", 5)
                stress_change = action_cfg.get("stress_change", -5)

                net_energy = energy_cost + energy_gain
                await self.repo.update_stat_safe("energy", net_energy)
                await self.repo.update_stat_safe("sanity", sanity_gain)
                await self.repo.update_stat_safe("stress", stress_change)
                await self.repo.set_cooldown(target, time.time())
                msg = "在风雨操场挥汗如雨，感觉整个人都升华了！"
        elif target == "game":
            energy_cost = action_cfg.get("energy_cost", -5)
            sanity_gain = action_cfg.get("sanity_gain", 20)

            await self.repo.update_stat_safe("energy", energy_cost)
            await self.repo.update_stat_safe("sanity", sanity_gain)
            await self.repo.set_cooldown(target, time.time())
            msg = "宿舍开黑连胜，这就是电子竞技的魅力吗？"
        elif target == "walk":
            stress_change = action_cfg.get("stress_change", -10)

            await self.repo.update_stat_safe("stress", stress_change)
            await self.repo.set_cooldown(target, time.time())
            msg = "启真湖畔的黑天鹅还是那么高傲..."
        elif target == "cc98":
            # CC98随机效果从配置读取
            effects = action_cfg.get("effects", [])
            if not effects:
                # 兜底默认值
                effects = [
                    {"weight": 0.5, "sanity": 8, "stress": -5},
                    {"weight": 0.3, "sanity": -10, "stress": 8},
                    {"weight": 0.2, "sanity": -15, "stress": 15},
                ]

            # 根据权重随机选择效果
            total_weight = sum(e.get("weight", 0) for e in effects)
            roll = random.uniform(0, total_weight)
            cumulative = 0
            selected_effect = effects[0]  # 默认

            for effect in effects:
                cumulative += effect.get("weight", 0)
                if roll <= cumulative:
                    selected_effect = effect
                    break

            # 应用效果
            if "sanity" in selected_effect:
                await self.repo.update_stat_safe("sanity", selected_effect["sanity"])
            if "stress" in selected_effect:
                await self.repo.update_stat_safe("stress", selected_effect["stress"])

            # 生成对应效果描述
            effect_type = (
                "positive" if selected_effect.get("sanity", 0) > 0 else "negative"
            )
            roll = random.randint(1, 100)  # 用于触发词

            if effect_type == "positive":
                trigger_words = [
                    "校友糗事分享",
                    "今日开怀",
                    "难绷瞬间",
                    "幽默段子",
                    "校园梗",
                    "甜蜜爱情故事",
                ]
            else:
                trigger_words = [
                    "凡尔赛GPA",
                    "郁闷小屋",
                    "烂坑",
                    "情侣秀恩爱",
                    "渣男渣女",
                ]

            trigger = random.choice(trigger_words)
            if self.mode == GameMode.AI:
                # AI 模式：跳过帖子库，直接走 LLM（含 Redis 缓存）
                post_content = None
            else:
                # Hybrid / Library 模式：优先从预编译帖子库获取（零 token 消耗）
                post_content = pick_cc98_post(effect=effect_type, trigger=trigger)
            if not post_content and self.mode != GameMode.LIBRARY:
                # 库未命中且非纯算法模式：fallback 到 LLM
                snapshot = await self.repo.get_snapshot()
                stats = snapshot.stats.model_dump()
                post_content, feedback = await generate_cc98_post(
                    stats, effect_type, trigger, llm_override=self.llm_override
                )
                if post_content == "CC98 服务器维护中..." and self.mode == GameMode.AI:
                    self.llm_available = False
                    self.mode = GameMode.HYBRID
                    await self.emit(
                        "mode_changed",
                        {"mode": self.mode, "llm_available": False},
                    )
                    await self.emit(
                        "toast",
                        {
                            "message": "AI 内容生成暂不可用，已自动切换到混合模式",
                            "level": "warning",
                        },
                    )
                    fallback_post = pick_cc98_post(effect=effect_type, trigger=trigger)
                    if fallback_post:
                        post_content = fallback_post
            elif not post_content:
                # Library 模式库耗尽：跳过本次 cc98
                post_content, feedback = "服务器繁忙，论坛暂时打不开...", ""
            else:
                # 帖子库命中，用固定 feedback
                feedback_map = {
                    "positive": "心情不错，继续冲浪~",
                    "neutral": "就这样吧，继续划水。",
                    "negative": "看得心态有点崩...",
                }
                feedback = feedback_map.get(effect_type, "")
            await self.repo.set_cooldown(target, time.time())
            msg = f"你在CC98刷到了：\n{post_content}\n{feedback}"

        await self._push_update(msg)
        if msg:
            title_map = {
                "gym": "健身结果",
                "game": "游戏结果",
                "walk": "散步结果",
                "cc98": "CC98 新帖",
            }
            await self._emit_feedback(
                title_map.get(target, "休闲结果"),
                msg,
                kind="relax",
                auto_close_ms=3000,
            )

    # app/game/engine.py

    async def _trigger_random_event(self):
        """触发随机事件（优先事件库，LLM 兜底）"""
        if not self.is_running:
            return
        if self._random_event_inflight:
            return

        self._random_event_inflight = True
        try:
            history = await self.repo.get_event_history()
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()
            event_data = None

            if self.mode == GameMode.AI:
                # AI 模式：跳过事件库，直接走 LLM（含 Redis 缓存）
                if self.llm_available:
                    event_data = await generate_random_event(
                        stats, history, llm_override=self.llm_override
                    )
                if not event_data:
                    self.llm_available = False
                    self.mode = GameMode.HYBRID
                    await self.emit(
                        "mode_changed",
                        {"mode": self.mode, "llm_available": False},
                    )
                    await self.emit(
                        "toast",
                        {
                            "message": "AI 内容生成暂不可用，已自动切换到混合模式",
                            "level": "warning",
                        },
                    )
                    event_data = pick_random_event(
                        sanity=int(stats.get("sanity", 50)),
                        stress=int(stats.get("stress", 0)),
                        seen_ids=set(history) if history else None,
                    )
            else:
                # Hybrid / Library 模式：优先从预编译事件库检索（零 token 消耗）
                event_data = pick_random_event(
                    sanity=int(stats.get("sanity", 50)),
                    stress=int(stats.get("stress", 0)),
                    seen_ids=set(history) if history else None,
                )
                # Hybrid 模式下库耗尽时 fallback 到 LLM；Library 模式直接跳过
                if (
                    not event_data
                    and self.mode == GameMode.HYBRID
                    and self.llm_available
                ):
                    event_data = await generate_random_event(
                        stats, history, llm_override=self.llm_override
                    )

            if event_data:
                # 统一按 event_id 去重：库事件直接使用 id；LLM 兜底生成稳定 id
                event_id = event_data.get("id")
                if not event_id:
                    seed = f"{event_data.get('title', '')}|{event_data.get('desc', '')}"
                    event_id = (
                        f"llm_evt_{hashlib.md5(seed.encode('utf-8')).hexdigest()[:10]}"
                    )
                    event_data["id"] = event_id

                await self.repo.add_event_to_history(event_id)
                await self.repo.set_current_event(event_data)
                await self.emit("random_event", {"data": event_data})
        except Exception as e:
            logger.error(f"Random event error: {e}", exc_info=True)
        finally:
            self._random_event_inflight = False

    # 事件效果允许修改的属性白名单及每次最大变化量
    _ALLOWED_EFFECT_FIELDS = {
        "energy": 50,
        "sanity": 30,
        "stress": 30,
        "eq": 20,
        "luck": 20,
        "reputation": 20,
    }

    async def _handle_event_choice(self, data):
        """处理随机事件的选择结果（只接受当前服务端事件的选项 id）。"""
        option_id = str(data.get("option_id", "")).strip()
        current_event = await self.repo.pop_current_event()
        if not current_event:
            msg = "事件已经过期。"
            await self._push_update(msg)
            await self._emit_feedback("事件结果", msg, kind="event", auto_close_ms=5000)
            return

        selected_option = None
        for option in current_event.get("options", []) or []:
            candidate_id = str(option.get("id", "")).strip()
            legacy_candidate_id = str(option.get(" id", "")).strip()
            if option_id and option_id in {candidate_id, legacy_candidate_id}:
                selected_option = option
                break
        if selected_option is None:
            msg = "无效的事件选项。"
            await self._push_update(msg)
            await self._emit_feedback("事件结果", msg, kind="event", auto_close_ms=5000)
            return

        effects = selected_option.get("effects", {})
        if not isinstance(effects, dict):
            effects = {}
        desc = effects.get("desc", "")
        for key, val in effects.items():
            if key == "desc":
                continue
            # 白名单校验：只允许修改预定义字段
            max_delta = self._ALLOWED_EFFECT_FIELDS.get(key)
            if max_delta is None:
                logger.warning(
                    "Blocked illegal effect field '%s' from user %s", key, self.user_id
                )
                continue
            try:
                delta = int(val)
                # 限制单次变化幅度
                delta = max(-max_delta, min(max_delta, delta))
                await self.repo.update_stat_safe(key, delta)
            except (ValueError, TypeError):
                continue
        result_msg = f"事件：{desc}"
        await self._push_update(result_msg)
        await self._emit_feedback(
            "事件结果",
            str(desc or "你的选择已经生效。"),
            kind="event",
            auto_close_ms=5000,
        )

    async def _trigger_dingtalk_message(self):
        """触发钉钉消息推送（优先使用 M2-her RP 模型）"""
        if not self.is_running:
            return
        if self._dingtalk_inflight:
            return

        # 纯算法模式：跳过钉钉消息（暂未建设 dingtalk_library）
        if self.mode == GameMode.LIBRARY or not self.llm_available:
            return

        self._dingtalk_inflight = True
        try:
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()

            # 简单的上下文判断逻辑
            context = "random"
            sanity = int(stats.get("sanity", 50))
            stress = int(stats.get("stress", 0))
            gpa = float(stats.get("gpa", 0))

            if sanity < 30:
                context = "low_sanity"
            elif stress > 80:
                context = "high_stress"
            elif gpa > 0 and gpa < 2.0:
                context = "low_gpa"

            # 优先使用 M2-her RP 模型（若用户配置了自定义模型，则跳过直接走 fallback）
            msg_data = None
            if not self.llm_override:
                try:
                    from app.core.dingtalk_llm import generate_dingtalk_via_m2her

                    msg_data = await generate_dingtalk_via_m2her(stats, context)
                except Exception as e:
                    logger.warning(f"M2-her dingtalk fallback: {e}")

            # Fallback 到旧接口
            if not msg_data:
                msg_data = await generate_dingtalk_message(
                    stats, context, llm_override=self.llm_override
                )

            if msg_data:
                contact = await self._store_dingtalk_npc_message(msg_data)
                if contact:
                    await self._emit_dingtalk_contact_update(contact)
            elif self.mode == GameMode.AI:
                self.llm_available = False
                self.mode = GameMode.HYBRID
                await self.emit(
                    "mode_changed",
                    {"mode": self.mode, "llm_available": False},
                )
                await self.emit(
                    "toast",
                    {
                        "message": "AI 内容生成暂不可用，已自动切换到混合模式",
                        "level": "warning",
                    },
                )

        except Exception as e:
            logger.error(f"DingTalk trigger error: {e}", exc_info=True)
        finally:
            self._dingtalk_inflight = False

    async def _check_achievements(self):
        """成就系统判定逻辑"""
        try:
            snapshot = await self.repo.get_snapshot()
            stats = snapshot.stats.model_dump()
            action_counts = await self.repo.get_action_counts()

            # 防御性转换
            gpa = float(stats.get("highest_gpa") or 0)
            sanity = int(stats.get("sanity") or 50)
            eq = int(stats.get("eq") or 50)
            study_count = int(action_counts.get("study") or 0)

            if not self.achievement_path.exists():
                return
            with open(self.achievement_path, "r", encoding="utf-8") as f:
                ach_config = json.load(f)

            unlocked = await self.repo.get_unlocked_achievements()

            for code, item in ach_config.items():
                if code in unlocked:
                    continue

                passed = False
                if code == "gpa_king" and gpa >= 4.0:
                    passed = True
                elif code == "broken_heart" and sanity < 10:
                    passed = True
                elif code == "social_butterfly" and eq >= 95:
                    passed = True
                elif code == "library_ghost" and study_count > 50:
                    passed = True

                if passed:
                    await self.repo.unlock_achievement(code)
                    await self.emit(
                        "achievement_unlocked",
                        {"data": item},
                    )
        except Exception as e:
            logger.error(f"Achievement check error: {e}")

    async def _next_semester(self):
        """进入下一学期逻辑"""
        was_running = self.is_running
        self.stop()  # 先暂停游戏循环，防止过渡期间 tick 继续消耗精力

        async with self.db_factory() as db:
            transition = await self.game_service.process_semester_transition(
                db,
                holiday_event_factory=generate_random_event,
                save_slot=self.save_slot,
            )

        current_semester_idx = transition.get("semester_idx")

        if transition.get("status") == "graduated":
            stats = transition.get("stats") or {}
            # 调用AI生成文言文结业总结
            from app.core.llm import generate_wenyan_report

            if self.mode == GameMode.LIBRARY:
                wenyan_report = "学业既成，前程似锦。"
            else:
                wenyan_report = await generate_wenyan_report(
                    stats, llm_override=self.llm_override
                )
            await self.emit(
                "graduation",
                {
                    "data": {
                        "msg": "恭喜你从折姜大学毕业！",
                        "final_stats": stats,
                        "wenyan_report": wenyan_report,
                    }
                },
            )
            # self.stop() 已在函数开头调用，毕业后无需重启
            return

        # 获取新学期的最新快照（含新课程数据）
        new_snapshot = await self.repo.get_snapshot()
        new_stats = new_snapshot.stats.model_dump()

        await self.emit(
            "new_semester",
            {
                "data": {
                    "semester_name": f"第 {current_semester_idx} 学期",
                    "holiday_event": transition.get("holiday_event"),
                    "course_info_json": new_stats.get("course_info_json", "[]"),
                }
            },
        )
        await self._push_update("新学期开始了，加油！")
        if was_running:
            self.start()

    async def _probe_llm(self):
        """后台探测 LLM API 是否可用"""
        try:
            from app.core.llm import check_llm_availability

            available = await check_llm_availability(self.llm_override)
            self.llm_available = available
            if not available and self.mode == GameMode.AI:
                self.mode = GameMode.HYBRID
                await self.emit(
                    "mode_changed",
                    {"mode": self.mode, "llm_available": False},
                )
                await self.emit(
                    "toast",
                    {
                        "message": "LLM API 连接失败，已自动切换到混合模式",
                        "level": "warning",
                    },
                )
        except Exception as e:
            logger.warning(f"LLM probe failed: {e}")

    async def _push_update(self, msg: str | None = None):
        """统一数据推送接口"""
        try:
            snapshot = await self.repo.get_snapshot()
            new_stats = snapshot.stats.model_dump()
            course_mastery = snapshot.courses
            course_states = snapshot.course_states
            relax_cooldowns = await self._get_relax_cooldowns()

            # 计算学期剩余时间
            semester_idx = int(new_stats.get("semester_idx", 1))
            base_duration = balance.get_semester_duration(semester_idx)
            # ✨ 传入我们在 Redis 中累加的虚拟流逝时间
            elapsed = int(new_stats.get("elapsed_game_time", 0))
            semester_time_left = self._get_semester_time_left(elapsed, base_duration)

            # 新增：真正下发综合效率（用于前端渲染）
            # 基于 iq 和 stress 计算并存入将下发的 new_stats 中
            iq = int(new_stats.get("iq", 100))
            stress = int(new_stats.get("stress", 0))
            # 基准 100，每高出一点智商提高 1%，每多一点压力降低 0.5%
            calculated_efficiency = max(10, 100 + (iq - 100) * 1 - int(stress * 0.5))
            new_stats["efficiency"] = calculated_efficiency

            await self.emit(
                "tick",
                {
                    "stats": new_stats,
                    "courses": course_mastery,
                    "course_states": course_states,
                    "semester_time_left": semester_time_left,
                    "relax_cooldowns": relax_cooldowns,
                },
                msg,
            )
        except Exception as e:
            logger.error(f"Push failed: {e}")

    def stop(self):
        """安全停止游戏循环"""
        self.is_running = False
        current_task = asyncio.current_task()
        if (
            self._run_task
            and not self._run_task.done()
            and self._run_task is not current_task
        ):
            self._run_task.cancel()
        self._run_task = None

    def shutdown(self):
        """停止游戏循环并取消挂起的后台生成任务。"""
        self.stop()
        for task in list(self._background_tasks):
            task.cancel()
        self._background_tasks.clear()

    def _get_semester_time_left(
        self, elapsed_game_time: int, duration_seconds: int
    ) -> int:
        try:
            # 尝试将传入的值强制转换为整型，防范 Redis 中的脏数据或 None
            elapsed = int(elapsed_game_time)
            duration = int(duration_seconds)
            return max(0, duration - elapsed)
        except (TypeError, ValueError):
            # 如果解析失败，兜底返回初始的 duration_seconds
            # 若 duration_seconds 本身也有问题，则返回一个安全的硬编码值（如 360）
            if isinstance(duration_seconds, (int, float)):
                return int(duration_seconds)
            return 360

    def _build_initial_stats(self, username: str) -> dict:
        from app.schemas.game_state import PlayerStats

        return PlayerStats.build_initial(username=username).model_dump()

    async def _check_cooldown(self, action_type: str) -> int:
        last_use = await self.repo.get_cooldown_timestamp(action_type)
        if not last_use:
            return 0

        elapsed = time.time() - float(last_use)
        cd_time = balance.get_cooldown(action_type)
        remaining = max(0, cd_time - elapsed)
        return math.ceil(remaining)

    async def _get_relax_cooldowns(self) -> dict[str, int]:
        cooldowns: dict[str, int] = {}
        for action in balance.relax_actions.keys():
            cooldowns[action] = await self._check_cooldown(action)
        return cooldowns
