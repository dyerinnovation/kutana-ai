"""Transcript segment domain model."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class TranscriptSegment(BaseModel):
    """Represents a single segment of meeting transcript.

    Attributes:
        id: Unique segment identifier.
        meeting_id: ID of the meeting this segment belongs to.
        speaker_id: Speaker identifier from diarization.
        speaker_name: Human-readable display name from session identity.
        text: Transcribed text content.
        start_time: Start time in seconds from meeting start.
        end_time: End time in seconds from meeting start.
        confidence: Confidence score from the STT provider (0.0 to 1.0).
        created_at: When this record was created.
    """

    id: UUID = Field(default_factory=uuid4)
    meeting_id: UUID
    speaker_id: str | None = None
    speaker_name: str | None = None
    text: str
    start_time: float
    end_time: float
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=_utc_now)

    @model_validator(mode="after")
    def _validate_segment(self) -> TranscriptSegment:
        """Validate confidence range and time ordering."""
        if not 0.0 <= self.confidence <= 1.0:
            msg = "confidence must be between 0.0 and 1.0"
            raise ValueError(msg)

        if self.start_time >= self.end_time:
            msg = "start_time must be less than end_time"
            raise ValueError(msg)

        return self
