from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import json
import logging

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.api import deps
from app.websockets.manager import manager
from app.game.engine import GameEngine
from app.api.cache import RedisCache
from app.repositories.redis_repo import RedisRepository
from app.services.save_service import SaveService
from app.services.game_service import GameService
from app.services.restriction_service import RestrictionService
from app.core.events import GameEvent

# 配置日志
logger = logging.getLogger(__name__)

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
@router.websocket("/ws/game")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(deps.get_db),
    game_service: GameService = Depends(deps.get_game_service),
    save_service: SaveService = Depends(deps.get_save_service),
    user_info: dict = Depends(deps.get_current_user_info),
):
    # --- 鉴权 ---
    logger.debug(f"WebSocket connection attempt with token: {token[:20]}...")
    user_id = user_info.get("user_id")
    username = user_info.get("username")
    tier = user_info.get("tier")

    if not user_id:
        logger.warning("Invalid token, closing WebSocket connection")
        await websocket.close(code=1008)
        return

    restriction = await RestrictionService.get_active_restriction(db, int(user_id))
    if restriction:
        logger.warning("Restricted user %s attempted connect", user_id)
        await websocket.close(code=1008)
        return

    # --- 连接管理 ---
    await manager.connect(websocket, user_id)
    redis_client = RedisCache.get_client()
    repo = RedisRepository(user_id, redis_client)
    state = RedisState(user_id)

    engine = None
    loop_task = None
    heartbeat_task = None
    forwarder_task = None

    # 心跳检测任务
    async def heartbeat_checker():
        """定期检查僵尸连接"""
        while True:
            await asyncio.sleep(30)  # 每30秒检查一次
            await manager.check_dead_connections()

    try:
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

        # --- 启动心跳检测任务 ---
        heartbeat_task = asyncio.create_task(heartbeat_checker())

        # --- 消息接收循环 ---
        while True:
            data_text = await websocket.receive_text()
            try:
                data_json = json.loads(data_text)
                action = data_json.get("action")

                # 处理心跳消息
                if action == "ping":
                    manager.update_heartbeat(user_id)
                    await repo.touch_ttl()
                    await manager.send_personal_message({"type": "pong"}, user_id)

                # 处理保存并退出
                elif action == "save_and_exit":
                    logger.info(f"User {username} requested save_and_exit")
                    success = await save_service.persist_to_db(repo, db)
                    await manager.send_personal_message(
                        {
                            "type": "save_result",
                            "success": success,
                            "message": "存档保存成功" if success else "存档保存失败",
                        },
                        user_id,
                    )
                    # 无论是否保存成功，都清理 Redis 并断开连接
                    await cleanup_redis_data(repo)
                    break

                # 处理仅保存（不退出）
                elif action == "save_game":
                    logger.info(f"User {username} requested save_game")
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
                    logger.info(f"User {username} exiting without save")
                    await cleanup_redis_data(repo)
                    await manager.send_personal_message(
                        {"type": "exit_confirmed"}, user_id
                    )
                    break

                else:
                    await engine.process_action(data_json)

            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received from {username}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {username}")
    except Exception as e:
        logger.error(f"WebSocket error for {username}: {e}", exc_info=True)
    finally:
        # --- 资源清理 ---
        if engine:
            engine.stop()
        if loop_task:
            loop_task.cancel()
        if heartbeat_task:
            heartbeat_task.cancel()
        if forwarder_task:
            forwarder_task.cancel()
        manager.disconnect(user_id)
        await state.close()
