"""Participant domain model."""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ParticipantRole(enum.StrEnum):
    """Role of a participant in a meeting."""

    HOST = "host"
    PARTICIPANT = "participant"
    AGENT = "agent"
    OBSERVER = "observer"


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class Participant(BaseModel):
    """Represents a meeting participant.

    Attributes:
        id: Unique participant identifier.
        name: Display name of the participant.
        email: Optional email address.
        speaker_id: Speaker identifier from diarization.
        role: Role of the participant in the meeting.
        created_at: When this record was created.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str
    email: str | None = None
    speaker_id: str | None = None
    role: ParticipantRole = ParticipantRole.PARTICIPANT
    connection_type: str | None = None
    agent_config_id: UUID | None = None
    created_at: datetime = Field(default_factory=_utc_now)
