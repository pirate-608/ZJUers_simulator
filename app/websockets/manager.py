from fastapi import WebSocket
from typing import Dict, List
import json

class ConnectionManager:
    def __init__(self):
        # 存放活跃连接: user_id -> WebSocket
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket
        print(f"[WS] User {user_id} connected. Total: {len(self.active_connections)}")
        print(f"[WS][DEBUG] active_connections keys: {list(self.active_connections.keys())}")

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            print(f"[WS] User {user_id} disconnected.")
            print(f"[WS][DEBUG] active_connections keys after disconnect: {list(self.active_connections.keys())}")

    async def send_personal_message(self, message: dict, user_id: str):
        if user_id in self.active_connections:
            websocket = self.active_connections[user_id]
            print(f"[WS][DEBUG] send_personal_message to {user_id}, message type: {message.get('type')}")
            await websocket.send_text(json.dumps(message))
        else:
            print(f"[WS][ERROR] Tried to send message to {user_id}, but not in active_connections! Current keys: {list(self.active_connections.keys())}")

    async def broadcast(self, message: dict):
        """广播给所有人（比如全服公告）"""
        json_msg = json.dumps(message)
        for connection in self.active_connections.values():
            await connection.send_text(json_msg)

manager = ConnectionManager()