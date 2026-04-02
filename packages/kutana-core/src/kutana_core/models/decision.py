"""Decision domain model."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class Decision(BaseModel):
    """Represents a decision made during a meeting.

    Attributes:
        id: Unique decision identifier.
        meeting_id: ID of the meeting where the decision was made.
        description: Human-readable description of the decision.
        decided_by_id: ID of the participant who made the decision.
        participants_present: List of participant IDs present when decided.
        created_at: When this record was created.
    """

    id: UUID = Field(default_factory=uuid4)
    meeting_id: UUID
    description: str
    decided_by_id: UUID
    participants_present: list[UUID] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
