"""Chat domain models."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class ChatMessageType(enum.StrEnum):
    """Semantic type classification for a chat message."""

    TEXT = "text"
    QUESTION = "question"
    ACTION_ITEM = "action_item"
    DECISION = "decision"


class ChatMessage(BaseModel):
    """A single chat message in a meeting.

    Attributes:
        message_id: Unique identifier for this message.
        meeting_id: The meeting this message belongs to.
        sender_id: Participant or agent UUID who sent the message.
        sender_name: Display name of the sender.
        content: The message text.
        message_type: Semantic classification of the message.
        sent_at: Timestamp when the message was sent (UTC).
        sequence: Ordering sequence derived from Redis stream entry ID (ms timestamp).
    """

    message_id: UUID = Field(default_factory=uuid4)
    meeting_id: UUID
    sender_id: UUID
    sender_name: str
    content: str
    message_type: ChatMessageType = ChatMessageType.TEXT
    sent_at: datetime = Field(default_factory=_utc_now)
    sequence: int = 0
