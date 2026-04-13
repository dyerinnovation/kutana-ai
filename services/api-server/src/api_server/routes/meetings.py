"""Meeting CRUD endpoints (wired to database)."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID  # noqa: TC003 — used in runtime route params

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import delete, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — FastAPI DI

from api_server.auth_deps import CurrentUser, CurrentUserOrAgent  # noqa: TC001 — FastAPI DI
from api_server.billing_deps import MANAGED_AGENT_MIN_TIER, check_meeting_limit, require_tier
from api_server.deps import (
    Settings,
    _build_session_factory,
    get_db_session,
    get_event_publisher,
    get_livekit_service,
    get_settings,
)
from api_server.event_publisher import EventPublisher  # noqa: TC001 — FastAPI DI
from api_server.managed_agent_activation import _warm_agent_in_background, _warming_tasks
from api_server.services.livekit_service import LiveKitService  # noqa: TC001 — FastAPI DI
from kutana_core.database.models import (
    AgentSessionORM,
    AgentTemplateORM,
    DecisionORM,
    FeedRunORM,
    HostedAgentSessionORM,
    MeetingInviteORM,
    MeetingORM,
    MeetingSelectedTemplateORM,
    MeetingSummaryORM,
    RoomORM,
    TaskORM,
    TranscriptSegmentORM,
    UserORM,
)
from kutana_core.events.definitions import MeetingEnded, MeetingStarted
from kutana_core.models.meeting import MeetingStatus

logger = logging.getLogger(__name__)

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
    scheduled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_test_meeting: bool = False


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
        is_test_meeting=body.is_test_meeting,
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


@router.delete("/{meeting_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_meeting(
    meeting_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete a meeting owned by the current user and cascade-remove children.

    Removes rows in tables that FK to meetings (tasks, decisions, transcripts,
    agent sessions, hosted agent sessions, feed runs, summaries, rooms,
    invites, selected templates) before deleting the meeting itself.

    Args:
        meeting_id: Meeting to delete.
        current_user: Authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if the meeting is missing, 403 if the caller
            is not the owner.
    """
    result = await db.execute(select(MeetingORM).where(MeetingORM.id == meeting_id))
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
    if meeting.owner_id is not None and meeting.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this meeting",
        )

    for model in (
        TaskORM,
        DecisionORM,
        TranscriptSegmentORM,
        AgentSessionORM,
        HostedAgentSessionORM,
        FeedRunORM,
        MeetingSummaryORM,
        RoomORM,
        MeetingInviteORM,
        MeetingSelectedTemplateORM,
    ):
        await db.execute(delete(model).where(model.meeting_id == meeting_id))

    await db.delete(meeting)
    await db.flush()


