"""Meeting CRUD endpoints (wired to database)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.auth_deps import CurrentUser, CurrentUserOrAgent
from api_server.deps import get_db_session
from kutana_core.database.models import MeetingORM
from kutana_core.models.meeting import MeetingStatus

router = APIRouter(prefix="/meetings", tags=["meetings"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class MeetingCreateRequest(BaseModel):
    """Request body for creating a new meeting.

    Attributes:
        platform: Meeting platform (e.g. "kutana", "zoom").
        title: Optional human-readable meeting title.
        scheduled_at: When the meeting is scheduled to start.
    """

    platform: str = "kutana"
    title: str | None = None
    scheduled_at: datetime


class MeetingResponse(BaseModel):
    """Response model for a single meeting.

    Attributes:
        id: Unique meeting identifier.
        platform: Meeting platform name.
        title: Human-readable meeting title.
        scheduled_at: Scheduled start time.
        started_at: Actual start time.
        ended_at: End time.
        status: Current meeting status.
        created_at: Record creation timestamp.
        updated_at: Record last-update timestamp.
    """

    id: UUID
    platform: str
    title: str | None = None
    scheduled_at: datetime
    started_at: datetime | None = None
    ended_at: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class MeetingUpdateRequest(BaseModel):
    """Request body for updating a meeting.

    Attributes:
        title: Updated meeting title.
        scheduled_at: Updated scheduled time.
        platform: Updated platform.
    """

    title: str | None = None
    scheduled_at: datetime | None = None
    platform: str | None = None


class MeetingListResponse(BaseModel):
    """Paginated list of meetings.

    Attributes:
        items: List of meeting response objects.
        total: Total number of meetings matching the query.
    """

    items: list[MeetingResponse]
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(meeting: MeetingORM) -> MeetingResponse:
    return MeetingResponse(
        id=meeting.id,
        platform=meeting.platform,
        title=meeting.title,
        scheduled_at=meeting.scheduled_at,
        started_at=meeting.started_at,
        ended_at=meeting.ended_at,
        status=meeting.status,
        created_at=meeting.created_at,
        updated_at=meeting.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=MeetingListResponse)
async def list_meetings(
    _current_user: CurrentUserOrAgent,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeetingListResponse:
    """List all meetings.

    Args:
        _current_user: Authenticated user (required for access).
        db: Database session.

    Returns:
        MeetingListResponse with meeting data.
    """
    result = await db.execute(
        select(MeetingORM).order_by(MeetingORM.scheduled_at.desc())
    )
    meetings = result.scalars().all()

    count_result = await db.execute(select(func.count()).select_from(MeetingORM))
    total = count_result.scalar_one()

    return MeetingListResponse(
        items=[_to_response(m) for m in meetings],
        total=total,
    )


@router.post("", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    body: MeetingCreateRequest,
    _current_user: CurrentUserOrAgent,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeetingResponse:
    """Create a new meeting.

    Args:
        body: The meeting creation payload.
        _current_user: Authenticated user.
        db: Database session.

    Returns:
        MeetingResponse with the newly created meeting data.
    """
    meeting = MeetingORM(
        platform=body.platform,
        title=body.title,
        scheduled_at=body.scheduled_at,
        status=MeetingStatus.SCHEDULED.value,
    )
    db.add(meeting)
    await db.flush()
    await db.refresh(meeting)
    return _to_response(meeting)


@router.get("/{meeting_id}", response_model=MeetingResponse)
async def get_meeting(
    meeting_id: UUID,
    _current_user: CurrentUserOrAgent,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeetingResponse:
    """Get a single meeting by ID.

    Args:
        meeting_id: The UUID of the meeting to retrieve.
        _current_user: Authenticated user.
        db: Database session.

    Returns:
        MeetingResponse for the requested meeting.

    Raises:
        HTTPException: 404 if meeting not found.
    """
    result = await db.execute(
        select(MeetingORM).where(MeetingORM.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    return _to_response(meeting)


@router.patch("/{meeting_id}", response_model=MeetingResponse)
async def update_meeting(
    meeting_id: UUID,
    body: MeetingUpdateRequest,
    _current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeetingResponse:
    """Update meeting fields (title, scheduled_at, platform).

    Args:
        meeting_id: The UUID of the meeting to update.
        body: Fields to update.
        _current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated MeetingResponse.

    Raises:
        HTTPException: 404 if meeting not found.
    """
    result = await db.execute(
        select(MeetingORM).where(MeetingORM.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(meeting, field, value)

    await db.flush()
    await db.refresh(meeting)
    return _to_response(meeting)


@router.post("/{meeting_id}/start", response_model=MeetingResponse)
async def start_meeting(
    meeting_id: UUID,
    _current_user: CurrentUserOrAgent,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeetingResponse:
    """Start a meeting (transition from scheduled to active).

    Args:
        meeting_id: The UUID of the meeting to start.
        _current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated MeetingResponse with active status.

    Raises:
        HTTPException: 404 if not found, 409 if not in scheduled status.
    """
    result = await db.execute(
        select(MeetingORM).where(MeetingORM.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    if meeting.status != MeetingStatus.SCHEDULED.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot start meeting in '{meeting.status}' status; must be 'scheduled'",
        )

    meeting.status = MeetingStatus.ACTIVE.value
    meeting.started_at = datetime.now(tz=UTC)
    await db.flush()
    await db.refresh(meeting)
    return _to_response(meeting)


@router.post("/{meeting_id}/end", response_model=MeetingResponse)
async def end_meeting(
    meeting_id: UUID,
    _current_user: CurrentUserOrAgent,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeetingResponse:
    """End a meeting (transition from active to completed).

    Args:
        meeting_id: The UUID of the meeting to end.
        _current_user: Authenticated user.
        db: Database session.

    Returns:
        Updated MeetingResponse with completed status.

    Raises:
        HTTPException: 404 if not found, 409 if not in active status.
    """
    result = await db.execute(
        select(MeetingORM).where(MeetingORM.id == meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    if meeting.status != MeetingStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot end meeting in '{meeting.status}' status; must be 'active'",
        )

    meeting.status = MeetingStatus.COMPLETED.value
    meeting.ended_at = datetime.now(tz=UTC)
    await db.flush()
    await db.refresh(meeting)
    return _to_response(meeting)
