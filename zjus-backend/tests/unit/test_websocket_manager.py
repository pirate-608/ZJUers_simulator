"""Focused tests for WebSocket connection manager behavior."""

import asyncio
import json

import pytest

from app.websockets.manager import ConnectionManager


class _SlowWebSocket:
    """Fake socket that exposes concurrent send attempts."""

    def __init__(self):
        self.sent: list[dict] = []
        self.inflight = 0
        self.max_inflight = 0
        self.closed: tuple[int, str] | None = None

    async def accept(self):
        return None

    async def send_text(self, payload: str):
        self.inflight += 1
        self.max_inflight = max(self.max_inflight, self.inflight)
        await asyncio.sleep(0)
        self.sent.append(json.loads(payload))
        self.inflight -= 1

    async def close(self, code: int = 1000, reason: str = ""):
        self.closed = (code, reason)


@pytest.mark.asyncio
async def test_send_personal_message_serializes_per_user_sends():
    manager = ConnectionManager()
    ws = _SlowWebSocket()

    await manager.register_accepted("1", ws)  # type: ignore[arg-type]
    await asyncio.gather(
        manager.send_personal_message({"type": "first"}, "1"),
        manager.send_personal_message({"type": "second"}, "1"),
    )

    assert [message["type"] for message in ws.sent] == ["first", "second"]
    assert ws.max_inflight == 1

    manager.disconnect("1", ws)  # type: ignore[arg-type]
    assert "1" not in manager.active_connections
    assert "1" not in manager._send_locks


@pytest.mark.asyncio
async def test_register_accepted_replaces_duplicate_connection():
    manager = ConnectionManager()
    old_ws = _SlowWebSocket()
    new_ws = _SlowWebSocket()

    await manager.register_accepted("1", old_ws)  # type: ignore[arg-type]
    await manager.register_accepted("1", new_ws)  # type: ignore[arg-type]

    assert old_ws.closed == (4001, "duplicate_session")
    assert manager.active_connections["1"] is new_ws