@router.post("/{meeting_id}/start", response_model=MeetingResponse)
async def start_meeting(
    meeting_id: UUID,
    current_user: CurrentUserOrAgent,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
    settings: Annotated[Settings, Depends(get_settings)],
    lk: Annotated[LiveKitService, Depends(get_livekit_service)],
) -> MeetingResponse:
    """Start a meeting and fire background warming for selected agents.

    Transitions the meeting to ``active``, publishes ``MeetingStarted``,
    and schedules one background ``_warm_agent_in_background`` task per
    row in ``meeting_selected_templates``. Activation is decoupled from
    the HTTP response — the caller returns immediately and the frontend
    flips each agent's in-room spinner via ``AgentSessionWarmed`` /
    ``AgentSessionFailed`` events.

    Args:
        meeting_id: The UUID of the meeting to start.
        current_user: Authenticated user.
        db: Database session.
        publisher: Event publisher for Redis Streams.
        settings: Application settings (for background DB session factory
            and Anthropic API key).

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

    # Provision (or look up) a LiveKit room for this meeting. If LiveKit is
    # not configured (local dev) skip gracefully so the rest of the start
    # flow still works.
    if settings.livekit_url:
        room_result = await db.execute(select(RoomORM).where(RoomORM.meeting_id == meeting_id))
        room = room_result.scalar_one_or_none()
        if room is None:
            room = RoomORM(
                name=f"meeting-{meeting_id}",
                meeting_id=meeting_id,
                status="active",
            )
            db.add(room)
            await db.flush()
            await db.refresh(room)
        sid = await lk.ensure_room(room.name)
        room.livekit_room_id = sid
        await db.flush()
    else:
        logger.debug(
            "LiveKit not configured (livekit_url empty) — skipping room provisioning "
            "for meeting %s",
            meeting_id,
        )

    # Load selections for this meeting (source of truth for which agents warm)
    sel_result = await db.execute(
        select(MeetingSelectedTemplateORM).where(
            MeetingSelectedTemplateORM.meeting_id == meeting_id
        )
    )
    selections = sel_result.scalars().all()

    # Commit the ACTIVE transition + selections snapshot so the background
    # tasks see the new row state through their own fresh sessions.
    await db.commit()

    # Fire one background warm per selected template. Keyed (meeting_id,
    # template_id) for idempotency — if a task is already in flight we
    # leave it alone rather than racing a second activation.
    if not selections:
        logger.info(
            "No templates selected for meeting %s — skipping background warm "
            "(PresenceReconciler will backfill if templates are added later)",
            meeting_id,
        )
    db_factory = _build_session_factory(settings)
    for sel in selections:
        key = (meeting_id, sel.template_id)
        existing = _warming_tasks.get(key)
        if existing is not None and not existing.done():
            logger.info(
                "Skipping duplicate warm for template %s in meeting %s (already in flight)",
                sel.template_id,
                meeting_id,
            )
            continue
        task = asyncio.create_task(
            _warm_agent_in_background(
                db_factory,
                settings,
                current_user.id,
                sel.template_id,
                meeting_id,
                sel.system_prompt_override,
                sel.sop_id,
                publisher,
            )
        )
        _warming_tasks[key] = task

    await publisher.publish(MeetingStarted(meeting_id=meeting_id))

    return _to_response(meeting)


# ---------------------------------------------------------------------------
# Selected agent template endpoints
# ---------------------------------------------------------------------------


class SelectedTemplateItem(BaseModel):
    """One agent template selected to join a meeting.

    Attributes:
        template_id: Agent template UUID.
        system_prompt_override: Optional system prompt override.
        sop_id: Optional organization SOP to prepend.
    """

    template_id: UUID
    system_prompt_override: str | None = None
    sop_id: UUID | None = None


class SelectedAgentsRequest(BaseModel):
    """PUT body for replacing a meeting's selected agents.

    Attributes:
        selections: The complete new list of selected templates. Any rows
            not present are deleted.
    """

    selections: list[SelectedTemplateItem] = Field(default_factory=list)


class SelectedAgentsResponse(BaseModel):
    """Response returning the current selection for a meeting."""

    meeting_id: UUID
    selections: list[SelectedTemplateItem]


async def _assert_meeting_accessible(
    db: AsyncSession, meeting_id: UUID, user: UserORM
) -> MeetingORM:
    """Look up a meeting and enforce that the user can see it.

    Accepts the meeting if the user owns it, has an invite, or the
    meeting has no owner (legacy row).

    Args:
        db: Database session.
        meeting_id: Meeting UUID.
        user: Authenticated user.

    Returns:
        The meeting row.

    Raises:
        HTTPException: 404 if missing or not accessible to the user.
    """
    invite_exists = exists(
        select(MeetingInviteORM.id).where(
            MeetingInviteORM.meeting_id == meeting_id,
            MeetingInviteORM.user_id == user.id,
        )
    )
    result = await db.execute(
        select(MeetingORM).where(
            MeetingORM.id == meeting_id,
            or_(
                MeetingORM.owner_id == user.id,
                MeetingORM.owner_id.is_(None),
                invite_exists,
            ),
        )
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )
    return meeting


@router.put("/{meeting_id}/selected-agents", response_model=SelectedAgentsResponse)
async def set_selected_agents(
    meeting_id: UUID,
    body: SelectedAgentsRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SelectedAgentsResponse:
    """Replace the agent templates selected to join this meeting.

    The full selection set is replaced on each PUT — rows not present in
    the body are deleted. Each template is tier-checked against the
    caller so users can't smuggle in templates above their plan.

    Args:
        meeting_id: Meeting UUID.
        body: The new selection set.
        current_user: Authenticated user (must own or be invited to the meeting).
        db: Database session.

    Returns:
        The newly-persisted selection.

    Raises:
        HTTPException: 402/403 if the user lacks the plan tier for any
            referenced template, 404 if the meeting is missing, or 404 if
            any referenced template does not exist.
    """
    require_tier(current_user, MANAGED_AGENT_MIN_TIER)
    await _assert_meeting_accessible(db, meeting_id, current_user)

    # Validate every template exists + enforce its tier requirement
    template_ids = [s.template_id for s in body.selections]
    if template_ids:
        tmpl_result = await db.execute(
            select(AgentTemplateORM).where(AgentTemplateORM.id.in_(template_ids))
        )
        templates_by_id = {t.id: t for t in tmpl_result.scalars().all()}
        missing = [str(tid) for tid in template_ids if tid not in templates_by_id]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template(s) not found: {', '.join(missing)}",
            )
        for sel in body.selections:
            template = templates_by_id[sel.template_id]
            require_tier(current_user, template.tier)
            if sel.sop_id is not None:
                require_tier(current_user, "business")

    # Replace the selection set atomically
    await db.execute(
        delete(MeetingSelectedTemplateORM).where(
            MeetingSelectedTemplateORM.meeting_id == meeting_id
        )
    )
    for sel in body.selections:
        db.add(
            MeetingSelectedTemplateORM(
                meeting_id=meeting_id,
                template_id=sel.template_id,
                system_prompt_override=sel.system_prompt_override,
                sop_id=sel.sop_id,
            )
        )
    await db.flush()
    # Commit immediately so that a concurrent POST /start sees these rows.
    # Without this, the implicit commit (via get_db_session teardown) runs
    # after the HTTP response is sent; with sub-ms intra-cluster latency the
    # next request can query MeetingSelectedTemplateORM before the transaction
    # commits and see 0 rows, silently skipping agent warming.
    await db.commit()

    return SelectedAgentsResponse(
        meeting_id=meeting_id,
        selections=[
            SelectedTemplateItem(
                template_id=sel.template_id,
                system_prompt_override=sel.system_prompt_override,
                sop_id=sel.sop_id,
            )
            for sel in body.selections
        ],
    )


@router.get("/{meeting_id}/selected-agents", response_model=SelectedAgentsResponse)
async def get_selected_agents(
    meeting_id: UUID,
    current_user: CurrentUserOrAgent,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> SelectedAgentsResponse:
    """Return the agent templates currently selected for this meeting.

    Args:
        meeting_id: Meeting UUID.
        current_user: Authenticated user or agent.
        db: Database session.

    Returns:
        The current selection (possibly empty).

    Raises:
        HTTPException: 404 if the meeting is missing or not accessible.
    """
    await _assert_meeting_accessible(db, meeting_id, current_user)

    result = await db.execute(
        select(MeetingSelectedTemplateORM)
        .where(MeetingSelectedTemplateORM.meeting_id == meeting_id)
        .order_by(MeetingSelectedTemplateORM.created_at)
    )
    rows = result.scalars().all()
    return SelectedAgentsResponse(
        meeting_id=meeting_id,
        selections=[
            SelectedTemplateItem(
                template_id=row.template_id,
                system_prompt_override=row.system_prompt_override,
                sop_id=row.sop_id,
            )
            for row in rows
        ],
    )


# ---------------------------------------------------------------------------
# LiveKit participant token
# ---------------------------------------------------------------------------


class LiveKitTokenResponse(BaseModel):
    """Response payload for the LiveKit participant token endpoint.

    Attributes:
        token: Short-lived participant JWT signed with the LiveKit API secret.
        url: The LiveKit server URL the client should connect to.
        room_name: The LiveKit room name (matches ``rooms.name``).
    """

    token: str
    url: str
    room_name: str


@router.post("/{meeting_id}/livekit-token", response_model=LiveKitTokenResponse)
async def issue_livekit_token(
    meeting_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    lk: Annotated[LiveKitService, Depends(get_livekit_service)],
) -> LiveKitTokenResponse:
    """Issue a LiveKit participant JWT for the authenticated user.

    The meeting must be accessible to the caller (owner or invitee) and a
    LiveKit room must already be provisioned for the meeting (normally via
    ``POST /meetings/{id}/start``).

    Args:
        meeting_id: Meeting UUID.
        current_user: Authenticated user (must own or be invited).
        db: Database session.
        settings: Application settings (for the LiveKit server URL).
        lk: LiveKit service dependency for token generation.

    Returns:
        ``{token, url, room_name}`` ready for a LiveKit SDK connect call.

    Raises:
        HTTPException: 404 if the meeting is missing or not accessible,
            409 if no room has been provisioned for the meeting yet.
    """
    await _assert_meeting_accessible(db, meeting_id, current_user)

    room_result = await db.execute(select(RoomORM).where(RoomORM.meeting_id == meeting_id))
    room = room_result.scalar_one_or_none()
    if room is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room not provisioned — call /start first",
        )

    user_name = current_user.name or current_user.email
    token = lk.generate_participant_token(
        user_id=current_user.id,
        user_name=user_name,
        room_name=room.name,
    )
    return LiveKitTokenResponse(
        token=token,
        url=settings.livekit_url,
        room_name=room.name,
    )


# ---------------------------------------------------------------------------
# Per-meeting agent session state + retry
# ---------------------------------------------------------------------------


class AgentSessionInfo(BaseModel):
    """Per-selected-template warming state.

    Matches the frontend ``AgentSessionInfo`` type in
    ``web/src/types/index.ts`` — one entry per ``meeting_selected_templates``
    row, with state derived from the latest ``HostedAgentSessionORM`` row
    (if any) for the (meeting_id, template_id) pair.

    Attributes:
        template_id: Template UUID.
        template_name: Human-readable template name for the in-room spinner.
        state: One of ``warming``, ``ready``, ``failed``, ``stopped``.
        hosted_session_id: Latest hosted session row ID (if any).
        error: Failure reason when state is ``failed``.
    """

    template_id: UUID
    template_name: str
    state: str
    hosted_session_id: UUID | None = None
    error: str | None = None


class AgentSessionsResponse(BaseModel):
    """List of per-template warming states for a meeting."""

    meeting_id: UUID
    sessions: list[AgentSessionInfo]


def _derive_session_state(session: HostedAgentSessionORM | None, in_flight: bool) -> str:
    """Map DB+in-memory state to a frontend ``AgentWarmingState``.

    Precedence:
      1. In-flight background warm task → ``warming``.
      2. No session row → ``warming`` (selection exists but warm hasn't
         started yet, e.g. before ``POST /start``).
      3. ``status == "failed"`` → ``failed``.
      4. ``status == "stopped"`` → ``stopped``.
      5. ``status == "active"`` and ``anthropic_session_id`` set → ``ready``.
      6. Anything else with ``status == "active"`` → ``warming``.
    """
    if in_flight:
        return "warming"
    if session is None:
        return "warming"
    if session.status == "failed":
        return "failed"
    if session.status == "stopped":
        return "stopped"
    if session.status == "active" and session.anthropic_session_id:
        return "ready"
    return "warming"


@router.get("/{meeting_id}/agent-sessions", response_model=AgentSessionsResponse)
async def list_agent_sessions(
    meeting_id: UUID,
    current_user: CurrentUserOrAgent,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentSessionsResponse:
    """Return per-template warming state for every selected agent.

    One entry per ``meeting_selected_templates`` row. For each template
    the latest ``HostedAgentSessionORM`` row (by ``started_at`` desc) is
    consulted and combined with the in-memory ``_warming_tasks`` map to
    derive the frontend's ``AgentWarmingState``.

    Args:
        meeting_id: Meeting UUID.
        current_user: Authenticated user or agent (must own or be invited).
        db: Database session.

    Returns:
        One ``AgentSessionInfo`` per selected template.

    Raises:
        HTTPException: 404 if the meeting is missing or not accessible.
    """
    await _assert_meeting_accessible(db, meeting_id, current_user)

    sel_result = await db.execute(
        select(MeetingSelectedTemplateORM, AgentTemplateORM)
        .join(
            AgentTemplateORM,
            AgentTemplateORM.id == MeetingSelectedTemplateORM.template_id,
        )
        .where(MeetingSelectedTemplateORM.meeting_id == meeting_id)
        .order_by(MeetingSelectedTemplateORM.created_at)
    )
    pairs = sel_result.all()

    sessions: list[AgentSessionInfo] = []
    for _sel, template in pairs:
        latest_result = await db.execute(
            select(HostedAgentSessionORM)
            .where(
                HostedAgentSessionORM.meeting_id == meeting_id,
                HostedAgentSessionORM.template_id == template.id,
            )
            .order_by(HostedAgentSessionORM.started_at.desc())
            .limit(1)
        )
        latest = latest_result.scalar_one_or_none()

        task = _warming_tasks.get((meeting_id, template.id))
        in_flight = task is not None and not task.done()

        state = _derive_session_state(latest, in_flight)
        sessions.append(
            AgentSessionInfo(
                template_id=template.id,
                template_name=template.name,
                state=state,
                hosted_session_id=latest.id if latest is not None else None,
                error=latest.error_detail if latest is not None and state == "failed" else None,
            )
        )

    return AgentSessionsResponse(meeting_id=meeting_id, sessions=sessions)


@router.post(
    "/{meeting_id}/agent-sessions/{template_id}/retry",
    status_code=status.HTTP_202_ACCEPTED,
)
async def retry_agent_session(
    meeting_id: UUID,
    template_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Re-fire background warming for a single failed/stopped agent.

    Used by the frontend retry affordance on the per-agent spinner when
    its state flipped to ``failed``. Verifies the template is still
    selected for this meeting, enforces the template's tier, and schedules
    a fresh ``_warm_agent_in_background`` task. Returns 202 Accepted
    immediately — the frontend watches the ``agent.session.warmed`` /
    ``agent.session.failed`` events to update its spinner.

    Args:
        meeting_id: Meeting UUID.
        template_id: Template UUID to retry.
        current_user: Authenticated user (must own or be invited).
        db: Database session.
        publisher: Event publisher for the background task.
        settings: Application settings.

    Returns:
        ``{"status": "warming"}`` on successful schedule.

    Raises:
        HTTPException: 402/403 on tier, 404 if meeting/selection missing,
            409 if a warm is already in flight for this (meeting, template).
    """
    require_tier(current_user, MANAGED_AGENT_MIN_TIER)
    await _assert_meeting_accessible(db, meeting_id, current_user)

    sel_result = await db.execute(
        select(MeetingSelectedTemplateORM, AgentTemplateORM)
        .join(
            AgentTemplateORM,
            AgentTemplateORM.id == MeetingSelectedTemplateORM.template_id,
        )
        .where(
            MeetingSelectedTemplateORM.meeting_id == meeting_id,
            MeetingSelectedTemplateORM.template_id == template_id,
        )
    )
    row = sel_result.first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template is not selected for this meeting",
        )
    selection, template = row
    require_tier(current_user, template.tier)
    if selection.sop_id is not None:
        require_tier(current_user, "business")

    key = (meeting_id, template_id)
    existing = _warming_tasks.get(key)
    if existing is not None and not existing.done():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Warm already in flight for this template",
        )

    db_factory = _build_session_factory(settings)
    task = asyncio.create_task(
        _warm_agent_in_background(
            db_factory,
            settings,
            current_user.id,
            template_id,
            meeting_id,
            selection.system_prompt_override,
            selection.sop_id,
            publisher,
        )
    )
    _warming_tasks[key] = task

    return {"status": "warming"}


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
