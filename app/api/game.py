from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import json
import logging
import time

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.api import deps
from app.websockets.manager import manager
from app.game.engine import GameEngine
from app.game.balance import balance  # 修复: 原缺失导致 get_game_config NameError
from app.api.cache import RedisCache
from app.repositories.redis_repo import RedisRepository
from app.services.save_service import SaveService
from app.services.game_service import GameService
from app.services.restriction_service import RestrictionService
from app.core.events import GameEvent
from app.models.user import User

# 配置日志
logger = logging.getLogger(__name__)

# WebSocket 消息限流：最小间隔（秒）
_WS_MIN_MSG_INTERVAL = 0.05

# 1. 必须先实例化 router
router = APIRouter()


# 2. 存档管理辅助函数
async def cleanup_redis_data(repo: RedisRepository):
    """清理用户的 Redis 数据"""
    try:
        await repo.delete_all()
        logger.info("Redis data cleaned for user %s", repo.user_id)
    except Exception as e:
        logger.error("Failed to cleanup Redis for user %s: %s", repo.user_id, e)


# 3. 辅助函数
async def get_current_user_id(token: str):
    """从 Token 解析 User ID"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        tier: str = payload.get("tier")
        username: str = payload.get("username")
        if user_id is None:
            return None, None, None
        return user_id, username, tier
    except JWTError:
        return None, None, None


def _parse_token(token: str) -> dict:
    """解析 JWT token，返回用户信息字典，失败返回空字典"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        if not user_id:
            return {}
        return {
            "user_id": user_id,
            "username": payload.get("username"),
            "tier": payload.get("tier"),
        }
    except JWTError:
        return {}


# 2.5 游戏配置API
@router.get("/config")
async def get_game_config():
    """获取游戏配置（供前端使用）"""
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


