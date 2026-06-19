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
    normalized = str(role or "unknown").strip().lower()
    return DINGTALK_ROLE_ALIASES.get(normalized, normalized)


def build_contact_id(sender: str, role: str) -> str:
    raw = f"{normalize_dingtalk_role(role)}:{sender.strip()}"
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"dt_{digest}"


def is_replyable_role(role: str) -> bool:
    return normalize_dingtalk_role(role) in REPLYABLE_DINGTALK_ROLES


def new_message_id() -> str:
    return f"dtm_{uuid.uuid4().hex[:16]}"


def now_ts() -> int:
    return int(time.time())


class DingTalkReplyOption(BaseModel):
    option_id: str
    text: str


class DingTalkRoundState(BaseModel):
    round_id: str = ""
    status: Literal["open", "closed"] = "closed"
    player_reply_count: int = 0


class DingTalkMessage(BaseModel):
    message_id: str
    speaker: Literal["npc", "player", "system"]
    content: str
    created_at: int
    round_id: str | None = None


class DingTalkContact(BaseModel):
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
        if len(self.messages) > DINGTALK_MAX_MESSAGES_PER_CONTACT:
            self.messages = self.messages[-DINGTALK_MAX_MESSAGES_PER_CONTACT:]


class DingTalkState(BaseModel):
    version: int = 1
    contacts: dict[str, DingTalkContact] = Field(default_factory=dict)
    updated_at: int = 0

    @classmethod
    def from_raw(cls, raw: Any) -> "DingTalkState":
        if not raw:
            return cls(updated_at=now_ts())
        if isinstance(raw, cls):
            return raw
        try:
            return cls.model_validate(raw)
        except Exception:
            return cls(updated_at=now_ts())

    def compact(self, max_contacts: int | None = None) -> "DingTalkState":
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
