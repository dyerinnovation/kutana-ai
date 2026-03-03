"""Room domain model."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RoomStatus(enum.StrEnum):
    """Status of a meeting room."""

    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class Room(BaseModel):
    """Represents a meeting room that participants and agents join.

    Attributes:
        id: Unique room identifier.
        name: Human-readable unique room name.
        meeting_id: Associated meeting ID.
        livekit_room_id: LiveKit room identifier (set when LiveKit is used).
        status: Current room status.
        max_participants: Maximum number of participants allowed (0 = unlimited).
        created_at: When this record was created.
        updated_at: When this record was last updated.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str
    meeting_id: UUID | None = None
    livekit_room_id: str | None = None
    status: RoomStatus = RoomStatus.PENDING
    max_participants: int = Field(default=0, ge=0)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