# 3. WebSocket 路由主入口
#    Token 通过首条消息传递（不再放在 URL Query String 中）
#    DB Session 按需创建（不再在整个连接期间持有）
@router.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket):
    # ========================================
    # 阶段 1：接受连接，等待首条消息进行鉴权
    # ========================================
    await websocket.accept()

    # 等待客户端发送 auth 消息（10 秒超时）
    try:
        auth_text = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        auth_data = json.loads(auth_text)
        token = auth_data.get("token", "")
    except (asyncio.TimeoutError, json.JSONDecodeError, Exception):
        await websocket.close(code=1008, reason="auth_timeout")
        return

    user_info = _parse_token(token)
    user_id = user_info.get("user_id")
    username = user_info.get("username")
    tier = user_info.get("tier")

    if not user_id:
        logger.warning("Invalid token in first WS message")
        await websocket.send_text(
            json.dumps({"type": "auth_error", "message": "无效凭证"})
        )
        await websocket.close(code=1008, reason="invalid_token")
        return

        # 鉴权通过后检查是否被限制（短生命周期 DB Session）
        llm_override = None
        custom_model = (auth_data.get("custom_llm_model") or "").strip()
        custom_key = (auth_data.get("custom_llm_api_key") or "").strip()
        if custom_model or custom_key:
            llm_override = {
                "model": custom_model or None,
                "api_key": custom_key or None,
            }

        async with AsyncSessionLocal() as db:
            restriction = await RestrictionService.get_active_restriction(
                db, int(user_id)
            )
    if restriction:
        logger.warning("Restricted user %s attempted connect", user_id)
        await websocket.send_text(
            json.dumps({"type": "auth_error", "message": "账号受限"})
        )
        await websocket.close(code=1008, reason="restricted")
        return

    # ========================================
    # 阶段 2：注册连接（会自动踢掉旧连接）
    # ========================================
    # 注意：connect 内部会 close 旧 ws，但不会再 accept（因为我们已经 accept 了）
    # 所以这里要用一个特殊方式：先注册，不重复 accept
    if user_id in manager.active_connections:
        old_ws = manager.active_connections[user_id]
        logger.warning("Kicking old connection for user %s", user_id)
        try:
            await old_ws.close(code=4001, reason="duplicate_session")
        except Exception:
            pass
        manager._remove(user_id)

    manager.active_connections[user_id] = websocket
    manager.heartbeat_timestamps[user_id] = time.time()
    logger.info(
        "User %s connected. Total: %d", user_id, len(manager.active_connections)
    )

    # 告知客户端鉴权成功
    await manager.send_personal_message({"type": "auth_ok"}, user_id)

    # ========================================
    # 阶段 3：初始化游戏上下文
    # ========================================
    redis_client = RedisCache.get_client()
    repo = RedisRepository(user_id, redis_client)
    world_service = deps.get_world_service()
    game_service = GameService(user_id, repo, world_service)
    save_service = SaveService()

    engine = None
    loop_task = None
    forwarder_task = None

    try:
        # 初始化游戏（使用短生命周期 DB Session）
        async with AsyncSessionLocal() as db:
            game_context = await game_service.prepare_game_context(username, tier, db)

        snapshot = await repo.get_snapshot()
        final_stats = snapshot.stats.model_dump()

        if game_context["status"] == "new":
            await manager.send_personal_message(
                {
                    "type": "event",
                    "data": {
                        "desc": f"欢迎来到折姜大学！你被分配到了【{final_stats.get('major', '未知专业')}】专业。"
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

        # 发送初始化数据包
        await manager.send_personal_message(
            {"type": "init", "data": final_stats}, user_id
        )

        # --- 启动游戏引擎 ---
        engine = GameEngine(
            user_id,
            repo=repo,
            save_service=save_service,
            game_service=game_service,
            db_factory=AsyncSessionLocal,
            llm_override=llm_override,
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
        loop_task = asyncio.create_task(engine.run_loop())

        # ========================================
        # 阶段 4：消息接收循环（带限流）
        # ========================================
        last_msg_time = 0.0

        while True:
            data_text = await websocket.receive_text()

            # 消息限流
            now = time.time()
            if now - last_msg_time < _WS_MIN_MSG_INTERVAL:
                continue
            last_msg_time = now

            try:
                data_json = json.loads(data_text)
                action = data_json.get("action")

                # 处理心跳消息
                if action == "ping":
                    manager.update_heartbeat(user_id)
                    await repo.touch_ttl()
                    await manager.send_personal_message({"type": "pong"}, user_id)

                # 处理保存并退出（按需获取 DB Session）
                elif action == "save_and_exit":
                    logger.info("User %s requested save_and_exit", username)
                    async with AsyncSessionLocal() as db:
                        success = await save_service.persist_to_db(repo, db)
                    await manager.send_personal_message(
                        {
                            "type": "save_result",
                            "success": success,
                            "message": "存档保存成功" if success else "存档保存失败",
                        },
                        user_id,
                    )
                    await cleanup_redis_data(repo)
                    break

                # 处理仅保存（不退出）
                elif action == "save_game":
                    logger.info("User %s requested save_game", username)
                    async with AsyncSessionLocal() as db:
                        success = await save_service.persist_to_db(repo, db)
                    await manager.send_personal_message(
                        {
                            "type": "save_result",
                            "success": success,
                            "message": "游戏已保存" if success else "保存失败，请重试",
                        },
                        user_id,
                    )

                # 处理不保存直接退出
                elif action == "exit_without_save":
                    logger.info("User %s exiting without save", username)
                    await cleanup_redis_data(repo)
                    await manager.send_personal_message(
                        {"type": "exit_confirmed"}, user_id
                    )
                    break

                else:
                    await engine.process_action(data_json)

            except json.JSONDecodeError:
                logger.warning("Invalid JSON received from %s", username)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: %s", username)
    except Exception as e:
        logger.error("WebSocket error for %s: %s", username, e, exc_info=True)
    finally:
        # --- 资源清理 ---
        if engine:
            engine.stop()
        if loop_task:
            loop_task.cancel()
        if forwarder_task:
            forwarder_task.cancel()
        manager.disconnect(user_id)
