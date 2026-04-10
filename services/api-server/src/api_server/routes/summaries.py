"""Meeting summary endpoints — on-demand Haiku generation with caching."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — FastAPI DI

from api_server.auth_deps import CurrentUser  # noqa: TC001 — FastAPI DI
from api_server.deps import get_db_session
from kutana_core.database.models import (
    MeetingORM,
    MeetingSummaryORM,
    TaskORM,
    TranscriptSegmentORM,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/meetings", tags=["summaries"])

# The Haiku model used for on-demand summary generation.
_HAIKU_MODEL = "claude-3-5-haiku-20241022"
_MAX_SUMMARY_TOKENS = 1024


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class MeetingSummaryResponse(BaseModel):
    """Structured meeting summary returned to callers.

    Attributes:
        meeting_id: UUID of the meeting.
        title: Meeting title.
        duration_minutes: Meeting duration in minutes (None if not ended).
        participant_count: Number of distinct speakers in transcript.
        key_points: Bullet-point discussion highlights.
        decisions: Recorded decisions.
        task_count: Number of extracted tasks.
        ended_at: When the meeting ended (None if still active).
        generated_at: When this summary was generated.
    """

    meeting_id: UUID
    title: str | None = None
    duration_minutes: int | None = None
    participant_count: int = 0
    key_points: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    task_count: int = 0
    ended_at: datetime | None = None
    generated_at: datetime


# ---------------------------------------------------------------------------
# Haiku summary generation
# ---------------------------------------------------------------------------

_SUMMARY_SYSTEM_PROMPT = """\
You are a meeting summarizer. Given transcript segments, produce a JSON object with:
- "key_points": list of 3-7 concise bullet points capturing the main discussion topics
- "decisions": list of any decisions or agreements made (empty list if none)

