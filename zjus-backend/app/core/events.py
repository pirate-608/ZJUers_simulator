"""Internal game-event envelope definitions.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
`GameEvent` is the small transport object used between the game engine and the
WebSocket fan-out loop.
"""

from typing import Any, Dict, Optional

from pydantic import BaseModel


class GameEvent(BaseModel):
    """Game event emitted by the engine."""

    user_id: str
    event_type: str
    data: Dict[str, Any]
    message: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        """Return the JSON object sent over the game WebSocket."""
        payload = {"type": self.event_type}
        payload.update(self.data or {})
        return payload
