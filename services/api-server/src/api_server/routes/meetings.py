"""Meeting CRUD endpoints (wired to database)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, or_, select

from api_server.billing_deps import check_meeting_limit
from api_server.deps import get_db_session, get_event_publisher
from kutana_core.database.models import MeetingInviteORM, MeetingORM, UserORM
from kutana_core.events.definitions import MeetingEnded, MeetingStarted
from kutana_core.models.meeting import MeetingStatus

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

    from api_server.auth_deps import CurrentUser, CurrentUserOrAgent
    from api_server.event_publisher import EventPublisher

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
    """List meetings the current user owns or is invited to.

    Args:
        _current_user: Authenticated user (required for access).
        db: Database session.

    Returns:
        MeetingListResponse with meeting data.
    """
    # User sees meetings they own OR are invited to
    invite_exists = exists(
        select(MeetingInviteORM.id).where(
            MeetingInviteORM.meeting_id == MeetingORM.id,
            MeetingInviteORM.user_id == _current_user.id,
        )
    )
    ownership_filter = or_(
        MeetingORM.owner_id == _current_user.id,
        invite_exists,
        # Include legacy meetings with no owner (created before this migration)
        MeetingORM.owner_id.is_(None),
    )

    result = await db.execute(
        select(MeetingORM).where(ownership_filter).order_by(MeetingORM.scheduled_at.desc())
    )
    meetings = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).select_from(MeetingORM).where(ownership_filter)
    )
    total = count_result.scalar_one()

    return MeetingListResponse(
        items=[_to_response(m) for m in meetings],
        total=total,
    )


@router.post("", response_model=MeetingResponse, status_code=201)
async def create_meeting(
    body: MeetingCreateRequest,
    current_user: CurrentUserOrAgent,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeetingResponse:
    """Create a new meeting.

    Args:
        body: The meeting creation payload.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        MeetingResponse with the newly created meeting data.

    Raises:
        HTTPException: 402/403 if the user has no active subscription or
            has hit their monthly meeting limit.
    """
    await check_meeting_limit(current_user, db)
    meeting = MeetingORM(
        platform=body.platform,
        title=body.title,
        scheduled_at=body.scheduled_at,
        status=MeetingStatus.SCHEDULED.value,
        owner_id=current_user.id,
    )
    db.add(meeting)
    current_user.meetings_this_month += 1
    await db.flush()
    await db.refresh(meeting)

    # Auto-invite the owner
    invite = MeetingInviteORM(
        meeting_id=meeting.id,
        user_id=current_user.id,
        status="accepted",
    )
    db.add(invite)
    await db.flush()

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
    result = await db.execute(select(MeetingORM).where(MeetingORM.id == meeting_id))
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
    result = await db.execute(select(MeetingORM).where(MeetingORM.id == meeting_id))
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
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
) -> MeetingResponse:
    """Start a meeting (transition from scheduled to active).

    Publishes a MeetingStarted event to Redis Streams so the
    MeetingEventRelay can notify managed agent sessions.

    Args:
        meeting_id: The UUID of the meeting to start.
        _current_user: Authenticated user.
        db: Database session.
        publisher: Event publisher for Redis Streams.

    Returns:
        Updated MeetingResponse with active status.

    Raises:
        HTTPException: 404 if not found, 409 if not in scheduled status.
    """
    result = await db.execute(select(MeetingORM).where(MeetingORM.id == meeting_id))
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

    await publisher.publish(MeetingStarted(meeting_id=meeting_id))

    return _to_response(meeting)


@router.post("/{meeting_id}/end", response_model=MeetingResponse)
async def end_meeting(
    meeting_id: UUID,
    _current_user: CurrentUserOrAgent,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
) -> MeetingResponse:
    """End a meeting (transition from active to completed).

    Publishes a MeetingEnded event to Redis Streams so the
    MeetingEventRelay can close managed agent sessions and record billing.

    Args:
        meeting_id: The UUID of the meeting to end.
        _current_user: Authenticated user.
        db: Database session.
        publisher: Event publisher for Redis Streams.

    Returns:
        Updated MeetingResponse with completed status.

    Raises:
        HTTPException: 404 if not found, 409 if not in active status.
    """
    result = await db.execute(select(MeetingORM).where(MeetingORM.id == meeting_id))
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

    await publisher.publish(MeetingEnded(meeting_id=meeting_id))

    return _to_response(meeting)


# ---------------------------------------------------------------------------
# Invite schemas
# ---------------------------------------------------------------------------


class InviteRequest(BaseModel):
    """Request body for inviting a user to a meeting.

    Attributes:
        email: Email address of the user to invite.
    """

    email: str


class InviteResponse(BaseModel):
    """Response model for a meeting invite.

    Attributes:
        id: Invite UUID.
        meeting_id: Meeting UUID.
        user_id: Invited user UUID.
        email: Invited user email.
        status: Invite status.
        created_at: When the invite was created.
    """

    id: UUID
    meeting_id: UUID
    user_id: UUID
    email: str
    status: str
    created_at: datetime


class InviteListResponse(BaseModel):
    """List of meeting invites.

    Attributes:
        items: List of invite response objects.
    """

    items: list[InviteResponse]


# ---------------------------------------------------------------------------
# Invite endpoints
# ---------------------------------------------------------------------------


@router.post("/{meeting_id}/invite", response_model=InviteResponse, status_code=201)
async def invite_to_meeting(
    meeting_id: UUID,
    body: InviteRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> InviteResponse:
    """Invite a user to a meeting by email. Only the meeting owner can invite.

    Args:
        meeting_id: The UUID of the meeting.
        body: The invite payload containing the user email.
        current_user: Authenticated user (must be meeting owner).
        db: Database session.

    Returns:
        InviteResponse with the created invite data.

    Raises:
        HTTPException: 404 if meeting or user not found, 403 if not owner,
            409 if user is already invited.
    """
    # Look up meeting
    result = await db.execute(select(MeetingORM).where(MeetingORM.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    # Only the owner can invite
    if meeting.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the meeting owner can send invitations",
        )

    # Look up invitee by email
    user_result = await db.execute(select(UserORM).where(UserORM.email == body.email))
    invitee = user_result.scalar_one_or_none()
    if invitee is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No user found with email '{body.email}'",
        )

    # Check for existing invite
    existing = await db.execute(
        select(MeetingInviteORM).where(
            MeetingInviteORM.meeting_id == meeting_id,
            MeetingInviteORM.user_id == invitee.id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User is already invited to this meeting",
        )

    invite = MeetingInviteORM(
        meeting_id=meeting_id,
        user_id=invitee.id,
        status="accepted",
    )
    db.add(invite)
    await db.flush()
    await db.refresh(invite)

    return InviteResponse(
        id=invite.id,
        meeting_id=invite.meeting_id,
        user_id=invite.user_id,
        email=invitee.email,
        status=invite.status,
        created_at=invite.created_at,
    )


@router.get("/{meeting_id}/invites", response_model=InviteListResponse)
async def list_meeting_invites(
    meeting_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> InviteListResponse:
    """List all invites for a meeting. Only the meeting owner can view.

    Args:
        meeting_id: The UUID of the meeting.
        current_user: Authenticated user (must be meeting owner).
        db: Database session.

    Returns:
        InviteListResponse with invite data.

    Raises:
        HTTPException: 404 if meeting not found, 403 if not owner.
    """
    # Look up meeting
    result = await db.execute(select(MeetingORM).where(MeetingORM.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    if meeting.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the meeting owner can view invitations",
        )

    invite_result = await db.execute(
        select(MeetingInviteORM, UserORM.email)
        .join(UserORM, MeetingInviteORM.user_id == UserORM.id)
        .where(MeetingInviteORM.meeting_id == meeting_id)
        .order_by(MeetingInviteORM.created_at)
    )
    rows = invite_result.all()

    return InviteListResponse(
        items=[
            InviteResponse(
                id=invite.id,
                meeting_id=invite.meeting_id,
                user_id=invite.user_id,
                email=email,
                status=invite.status,
                created_at=invite.created_at,
            )
            for invite, email in rows
        ]
    )
