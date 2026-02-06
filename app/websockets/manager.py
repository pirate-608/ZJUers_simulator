from fastapi import WebSocket
from typing import Dict, List, Optional
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
        # 全局心跳任务引用
        self._heartbeat_task: Optional[asyncio.Task] = None

    # ==========================================
    # 全局心跳任务（单例）
    # ==========================================
    def start_heartbeat_checker(self):
        """启动全局心跳检测任务，保证只运行一个"""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("Global heartbeat checker started")

    async def _heartbeat_loop(self):
        """全局心跳检测循环，每 30 秒清理一次僵尸连接"""
        try:
            while True:
                await asyncio.sleep(30)
                await self.check_dead_connections()
        except asyncio.CancelledError:
            logger.info("Global heartbeat checker stopped")
        except Exception as e:
            logger.error("Heartbeat loop error: %s", e, exc_info=True)

    # ==========================================
    # 连接管理
    # ==========================================
    async def connect(self, websocket: WebSocket, user_id: str):
        """接受新连接，如果用户已有连接则踢掉旧连接"""
        # 踢掉旧连接（互斥策略）
        if user_id in self.active_connections:
            old_ws = self.active_connections[user_id]
            logger.warning(
                "Kicking old connection for user %s (duplicate session)", user_id
            )
            try:
                await old_ws.close(code=4001, reason="duplicate_session")
            except Exception:
                pass  # 旧连接可能已断开
            # 清理旧记录
            self._remove(user_id)

        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.heartbeat_timestamps[user_id] = time.time()
        logger.info(
            "User %s connected. Total: %d", user_id, len(self.active_connections)
        )

    def disconnect(self, user_id: str):
        """从管理器中移除连接（不负责关闭 WebSocket 本身）"""
        self._remove(user_id)

    def _remove(self, user_id: str):
        """内部清理方法"""
        removed = False
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            removed = True
        self.heartbeat_timestamps.pop(user_id, None)
        if removed:
            logger.info(
                "User %s removed. Remaining: %d", user_id, len(self.active_connections)
            )

    def update_heartbeat(self, user_id: str):
        """更新心跳时间戳"""
        if user_id in self.active_connections:
            self.heartbeat_timestamps[user_id] = time.time()

    async def check_dead_connections(self):
        """检查并清理超时的僵尸连接（先关闭再删除）"""
        now = time.time()
        dead_users = [
            uid
            for uid, last_time in self.heartbeat_timestamps.items()
            if now - last_time > self.heartbeat_timeout
        ]

        for user_id in dead_users:
            logger.warning(
                "Cleaning up dead connection for user %s (heartbeat timeout)", user_id
            )
            # 先尝试关闭 WebSocket
            ws = self.active_connections.get(user_id)
            if ws:
                try:
                    await ws.close(code=1001, reason="heartbeat_timeout")
                except Exception as e:
                    logger.debug("Error closing dead connection for %s: %s", user_id, e)
            # 再从字典中移除
            self._remove(user_id)

    # ==========================================
    # 消息发送
    # ==========================================
    async def send_personal_message(self, message: dict, user_id: str):
        ws = self.active_connections.get(user_id)
        if ws is None:
            logger.debug("Skip send to disconnected user %s", user_id)
            return
        try:
            await ws.send_text(json.dumps(message, ensure_ascii=False))
            self.update_heartbeat(user_id)
        except Exception as e:
            logger.error("Failed to send message to %s: %s", user_id, e)
            self._remove(user_id)

    async def broadcast(self, message: dict):
        """广播给所有人（并行发送，单个失败不影响其余）"""
        json_msg = json.dumps(message, ensure_ascii=False)
        disconnected = []

        async def _safe_send(uid: str, ws: WebSocket):
            try:
                await ws.send_text(json_msg)
            except Exception:
                disconnected.append(uid)

        await asyncio.gather(
            *[_safe_send(uid, ws) for uid, ws in self.active_connections.items()]
        )
        # 清理发送失败的连接
        for uid in disconnected:
            self._remove(uid)


manager = ConnectionManager()
