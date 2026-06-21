"""Connection registry and heartbeat helpers for game WebSockets.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The manager tracks active sockets by user, serializes sends, and handles
heartbeat timeout cleanup.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Track active game WebSocket connections and heartbeat liveness."""

    def __init__(self):
        """Create an empty connection registry."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.heartbeat_timestamps: Dict[str, float] = {}
        self.heartbeat_timeout = 60
        self._heartbeat_task: Optional[asyncio.Task] = None

    def start_heartbeat_checker(self):
        """Start the singleton heartbeat cleanup task."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            logger.info("Global heartbeat checker started")

    async def _heartbeat_loop(self):
        """Periodically close sockets that stopped sending heartbeats."""
        try:
            while True:
                await asyncio.sleep(30)
                await self.check_dead_connections()
        except asyncio.CancelledError:
            logger.info("Global heartbeat checker stopped")
        except Exception as e:
            logger.error("Heartbeat loop error: %s", e, exc_info=True)

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept a WebSocket and replace any older session for that user."""
        if user_id in self.active_connections:
            old_ws = self.active_connections[user_id]
            logger.warning(
                "Kicking old connection for user %s (duplicate session)", user_id
            )
            try:
                await old_ws.close(code=4001, reason="duplicate_session")
            except Exception:
                pass
            self._remove(user_id)

        await websocket.accept()
        self.active_connections[user_id] = websocket
        self.heartbeat_timestamps[user_id] = time.time()
        logger.info(
            "User %s connected. Total: %d", user_id, len(self.active_connections)
        )

    def disconnect(self, user_id: str, websocket: Optional[WebSocket] = None):
        """Remove a connection from manager state without closing the socket.

        When websocket is provided, only remove the active record if it still
        points to that same connection. This prevents an old duplicate session
        from deleting a newer connection in its cleanup block.
        """
        self._remove(user_id, websocket)

    def _remove(self, user_id: str, websocket: Optional[WebSocket] = None):
        """Remove a connection record if it still points at the expected socket."""
        removed = False
        current = self.active_connections.get(user_id)
        if current is not None and (websocket is None or current is websocket):
            del self.active_connections[user_id]
            removed = True
            self.heartbeat_timestamps.pop(user_id, None)
        if removed:
            logger.info(
                "User %s removed. Remaining: %d", user_id, len(self.active_connections)
            )

    def update_heartbeat(self, user_id: str):
        """Refresh the heartbeat timestamp for a connected user."""
        if user_id in self.active_connections:
            self.heartbeat_timestamps[user_id] = time.time()

    async def check_dead_connections(self):
        """Close and remove heartbeat-expired connections."""
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
            ws = self.active_connections.get(user_id)
            if ws:
                try:
                    await ws.close(code=1001, reason="heartbeat_timeout")
                except Exception as e:
                    logger.debug("Error closing dead connection for %s: %s", user_id, e)
            self._remove(user_id)

    async def send_personal_message(self, message: dict, user_id: str):
        """Send one JSON message to a user if the socket is still active."""
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
        """Broadcast one JSON message, isolating per-socket send failures."""
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
        for uid in disconnected:
            self._remove(uid)


manager = ConnectionManager()