Be concise. Each point should be one sentence. Do not include filler."""


async def _generate_summary_via_haiku(
    segments: list[TranscriptSegmentORM],
) -> tuple[list[str], list[str], str]:
    """Generate summary key_points and decisions using Claude Haiku.

    Args:
        segments: Transcript segments from the meeting.

    Returns:
        Tuple of (key_points, decisions, model_used).
    """
    import anthropic

    # Build transcript text from segments
    lines: list[str] = []
    for seg in segments:
        speaker = seg.speaker_id or "Unknown"
        lines.append(f"[{speaker}]: {seg.text}")
    transcript_text = "\n".join(lines)

    if not transcript_text.strip():
        return (["No transcript content available."], [], _HAIKU_MODEL)

    # Truncate to ~100k chars to stay within context window
    if len(transcript_text) > 100_000:
        transcript_text = transcript_text[:100_000] + "\n[... transcript truncated ...]"

    client = anthropic.AsyncAnthropic()

    response = await client.messages.create(
        model=_HAIKU_MODEL,
        max_tokens=_MAX_SUMMARY_TOKENS,
        system=_SUMMARY_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": (f"Summarize this meeting transcript:\n\n{transcript_text}"),
            }
        ],
    )

    # Parse the response — Haiku should return JSON
    raw_text = response.content[0].text  # type: ignore[union-attr]

    # Try to extract JSON from the response
    try:
        # Handle case where model wraps JSON in markdown code block
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1]
            cleaned = cleaned.rsplit("```", 1)[0]
        data = json.loads(cleaned)
        key_points = data.get("key_points", [])
        decisions = data.get("decisions", [])
    except (json.JSONDecodeError, IndexError):
        # Fallback: treat the whole response as a single key point
        key_points = [raw_text.strip()]
        decisions = []

    return (key_points, decisions, _HAIKU_MODEL)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("/{meeting_id}/summary", response_model=MeetingSummaryResponse)
async def get_meeting_summary(
    meeting_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    regenerate: bool = False,
) -> MeetingSummaryResponse:
    """Get or generate a meeting summary.

    Returns a cached summary if available, otherwise generates one
    on-demand using Claude Haiku over the transcript segments.

    Args:
        meeting_id: UUID of the meeting.
        current_user: Authenticated user.
        db: Async database session.
        regenerate: Force regeneration even if cached.

    Returns:
        MeetingSummaryResponse with structured summary data.

    Raises:
        HTTPException: 404 if meeting not found.
    """
    # Verify meeting exists
    result = await db.execute(select(MeetingORM).where(MeetingORM.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    # Check for cached summary
    if not regenerate:
        cached_result = await db.execute(
            select(MeetingSummaryORM).where(MeetingSummaryORM.meeting_id == meeting_id)
        )
        cached = cached_result.scalar_one_or_none()
        if cached is not None:
            # Get task count fresh
            task_count_result = await db.execute(
                select(func.count()).select_from(TaskORM).where(TaskORM.meeting_id == meeting_id)
            )
            task_count = task_count_result.scalar() or 0

            # Get participant count from transcript
            participant_result = await db.execute(
                select(func.count(func.distinct(TranscriptSegmentORM.speaker_id))).where(
                    TranscriptSegmentORM.meeting_id == meeting_id
                )
            )
            participant_count = participant_result.scalar() or 0

            # Calculate duration
            duration_minutes = None
            if meeting.started_at and meeting.ended_at:
                delta = meeting.ended_at - meeting.started_at
                duration_minutes = int(delta.total_seconds() / 60)

            return MeetingSummaryResponse(
                meeting_id=meeting_id,
                title=meeting.title,
                duration_minutes=duration_minutes,
                participant_count=participant_count,
                key_points=cached.key_points,
                decisions=cached.decisions,
                task_count=task_count,
                ended_at=meeting.ended_at,
                generated_at=cached.generated_at,
            )

    # Generate on-demand via Haiku
    segments_result = await db.execute(
        select(TranscriptSegmentORM)
        .where(TranscriptSegmentORM.meeting_id == meeting_id)
        .order_by(TranscriptSegmentORM.start_time)
    )
    segments = list(segments_result.scalars().all())

    if not segments:
        # Return empty summary for meetings with no transcript
        return MeetingSummaryResponse(
            meeting_id=meeting_id,
            title=meeting.title,
            duration_minutes=None,
            participant_count=0,
            key_points=["No transcript segments available for this meeting."],
            decisions=[],
            task_count=0,
            ended_at=meeting.ended_at,
            generated_at=datetime.now(tz=UTC),
        )

    key_points, decisions, model_used = await _generate_summary_via_haiku(segments)

    # Get task count
    task_count_result = await db.execute(
        select(func.count()).select_from(TaskORM).where(TaskORM.meeting_id == meeting_id)
    )
    task_count = task_count_result.scalar() or 0

    # Get participant count
    participant_result = await db.execute(
        select(func.count(func.distinct(TranscriptSegmentORM.speaker_id))).where(
            TranscriptSegmentORM.meeting_id == meeting_id
        )
    )
    participant_count = participant_result.scalar() or 0

    # Calculate duration
    duration_minutes = None
    if meeting.started_at and meeting.ended_at:
        delta = meeting.ended_at - meeting.started_at
        duration_minutes = int(delta.total_seconds() / 60)

    now = datetime.now(tz=UTC)

    # Cache the summary — upsert
    existing_result = await db.execute(
        select(MeetingSummaryORM).where(MeetingSummaryORM.meeting_id == meeting_id)
    )
    existing = existing_result.scalar_one_or_none()
    if existing is not None:
        existing.key_points = key_points
        existing.decisions = decisions
        existing.task_count = task_count
        existing.generated_at = now
        existing.model_used = model_used
    else:
        summary_row = MeetingSummaryORM(
            id=uuid4(),
            meeting_id=meeting_id,
            key_points=key_points,
            decisions=decisions,
            task_count=task_count,
            generated_at=now,
            model_used=model_used,
        )
        db.add(summary_row)

    return MeetingSummaryResponse(
        meeting_id=meeting_id,
        title=meeting.title,
        duration_minutes=duration_minutes,
        participant_count=participant_count,
        key_points=key_points,
        decisions=decisions,
        task_count=task_count,
        ended_at=meeting.ended_at,
        generated_at=now,
    )
