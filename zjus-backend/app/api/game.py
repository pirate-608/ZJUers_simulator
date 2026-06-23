"""HTTP and WebSocket entry points for running game sessions.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The WebSocket route performs auth, save-slot loading, engine lifecycle
management, client action dispatch, and server event fan-out.
"""

import asyncio
import json
import logging
import time
from typing import Any, Dict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from pydantic import BaseModel

from app.api import deps
from app.api.cache import RedisCache
from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.events import GameEvent
from app.game.balance import balance
from app.game.engine import GameEngine
from app.repositories.redis_repo import RedisRepository
from app.services.game_service import GameService
from app.services.restriction_service import RestrictionService
from app.services.save_service import SaveService
from app.websockets.manager import manager

logger = logging.getLogger(__name__)

# WebSocket messages are rate-limited so rapid UI clicks do not starve ticks.
_WS_MIN_MSG_INTERVAL = 0.05
_SAVE_TIMEOUT_SECONDS = 12.0
_VALID_COURSE_STATES = {0, 1, 2}

router = APIRouter()


async def cleanup_redis_data(repo: RedisRepository):
    """Delete a player's active Redis session after logout/restart cleanup."""
    try:
        await repo.delete_all()
        logger.info("Redis data cleaned for user %s", repo.user_id)
    except Exception as e:
        logger.error("Failed to cleanup Redis for user %s: %s", repo.user_id, e)


async def persist_save_with_timeout(
    save_service: SaveService,
    repo: RedisRepository,
    save_slot: int,
) -> tuple[bool, str | None]:
    """Persist a save and return a user-facing timeout reason when needed."""
    try:
        async with AsyncSessionLocal() as db:
            success = await asyncio.wait_for(
                save_service.persist_to_db(repo, db, save_slot=save_slot),
                timeout=_SAVE_TIMEOUT_SECONDS,
            )
        return success, None
    except TimeoutError:
        logger.error(
            "Persistence timed out for user %s slot %s",
            repo.user_id,
            save_slot,
        )
        return False, "保存超时，请检查网络后重试"


