from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
import asyncio
import json

from app.core.config import settings
from app.websockets.manager import manager
from app.game.state import RedisState
from app.game.engine import GameEngine
from app.game.balance import balance

# 1. 必须先实例化 router
router = APIRouter()

# 2. 辅助函数
async def get_current_user_id(token: str):
    """从 Token 解析 User ID"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
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
            "default_duration": balance.semester_config.get("default_duration_seconds", 360),
            "speed_modes": balance.speed_modes
        },
        "course_states": balance.course_states,
        "cooldowns": {
            action: cfg.get("cooldown_seconds", 0)
            for action, cfg in balance.relax_actions.items()
        },
        "tick_interval": balance.tick_interval,
        "base_drain": balance.base_energy_drain
    }

# 3. WebSocket 路由主入口
@router.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket, token: str):
    # --- 鉴权 ---
    print(f"[WS][DEBUG] websocket_endpoint called, token={token}")
    user_id, username, tier = await get_current_user_id(token)
    
    if not user_id:
        print(f"[WS][ERROR] Invalid token, closing websocket.")
        await websocket.close(code=1008)
        return

    # --- 连接管理 ---
    await manager.connect(websocket, user_id)
    state = RedisState(user_id)
    
    engine = None
    loop_task = None

    try:
        # --- 状态初始化/加载 ---
        # 1. 检查是否存在存档
        exists = await state.exists()
        
        # 2. 如果存在，检查存档是否完整（是否包含课程数据）
        need_repair = False
        if exists:
            stats = await state.get_stats()
            course_json = stats.get("course_info_json")
            # 如果课程数据为空或为 "[]"，说明是坏档
            if not course_json or course_json == "[]":
                need_repair = True
                print(f"[GAME] Detected corrupted save for {username} (Missing courses). Repairing...")

        if not exists:
            # === 情况A：全新开局 ===
            print(f"[GAME] Initializing new game for {username} (Tier: {tier})")
            await state.init_game(username, tier)
            await state.assign_major(tier) # 必做：分配课程
            
            # 发送欢迎语
            stats = await state.get_stats()
            await manager.send_personal_message({
                "type": "event",
                "data": {"desc": f"欢迎来到浙江大学！你被分配到了【{stats.get('major', '未知专业')}】专业。"}
            }, user_id)

        elif need_repair:
            # === 情况B：坏档修复 ===
            # 保留原有属性，但重新分配专业和课程
            await state.assign_major(tier)
            stats = await state.get_stats()
            await manager.send_personal_message({
                "type": "event",
                "data": {"desc": "系统检测到你的课表丢失，已自动为你重新安排了课程。"}
            }, user_id)
            
        else:
            # === 情况C：正常读取旧档 ===
            print(f"[GAME] Loading existing game for {username}")
            # stats 已经在上面获取过了

        # 再次获取最新的完整状态（确保包含了修复后的数据）
        final_stats = await state.get_stats()
        
        # 发送初始化数据包
        await manager.send_personal_message({
            "type": "init",
            "data": final_stats
        }, user_id)

        # 立即推送一次 Tick 以激活前端视图
        await manager.send_personal_message({
            "type": "tick",
            "stats": final_stats
        }, user_id)

        # --- 启动游戏引擎 ---
        engine = GameEngine(user_id, state, manager)
        loop_task = asyncio.create_task(engine.run_loop())

        # --- 消息接收循环 ---
        while True:
            data_text = await websocket.receive_text()
            try:
                data_json = json.loads(data_text)
                await engine.process_action(data_json)
            except json.JSONDecodeError:
                print(f"[WS] Invalid JSON from {username}")

    except WebSocketDisconnect:
        print(f"[WS] Disconnected: {username}")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        # --- 资源清理 ---
        if engine:
            engine.stop()
        if loop_task:
            loop_task.cancel()
        manager.disconnect(user_id)
        await state.close()