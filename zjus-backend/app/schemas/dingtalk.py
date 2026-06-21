"""DingTalk private-message state schemas and normalization helpers.

Copyright (c) 2026 pirate-608. Licensed under the MIT License.
The schemas keep contact IDs, message IDs, reply options, unread counts, and
round state stable across Redis, PostgreSQL saves, and WebSocket payloads.
"""

import hashlib
import time
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

REPLYABLE_DINGTALK_ROLES = {
    "roommate",
    "classmate",
    "friend",
    "teaching_assistant",
    "teacher",
    "crush",
}

DINGTALK_ROLE_ALIASES = {
    "student": "classmate",
    "students": "classmate",
    "同学": "classmate",
    "同班同学": "classmate",
    "室友": "roommate",
    "舍友": "roommate",
    "roomie": "roommate",
    "ta": "teaching_assistant",
    "assistant": "teaching_assistant",
    "助教": "teaching_assistant",
    "老师": "teacher",
    "教师": "teacher",
    "朋友": "friend",
    "好友": "friend",
    "crush": "crush",
    "暗恋对象": "crush",
}

DINGTALK_MAX_MESSAGES_PER_CONTACT = 50
DINGTALK_DEFAULT_MAX_CONTACTS = 12


def normalize_dingtalk_role(role: str) -> str:
    """Normalize human-facing role aliases into canonical DingTalk role IDs."""
    normalized = str(role or "unknown").strip().lower()
    return DINGTALK_ROLE_ALIASES.get(normalized, normalized)


def build_contact_id(sender: str, role: str) -> str:
    """Build a deterministic contact ID from a sender name and role."""
    raw = f"{normalize_dingtalk_role(role)}:{sender.strip()}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"dt_{digest}"


def is_replyable_role(role: str) -> bool:
    """Return whether a normalized role supports player replies."""
    return normalize_dingtalk_role(role) in REPLYABLE_DINGTALK_ROLES


def new_message_id() -> str:
    """Return a compact globally unique DingTalk message ID."""
    return f"dtm_{uuid.uuid4().hex[:16]}"


def now_ts() -> int:
    """Return the current Unix timestamp used in DingTalk state payloads."""
    return int(time.time())


class DingTalkReplyOption(BaseModel):
    """A single player-selectable reply option for an open conversation round."""

    option_id: str
    text: str


class DingTalkRoundState(BaseModel):
    """Conversation-round progress for settlement after three player replies."""

    round_id: str = ""
    status: Literal["open", "closed"] = "closed"
    player_reply_count: int = 0


class DingTalkMessage(BaseModel):
    """Persisted DingTalk message exchanged by NPC, player, or system."""

    message_id: str
    speaker: Literal["npc", "player", "system"]
    content: str
    created_at: int
    round_id: str | None = None


class DingTalkContact(BaseModel):
    """A private DingTalk contact with bounded history and reply state."""

    contact_id: str
    sender: str
    role: str
    is_replyable: bool = False
    is_urgent: bool = False
    unread_count: int = 0
    last_message_at: int = 0
    messages: list[DingTalkMessage] = Field(default_factory=list)
    pending_options: list[DingTalkReplyOption] = Field(default_factory=list)
    round: DingTalkRoundState = Field(default_factory=DingTalkRoundState)

    def trim_messages(self) -> None:
        """Keep only the latest messages for this contact."""
        if len(self.messages) > DINGTALK_MAX_MESSAGES_PER_CONTACT:
            self.messages = self.messages[-DINGTALK_MAX_MESSAGES_PER_CONTACT:]


class DingTalkState(BaseModel):
    """Top-level DingTalk inbox state persisted in Redis and save slots."""

    version: int = 1
    contacts: dict[str, DingTalkContact] = Field(default_factory=dict)
    updated_at: int = 0

    @classmethod
    def from_raw(cls, raw: Any) -> "DingTalkState":
        """Parse persisted DingTalk state, falling back to an empty inbox.

        Args:
            raw: Redis/PostgreSQL value or an already-validated state object.

        Returns:
            A valid DingTalk state object. Corrupt legacy data is discarded
            instead of blocking game startup.
        """
        if not raw:
            return cls(updated_at=now_ts())
        if isinstance(raw, cls):
            return raw
        try:
            return cls.model_validate(raw)
        except Exception:
            return cls(updated_at=now_ts())

    def compact(self, max_contacts: int | None = None) -> "DingTalkState":
        """Trim histories and remove oldest closed contacts beyond a cap.

        Args:
            max_contacts: Optional maximum contact count. Open conversation
                rounds are preserved even when the list is above the cap.

        Returns:
            The mutated state instance for fluent save/update paths.
        """
        for contact in self.contacts.values():
            contact.trim_messages()
        if max_contacts is not None and max_contacts > 0:
            removable = [
                contact
                for contact in self.contacts.values()
                if contact.round.status != "open"
            ]
            removable.sort(key=lambda c: (c.last_message_at, c.contact_id))
            while len(self.contacts) > max_contacts and removable:
                contact = removable.pop(0)
                self.contacts.pop(contact.contact_id, None)
        self.updated_at = now_ts()
        return self
