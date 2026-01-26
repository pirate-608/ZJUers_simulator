from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
import asyncio
import json

from app.core.config import settings
from app.websockets.manager import manager
from app.game.state import RedisState
from app.game.engine import GameEngine

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

# 3. WebSocket 路由主入口
@router.websocket("/ws/game")
async def websocket_endpoint(websocket: WebSocket, token: str):
    # --- 鉴权 ---
    user_id, username, tier = await get_current_user_id(token)
    if not user_id:
        await websocket.close(code=1008)
        return

    # --- 连接管理 ---
    await manager.connect(websocket, user_id)
    state = RedisState(user_id)
    
    # --- 状态初始化/加载 ---
    try:
        if not await state.exists():
            # 新游戏初始化
            print(f"[GAME] Initializing new game for {username} (Tier: {tier})")
            initial_stats = await state.init_game(username, tier)
            
            await manager.send_personal_message({
                "type": "init",
                "data": initial_stats
            }, user_id)
            
            await manager.send_personal_message({
                "type": "event",
                "data": {"desc": f"欢迎来到浙江大学！你被分配到了【{initial_stats['major']}】专业。"}
            }, user_id)
        else:
            # 读取旧存档
            stats = await state.get_stats()
            await manager.send_personal_message({
                "type": "init",
                "data": stats
            }, user_id)
            await manager.send_personal_message({
                "type": "tick",
                "stats": stats
            }, user_id)

        # --- 启动游戏引擎 ---
        # 1. 创建引擎实例
        engine = GameEngine(user_id, state, manager)
        
        # 2. 启动后台心跳任务 (Fire and Forget，不阻塞主线程)
        loop_task = asyncio.create_task(engine.run_loop())

        # --- 消息接收循环 ---
        while True:
            # 3. 接收前端动作指令 (阻塞等待)
            data_text = await websocket.receive_text()
            try:
                data_json = json.loads(data_text)
                # 4. 交给引擎处理动作
                await engine.process_action(data_json)
            except json.JSONDecodeError:
                print(f"[WS] Invalid JSON from {username}")

    except WebSocketDisconnect:
        print(f"[WS] Disconnected: {username}")
        # 清理工作
        if 'engine' in locals():
            engine.stop()
        if 'loop_task' in locals():
            loop_task.cancel()
        manager.disconnect(user_id)
        await state.close()
        
    except Exception as e:
        print(f"[WS] Error: {e}")
        if 'engine' in locals():
            engine.stop()
        if 'loop_task' in locals():
            loop_task.cancel()
        manager.disconnect(user_id)
        await state.close()