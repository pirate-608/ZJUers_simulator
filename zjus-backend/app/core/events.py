from typing import Any, Dict, Optional
from pydantic import BaseModel


class GameEvent(BaseModel):
    """Game event emitted by the engine."""

    user_id: str
    event_type: str
    data: Dict[str, Any]
    message: Optional[str] = None

    def to_payload(self) -> Dict[str, Any]:
        payload = {"type": self.event_type}
        payload.update(self.data or {})
        return payload