async def get_current_user_id(token: str) -> tuple[str | None, str | None]:
    """Decode a JWT and return its user ID and username claims."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id_raw = payload.get("sub")
        username_raw = payload.get("username")
        if not user_id_raw:
            return None, None
        return str(user_id_raw), str(username_raw) if username_raw else None
    except JWTError:
        return None, None


def _parse_token(token: str) -> dict[str, str]:
    """Decode a JWT into a small user-info dict, returning `{}` on failure."""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id_raw = payload.get("sub")
        if not user_id_raw:
            return {}
        user_id = str(user_id_raw)
        username_raw = payload.get("username")
        return {
            "user_id": user_id,
            "username": str(username_raw) if username_raw else user_id,
        }
    except JWTError:
        return {}


def _safe_int(value, default=None):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_initialized_stats(stats: dict) -> bool:
    return bool(stats.get("major_abbr") and stats.get("course_info_json"))


def _string_field(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    return value if isinstance(value, str) else ""


class SemesterConfigResponse(BaseModel):
    """Runtime semester and speed configuration exposed to the frontend."""

    durations: Dict[str, int]
    default_duration: int
    speed_modes: Dict[str, float]


class GameConfigResponse(BaseModel):
    """Public game-balance subset used by the frontend UI."""

    version: str
    semester: SemesterConfigResponse
    course_states: Dict[str, Dict[str, str]]
    cooldowns: Dict[str, int]
    tick_interval: float
    base_drain: int


@router.get("/config", response_model=GameConfigResponse)
async def get_game_config():
    """Return the frontend-visible game balance configuration."""
    return {
        "version": balance.version,
        "semester": {
            "durations": balance.semester_config.get("duration_by_index", {}),
            "default_duration": balance.semester_config.get(
                "default_duration_seconds", 360
            ),
            "speed_modes": balance.speed_modes,
        },
        "course_states": balance.course_states,
        "cooldowns": {
            action: cfg.get("cooldown_seconds", 0)
            for action, cfg in balance.relax_actions.items()
        },
        "tick_interval": balance.tick_interval,
        "base_drain": balance.base_energy_drain,
    }


@router.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket):
    """Run one authenticated game WebSocket session."""
    await websocket.accept()

    # Authentication is a first-message handshake so tokens stay out of URLs.
    try:
        auth_text = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        auth_payload = json.loads(auth_text)
        if not isinstance(auth_payload, dict):
            raise ValueError("auth payload must be an object")
        auth_data: dict[str, Any] = auth_payload
        token_value = auth_data.get("token", "")
        token = token_value if isinstance(token_value, str) else ""
        load_save_slot = auth_data.get("load_save_slot")
    except (asyncio.TimeoutError, json.JSONDecodeError, ValueError):
        await websocket.close(code=1008, reason="auth_timeout")
        return

    user_info = _parse_token(token)
    user_id = user_info.get("user_id")

    if not user_id:
        logger.warning("Invalid token in first WS message")
        await websocket.send_text(
            json.dumps({"type": "auth_error", "message": "无效凭证"})
        )
        await websocket.close(code=1008, reason="invalid_token")
        return
    username = user_info.get("username") or user_id

    # Check restrictions with a short-lived DB session after JWT auth.
    llm_override = None
    rp_llm_override = None
    custom_model = _string_field(auth_data, "custom_llm_model").strip()
    custom_key = _string_field(auth_data, "custom_llm_api_key").strip()
    custom_provider = _string_field(auth_data, "custom_llm_provider").strip()
    custom_rp_key = _string_field(auth_data, "custom_rp_api_key").strip()
    custom_rp_model = _string_field(auth_data, "custom_rp_model").strip()
    custom_rp_base_url = _string_field(auth_data, "custom_rp_base_url").strip()

    if custom_model or custom_key:
        llm_override = {
            "model": custom_model or None,
            "api_key": custom_key or None,
            "provider": custom_provider or None,
        }
    if custom_rp_key:
        rp_llm_override = {
            "provider": "minimax",
            "model": custom_rp_model or "M2-her",
            "api_key": custom_rp_key,
            "base_url": custom_rp_base_url or settings.MINIMAX_BASE_URL,
        }

    async with AsyncSessionLocal() as db:
        restriction = await RestrictionService.get_active_restriction(db, int(user_id))

    if restriction:
        logger.warning("Restricted user %s attempted connect", user_id)
        await websocket.send_text(
            json.dumps({"type": "auth_error", "message": "账号受限"})
        )
        await websocket.close(code=1008, reason="restricted")
        return

    # Register the accepted socket and replace any older session for this user.
    await manager.register_accepted(user_id, websocket)

    await manager.send_personal_message({"type": "auth_ok"}, user_id)

    # Initialize or restore game context after auth succeeds.
    redis_client = RedisCache.get_client()
    repo = RedisRepository(user_id, redis_client)
    world_service = deps.get_world_service()
    game_service = GameService(user_id, repo, world_service)
    save_service = SaveService()

    engine = None
    forwarder_task = None

    try:
        selected_save_slot = None
        if load_save_slot is not None:
            try:
                parsed_save_slot = int(load_save_slot)
                selected_save_slot = parsed_save_slot if parsed_save_slot > 0 else None
            except (TypeError, ValueError):
                selected_save_slot = None

            if selected_save_slot is None:
                await manager.send_personal_message(
                    {"type": "auth_error", "message": "无效的存档槽位"},
                    user_id,
                )
                return

        active_save_slot = selected_save_slot or 1

        async with AsyncSessionLocal() as db:
            game_context = await game_service.prepare_game_context(
                username,
                db,
                save_slot=active_save_slot,
                force_load_save=selected_save_slot is not None,
            )

        if game_context["status"] == "missing_save":
            await manager.send_personal_message(
                {"type": "auth_error", "message": "选择的存档不存在"},
                user_id,
            )
            return

        snapshot = await repo.get_snapshot()
        final_stats = snapshot.stats.model_dump()
        if not _is_initialized_stats(final_stats):
            await manager.send_personal_message(
                {
                    "type": "auth_error",
                    "message": "角色尚未初始化，请先创建角色",
                },
                user_id,
            )
            return

        if game_context["status"] == "new":
            major_name = final_stats.get("major", "未知专业")
            await manager.send_personal_message(
                {
                    "type": "event",
                    "data": {
                        "desc": f"欢迎来到折姜大学！你被分配到了【{major_name}】专业。"
                    },
                },
                user_id,
            )
        elif game_context["status"] == "repaired":
            await manager.send_personal_message(
                {
                    "type": "event",
                    "data": {
                        "desc": "系统检测到你的课表丢失，已自动为你重新安排了课程。"
                    },
                },
                user_id,
            )

        # Start the per-user engine after Redis state exists.
        engine = GameEngine(
            user_id,
            repo=repo,
            save_service=save_service,
            game_service=game_service,
            db_factory=AsyncSessionLocal,
            llm_override=llm_override,
            rp_llm_override=rp_llm_override,
            save_slot=active_save_slot,
        )
        final_stats = await engine._effective_stats(final_stats)

        # Send time-left in init so the frontend does not wait for first tick.
        semester_idx = int(final_stats.get("semester_idx", 1))
        base_duration = balance.get_semester_duration(semester_idx)
        elapsed = int(final_stats.get("elapsed_game_time", 0))
        semester_time_left = max(0, base_duration - elapsed)
        relax_cooldowns = await engine._get_relax_cooldowns()
        dingtalk_state = await repo.get_dingtalk_state()
        items_state = await engine._get_items_state_payload()

        await manager.send_personal_message(
            {
                "type": "init",
                "data": final_stats,
                "courses": snapshot.courses,
                "course_states": snapshot.course_states,
                "semester_time_left": semester_time_left,
                "relax_cooldowns": relax_cooldowns,
                "dingtalk_state": dingtalk_state.model_dump(),
                "items_state": items_state,
            },
            user_id,
        )
        await manager.send_personal_message(
            {"type": "dingtalk_state", "state": dingtalk_state.model_dump()},
            user_id,
        )
        await manager.send_personal_message(
            {"type": "items_state", "data": items_state},
            user_id,
        )

        async def event_forwarder():
            try:
                while True:
                    event = await engine.event_queue.get()
                    try:
                        if isinstance(event, GameEvent):
                            payload = event.to_payload()
                        else:
                            payload = event
                        await manager.send_personal_message(payload, user_id)
                    except Exception as send_error:
                        logger.warning(
                            "Event forward failed for user %s: %s",
                            user_id,
                            send_error,
                            exc_info=True,
                        )
                    finally:
                        engine.event_queue.task_done()
            except asyncio.CancelledError:
                pass

        forwarder_task = asyncio.create_task(event_forwarder())
        await engine._push_update()
        engine.start()

        # Receive loop with lightweight rate limiting.
        last_msg_time = 0.0

        while True:
            data_text = await websocket.receive_text()

            now = time.time()
            if now - last_msg_time < _WS_MIN_MSG_INTERVAL:
                continue
            last_msg_time = now

            try:
                data_json = json.loads(data_text)
                action = data_json.get("action")

                if action == "ping":
                    manager.update_heartbeat(user_id)
                    await repo.touch_ttl()
                    await manager.send_personal_message({"type": "pong"}, user_id)

                elif action == "save_and_exit":
                    logger.info("User %s requested save_and_exit", username)
                    success, failure_reason = await persist_save_with_timeout(
                        save_service, repo, active_save_slot
                    )
                    await manager.send_personal_message(
                        {
                            "type": "save_result",
                            "success": success,
                            "message": (
                                "存档保存成功"
                                if success
                                else failure_reason or "存档保存失败，请重试"
                            ),
                        },
                        user_id,
                    )
                    if success:
                        await manager.send_personal_message(
                            {"type": "exit_confirmed"},
                            user_id,
                        )
                        await cleanup_redis_data(repo)
                        try:
                            await websocket.close(code=1000, reason="save_and_exit")
                        except Exception as e:
                            logger.debug("save_and_exit close skipped: %s", e)
                        break

                elif action == "save_game":
                    logger.info("User %s requested save_game", username)
                    success, failure_reason = await persist_save_with_timeout(
                        save_service, repo, active_save_slot
                    )
                    await manager.send_personal_message(
                        {
                            "type": "save_result",
                            "success": success,
                            "message": (
                                "游戏已保存"
                                if success
                                else failure_reason or "保存失败，请重试"
                            ),
                        },
                        user_id,
                    )

                elif action == "exit_without_save":
                    logger.info("User %s exiting without save", username)
                    await cleanup_redis_data(repo)
                    await manager.send_personal_message(
                        {"type": "exit_confirmed"}, user_id
                    )
                    try:
                        await websocket.close(code=1000, reason="exit_without_save")
                    except Exception as e:
                        logger.debug("exit_without_save close skipped: %s", e)
                    break

                else:
                    if action == "change_course_state":
                        course_id = data_json.get("target")
                        state_val = _safe_int(data_json.get("value"))
                        current_snapshot = await repo.get_snapshot()
                        if (
                            not course_id
                            or state_val not in _VALID_COURSE_STATES
                            or str(course_id) not in current_snapshot.courses
                        ):
                            await manager.send_personal_message(
                                {
                                    "type": "toast",
                                    "message": "无效的课程策略",
                                    "level": "warning",
                                },
                                user_id,
                            )
                            continue
                    elif action == "set_speed":
                        speed = data_json.get("speed")
                        if (
                            not isinstance(speed, (int, float))
                            or isinstance(speed, bool)
                            or speed < 0.5
                            or speed > 5.0
                        ):
                            await manager.send_personal_message(
                                {
                                    "type": "toast",
                                    "message": (
                                        "无效的游戏速度，请选择 0.5 到 5.0 "
                                        "之间的倍率"
                                    ),
                                    "level": "warning",
                                },
                                user_id,
                            )
                            continue
                    elif action == "set_mode":
                        mode = data_json.get("mode")
                        if mode not in {"library", "ai", "hybrid"}:
                            await manager.send_personal_message(
                                {
                                    "type": "toast",
                                    "message": "无效的内容生成模式",
                                    "level": "warning",
                                },
                                user_id,
                            )
                            continue
                    elif action in {"item_buy", "item_sell"}:
                        item_id = data_json.get("item_id")
                        if not isinstance(item_id, str) or not item_id.strip():
                            await manager.send_personal_message(
                                {
                                    "type": "toast",
                                    "message": "无效的道具",
                                    "level": "warning",
                                },
                                user_id,
                            )
                            continue
                    elif action == "next_semester":
                        current_snapshot = await repo.get_snapshot()
                        current_stats = current_snapshot.stats.model_dump()
                        if not int(current_stats.get("exam_completed", 0) or 0):
                            await manager.send_personal_message(
                                {
                                    "type": "toast",
                                    "message": "请先完成本学期期末考试",
                                    "level": "warning",
                                },
                                user_id,
                            )
                            continue
                    await engine.process_action(data_json)

            except json.JSONDecodeError:
                logger.warning("Invalid JSON received from %s", username)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", username)
    except Exception as e:
        logger.error("WebSocket error for %s: %s", username, e, exc_info=True)
    finally:
        # Cleanup is best-effort so disconnects do not cascade.
        if engine:
            engine.shutdown()
        if forwarder_task:
            forwarder_task.cancel()
        manager.disconnect(user_id, websocket)
