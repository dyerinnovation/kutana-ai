"""Turn management domain models."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class HandRaisePriority(enum.StrEnum):
    """Priority level for a hand raise."""

    NORMAL = "normal"
    URGENT = "urgent"


class QueueEntry(BaseModel):
    """A single entry in the speaker queue.

    Attributes:
        participant_id: The participant waiting to speak.
        hand_raise_id: Unique ID for this specific hand raise event.
        priority: Queue priority — urgent entries sort before normal ones.
        topic: Optional topic the participant wants to discuss.
        raised_at: When the hand was raised (UTC).
        position: 1-based position in the queue.
    """

    participant_id: UUID
    hand_raise_id: UUID = Field(default_factory=uuid4)
    priority: HandRaisePriority = HandRaisePriority.NORMAL
    topic: str | None = None
    raised_at: datetime = Field(default_factory=_utc_now)
    position: int


class QueueStatus(BaseModel):
    """Snapshot of the speaker queue for a meeting.

    Attributes:
        meeting_id: The meeting this status belongs to.
        active_speaker_id: Current active speaker, or None if no one is speaking.
        queue: Ordered list of participants waiting to speak (position 1 = next up).
    """

    meeting_id: UUID
    active_speaker_id: UUID | None = None
    queue: list[QueueEntry] = Field(default_factory=list)


class SpeakingStatus(BaseModel):
    """Speaking status of a specific participant.

    Attributes:
        participant_id: The participant being queried.
        is_speaking: True if this participant is the active speaker.
        in_queue: True if this participant is waiting in the queue.
        queue_position: 1-based queue position, or None if not in queue.
        hand_raise_id: ID of the active hand raise, or None if not in queue.
    """

    participant_id: UUID
    is_speaking: bool
    in_queue: bool
    queue_position: int | None = None
    hand_raise_id: UUID | None = None


class RaiseHandResult(BaseModel):
    """Result of a raise_hand operation.

    Attributes:
        queue_position: 1-based position in queue. 0 means immediately promoted.
        hand_raise_id: Unique ID assigned to this hand raise.
        was_promoted: True if the participant was immediately set as active speaker.
    """

    queue_position: int
    hand_raise_id: UUID
    was_promoted: bool
