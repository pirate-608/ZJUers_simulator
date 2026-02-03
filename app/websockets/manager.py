from fastapi import WebSocket
from typing import Dict, List
import json
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        # 存放活跃连接: user_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}
        # 心跳时间戳记录: user_id -> last_heartbeat_time
        self.heartbeat_timestamps: Dict[str, float] = {}
        # 心跳超时时间（秒）
        self.heartbeat_timeout = 60

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.heartbeat_timestamps[user_id] = time.time()  # 记录连接时间
        logger.info(f"User {user_id} connected. Total: {len(self.active_connections)}")
        logger.debug(f"Active connections: {list(self.active_connections.keys())}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            if user_id in self.heartbeat_timestamps:
                del self.heartbeat_timestamps[user_id]
            logger.info(f"User {user_id} disconnected. Remaining: {len(self.active_connections)}")
            logger.debug(f"Active connections: {list(self.active_connections.keys())}")

    def update_heartbeat(self, user_id: str):
        """更新心跳时间戳"""
        self.heartbeat_timestamps[user_id] = time.time()
        logger.debug(f"Heartbeat updated for user {user_id}")

    async def check_dead_connections(self):
        """检查并清理超时的僵尸连接"""
        now = time.time()
        dead_users = []
        
        for user_id, last_time in self.heartbeat_timestamps.items():
            if now - last_time > self.heartbeat_timeout:
                dead_users.append(user_id)
        
        for user_id in dead_users:
            logger.warning(f"Cleaning up dead connection for user {user_id} (timeout)")
            self.disconnect(user_id)
            # 尝试关闭 WebSocket
            if user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].close(code=1001)
                except Exception as e:
                    logger.error(f"Error closing connection for {user_id}: {e}")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            logger.debug(f"Sending message to {user_id}, type: {message.get('type')}")
            try:
                await websocket.send_text(json.dumps(message))
                # 发送成功，更新心跳
                self.update_heartbeat(user_id)
            except Exception as e:
                logger.error(f"Failed to send message to {user_id}: {e}")
                self.disconnect(user_id)
        else:
            logger.warning(f"Attempted to send message to disconnected user {user_id}")

    async def broadcast(self, message: dict):
        """广播给所有人（比如全服公告）"""
        json_msg = json.dumps(message)
        for connection in self.active_connections.values():
            await connection.send_text(json_msg)

manager = ConnectionManager()