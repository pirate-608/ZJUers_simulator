from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert
from sqlalchemy.dialects.postgresql import insert as pg_insert
import asyncio
import json
import logging

from app.core.config import settings
from app.core.database import get_db
from app.websockets.manager import manager
from app.game.state import RedisState
from app.game.engine import GameEngine
from app.game.balance import balance
from app.models.game_save import GameSave
from app.api.cache import RedisCache

# 配置日志
logger = logging.getLogger(__name__)

# 1. 必须先实例化 router
router = APIRouter()


# 2. 存档管理辅助函数
async def save_game_to_db(user_id: str, state: RedisState) -> bool:
    """保存游戏到数据库"""
    try:
        from app.core.database import AsyncSessionLocal

        # 收集所有游戏数据
        stats, courses, course_states = await asyncio.gather(
            state.get_stats(),
            state.get_courses_mastery(),
            state.get_all_course_states(),
        )

        achievements = list(await state.get_unlocked_achievements())

        # 准备保存数据
        save_data = {
            "user_id": int(user_id),
            "save_slot": 1,  # 默认存档位1
            "stats_data": dict(stats),
            "courses_data": dict(courses) if courses else {},
            "course_states_data": dict(course_states) if course_states else {},
            "achievements_data": achievements,
            "game_version": "1.0.0",
            "semester_index": int(stats.get("semester_idx", 1)),
        }

        # 使用 upsert 保存或更新
        async with AsyncSessionLocal() as session:
            stmt = pg_insert(GameSave).values(**save_data)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_user_save_slot",
                set_={
                    "stats_data": save_data["stats_data"],
                    "courses_data": save_data["courses_data"],
                    "course_states_data": save_data["course_states_data"],
                    "achievements_data": save_data["achievements_data"],
                    "semester_index": save_data["semester_index"],
                },
            )
            await session.execute(stmt)
            await session.commit()

        logger.info(f"Game saved to database for user {user_id}")
        return True

    except Exception as e:
        logger.error(f"Failed to save game for user {user_id}: {e}", exc_info=True)
        return False


async def load_game_from_db(user_id: str, state: RedisState) -> bool:
    """从数据库加载游戏存档到 Redis"""
    try:
        from app.core.database import AsyncSessionLocal

        async with AsyncSessionLocal() as session:
            stmt = select(GameSave).where(
                GameSave.user_id == int(user_id), GameSave.save_slot == 1
            )
            result = await session.execute(stmt)
            save = result.scalars().first()

            if not save:
                logger.info(f"No save found in database for user {user_id}")
                return False

            # 加载数据到 Redis
            await state.redis.hset(state.key, mapping=save.stats_data)

            if save.courses_data:
                await state.redis.hset(state.course_key, mapping=save.courses_data)

            if save.course_states_data:
                await state.redis.hset(
                    state.course_state_key, mapping=save.course_states_data
                )

            if save.achievements_data:
                for ach_id in save.achievements_data:
                    await state.redis.sadd(state.achievement_key, ach_id)

            await RedisCache.touch_ttl(
                RedisCache.build_player_keys(user_id), state.player_ttl_seconds
            )

            logger.info(f"Game loaded from database for user {user_id}")
            return True

    except Exception as e:
        logger.error(f"Failed to load game for user {user_id}: {e}", exc_info=True)
        return False


async def cleanup_redis_data(user_id: str):
    """清理用户的 Redis 数据"""
    try:
        state = RedisState(user_id)
        await state.redis.delete(
            state.key,
            state.course_key,
            state.course_state_key,
            state.action_key,
            state.achievement_key,
            state.history_key,
            state.cooldown_key,
        )
        logger.info(f"Redis data cleaned for user {user_id}")
    except Exception as e:
        logger.error(f"Failed to cleanup Redis for user {user_id}: {e}")


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
async def websocket_endpoint(websocket: WebSocket, token: str):
    # --- 鉴权 ---
    logger.debug(f"WebSocket connection attempt with token: {token[:20]}...")
    user_id, username, tier = await get_current_user_id(token)

    if not user_id:
        logger.warning("Invalid token, closing WebSocket connection")
        await websocket.close(code=1008)
        return

    # --- 连接管理 ---
    await manager.connect(websocket, user_id)
    state = RedisState(user_id)

    engine = None
    loop_task = None
    heartbeat_task = None

    # 心跳检测任务
    async def heartbeat_checker():
        """定期检查僵尸连接"""
        while True:
            await asyncio.sleep(30)  # 每30秒检查一次
            await manager.check_dead_connections()

    try:
        # --- 状态初始化/加载 ---
        # 1. 检查 Redis 是否存在数据
        exists = await state.exists()

        # 2. 如果 Redis 没有数据，尝试从数据库加载
        if not exists:
            logger.info(f"No Redis data found for {username}, checking database...")
            loaded = await load_game_from_db(user_id, state)
            if loaded:
                exists = True  # 标记为已存在
                logger.info(f"Successfully loaded save from database for {username}")

        # 3. 如果存在，检查存档是否完整（是否包含课程数据）
        need_repair = False
        if exists:
            stats = await state.get_stats()
            course_json = stats.get("course_info_json")
            # 如果课程数据为空或为 "[]"，说明是坏档
            if not course_json or course_json == "[]":
                need_repair = True
                logger.warning(f"Corrupted save detected for {username}, repairing...")

        if not exists:
            # === 情况A：全新开局 ===
            logger.info(f"Initializing new game for {username} (Tier: {tier})")
            await state.init_game(username, tier)
            await state.assign_major(tier)  # 必做：分配课程

            # 发送欢迎语
            stats = await state.get_stats()
            await manager.send_personal_message(
                {
                    "type": "event",
                    "data": {
                        "desc": f"欢迎来到折姜大学！你被分配到了【{stats.get('major', '未知专业')}】专业。"
                    },
                },
                user_id,
            )

        elif need_repair:
            # === 情况B：坏档修复 ===
            # 确保基础字段存在（旧数据可能缺失）
            import time as _time

            repair_fields = {}
            if not stats.get("username"):
                repair_fields["username"] = username
            if not stats.get("semester"):
                repair_fields["semester"] = "大一秋冬"
            if not stats.get("semester_idx"):
                repair_fields["semester_idx"] = 1
            if not stats.get("semester_start_time"):
                repair_fields["semester_start_time"] = int(_time.time())
            if repair_fields:
                await state.redis.hset(state.key, mapping=repair_fields)
            # 保留原有属性，但重新分配专业和课程
            await state.assign_major(tier)
            stats = await state.get_stats()
            await manager.send_personal_message(
                {
                    "type": "event",
                    "data": {
                        "desc": "系统检测到你的课表丢失，已自动为你重新安排了课程。"
                    },
                },
                user_id,
            )

        else:
            # === 情况C：正常读取旧档 ===
            logger.info(f"Loading existing game for {username}")
            # 确保基础字段完整（兼容旧版本存档）
            import time as _time

            repair_fields = {}
            if not stats.get("username"):
                repair_fields["username"] = username
            if not stats.get("semester"):
                repair_fields["semester"] = "大一秋冬"
            if not stats.get("semester_idx"):
                repair_fields["semester_idx"] = 1
            if not stats.get("semester_start_time"):
                repair_fields["semester_start_time"] = int(_time.time())
            if repair_fields:
                logger.warning(
                    f"Repairing missing fields for {username}: {list(repair_fields.keys())}"
                )
                await state.redis.hset(state.key, mapping=repair_fields)

        # 再次获取最新的完整状态（确保包含了修复后的数据）
        final_stats = await state.get_stats()

        # 发送初始化数据包
        await manager.send_personal_message(
            {"type": "init", "data": final_stats}, user_id
        )

        # 立即推送一次完整的 Tick 以激活前端视图（包含courses和course_states）
        course_mastery = await state.get_courses_mastery()
        course_states = await state.get_all_course_states()

        # 计算学期剩余时间
        from app.game.balance import balance

        semester_idx = int(final_stats.get("semester_idx", 1))
        semester_config = balance.semester_config
        base_duration = semester_config.get("durations", {}).get(
            str(semester_idx), semester_config.get("default_duration", 360)
        )
        semester_time_left = await state.get_semester_time_left(base_duration)

        await manager.send_personal_message(
            {
                "type": "tick",
                "stats": final_stats,
                "courses": course_mastery,
                "course_states": course_states,
                "semester_time_left": semester_time_left,
            },
            user_id,
        )

        # --- 启动游戏引擎 ---
        engine = GameEngine(user_id, state, manager)
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
                    await RedisCache.touch_ttl(
                        RedisCache.build_player_keys(user_id), state.player_ttl_seconds
                    )
                    await manager.send_personal_message({"type": "pong"}, user_id)

                # 处理保存并退出
                elif action == "save_and_exit":
                    logger.info(f"User {username} requested save_and_exit")
                    success = await save_game_to_db(user_id, state)
                    await manager.send_personal_message(
                        {
                            "type": "save_result",
                            "success": success,
                            "message": "存档保存成功" if success else "存档保存失败",
                        },
                        user_id,
                    )
                    # 无论是否保存成功，都清理 Redis 并断开连接
                    await cleanup_redis_data(user_id)
                    break

                # 处理仅保存（不退出）
                elif action == "save_game":
                    logger.info(f"User {username} requested save_game")
                    success = await save_game_to_db(user_id, state)
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
                    await cleanup_redis_data(user_id)
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
        manager.disconnect(user_id)
        await state.close()
