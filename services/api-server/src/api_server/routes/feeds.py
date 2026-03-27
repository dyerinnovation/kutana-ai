"""Feed CRUD and trigger endpoints."""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession

from api_server.auth_deps import CurrentUser  # noqa: TC001 — runtime dep for FastAPI DI
from api_server.deps import get_db_session, get_event_publisher
from api_server.encryption import encrypt_value
from api_server.event_publisher import EventPublisher  # noqa: TC001 — runtime dep for FastAPI DI
from convene_core.database.models import FeedORM, FeedRunORM, FeedSecretORM
from convene_core.events.definitions import FeedCreated, FeedDeleted, FeedUpdated
from convene_core.models.feed import FeedCreate, FeedRead, FeedRunRead, FeedUpdate

router = APIRouter(prefix="/feeds", tags=["feeds"])

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Response wrappers
# ---------------------------------------------------------------------------


class FeedListResponse(BaseModel):
    """Paginated list of feeds.

    Attributes:
        items: List of feed response objects.
        total: Total number of feeds.
    """

    items: list[FeedRead]
    total: int = Field(ge=0)


class FeedRunListResponse(BaseModel):
    """Paginated list of feed runs.

    Attributes:
        items: List of feed run response objects.
        total: Total number of runs.
    """

    items: list[FeedRunRead]
    total: int = Field(ge=0)


class FeedTriggerRequest(BaseModel):
    """Request body for manually triggering a feed.

    Attributes:
        meeting_id: Meeting to trigger the feed for.
    """

    meeting_id: UUID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _orm_to_read(feed: FeedORM) -> FeedRead:
    """Convert a FeedORM row to a FeedRead response model.

    Args:
        feed: The ORM feed row.

    Returns:
        A FeedRead pydantic model.
    """
    token_hint: str | None = None
    if feed.secret is not None:
        token_hint = feed.secret.token_hint

    return FeedRead(
        id=feed.id,
        user_id=feed.user_id,
        name=feed.name,
        platform=feed.platform,
        direction=feed.direction,
        delivery_type=feed.delivery_type,
        mcp_server_url=feed.mcp_server_url,
        channel_name=feed.channel_name,
        data_types=feed.data_types,
        context_types=feed.context_types,
        trigger=feed.trigger,
        meeting_tag=feed.meeting_tag,
        is_active=feed.is_active,
        created_at=feed.created_at,
        last_triggered_at=feed.last_triggered_at,
        last_error=feed.last_error,
        token_hint=token_hint,
    )


def _run_orm_to_read(run: FeedRunORM) -> FeedRunRead:
    """Convert a FeedRunORM row to a FeedRunRead response model.

    Args:
        run: The ORM feed run row.

    Returns:
        A FeedRunRead pydantic model.
    """
    return FeedRunRead(
        id=run.id,
        feed_id=run.feed_id,
        meeting_id=run.meeting_id,
        trigger=run.trigger,
        direction=run.direction,
        status=run.status,
        agent_session_id=run.agent_session_id,
        started_at=run.started_at,
        finished_at=run.finished_at,
        error=run.error,
    )


async def _get_user_feed(
    feed_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> FeedORM:
    """Fetch a feed owned by the given user or raise 404.

    Args:
        feed_id: The feed UUID to look up.
        user_id: The authenticated user's UUID.
        db: Async database session.

    Returns:
        The FeedORM row.

    Raises:
        HTTPException: 404 if not found or not owned by user.
    """
    result = await db.execute(
        select(FeedORM).where(FeedORM.id == feed_id, FeedORM.user_id == user_id)
    )
    feed = result.scalar_one_or_none()
    if feed is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Feed not found",
        )
    return feed


async def _safe_publish(
    publisher: EventPublisher,
    event: FeedCreated | FeedUpdated | FeedDeleted,
) -> None:
    """Publish an event, swallowing errors to avoid breaking the HTTP response.

    Args:
        publisher: The event publisher to use.
        event: The domain event to publish.
    """
    try:
        await publisher.publish(event)
    except Exception:
        logger.exception(
            "Failed to publish %s — continuing without event",
            event.event_type,
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=FeedListResponse)
async def list_feeds(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FeedListResponse:
    """List all feeds for the current user.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        FeedListResponse with feed data.
    """
    result = await db.execute(
        select(FeedORM)
        .where(FeedORM.user_id == current_user.id)
        .order_by(FeedORM.created_at.desc())
    )
    feeds = result.scalars().all()
    return FeedListResponse(
        items=[_orm_to_read(f) for f in feeds],
        total=len(feeds),
    )


@router.post("", response_model=FeedRead, status_code=201)
async def create_feed(
    body: FeedCreate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
) -> FeedRead:
    """Create a new feed configuration.

    Args:
        body: The feed creation payload.
        current_user: Authenticated user.
        db: Database session.
        publisher: Redis event publisher.

    Returns:
        FeedRead with the newly created feed.
    """
    feed = FeedORM(
        id=uuid4(),
        user_id=current_user.id,
        name=body.name,
        platform=body.platform,
        direction=body.direction,
        delivery_type=body.delivery_type,
        mcp_server_url=body.mcp_server_url,
        channel_name=body.channel_name,
        data_types=body.data_types,
        context_types=body.context_types,
        trigger=body.trigger,
        meeting_tag=body.meeting_tag,
    )
    db.add(feed)
    await db.flush()

    # Store encrypted token if provided
    if body.mcp_auth_token:
        secret = FeedSecretORM(
            id=uuid4(),
            feed_id=feed.id,
            encrypted_token=encrypt_value(body.mcp_auth_token),
            token_hint=body.mcp_auth_token[-4:],
        )
        db.add(secret)
        await db.flush()

    # Refresh to pick up the secret relationship
    await db.refresh(feed)

    await _safe_publish(
        publisher,
        FeedCreated(
            feed_id=feed.id,
            user_id=current_user.id,
            platform=body.platform,
            direction=body.direction,
        ),
    )

    return _orm_to_read(feed)


@router.get("/{feed_id}", response_model=FeedRead)
async def get_feed(
    feed_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> FeedRead:
    """Get a single feed by ID.

    Args:
        feed_id: The UUID of the feed to retrieve.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        FeedRead for the requested feed.

    Raises:
        HTTPException: 404 if feed not found.
    """
    feed = await _get_user_feed(feed_id, current_user.id, db)
    return _orm_to_read(feed)


@router.patch("/{feed_id}", response_model=FeedRead)
async def update_feed(
    feed_id: UUID,
    body: FeedUpdate,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
) -> FeedRead:
    """Update an existing feed configuration.

    Args:
        feed_id: The UUID of the feed to update.
        body: The update payload (partial).
        current_user: Authenticated user.
        db: Database session.
        publisher: Redis event publisher.

    Returns:
        FeedRead reflecting the updated feed.

    Raises:
        HTTPException: 404 if feed not found.
    """
    feed = await _get_user_feed(feed_id, current_user.id, db)

    update_data = body.model_dump(exclude_unset=True, exclude={"mcp_auth_token"})
    for field_name, value in update_data.items():
        setattr(feed, field_name, value)

    # Update token if provided
    if body.mcp_auth_token is not None:
        if feed.secret is not None:
            feed.secret.encrypted_token = encrypt_value(body.mcp_auth_token)
            feed.secret.token_hint = body.mcp_auth_token[-4:]
        else:
            secret = FeedSecretORM(
                id=uuid4(),
                feed_id=feed.id,
                encrypted_token=encrypt_value(body.mcp_auth_token),
                token_hint=body.mcp_auth_token[-4:],
            )
            db.add(secret)

    await db.flush()
    await db.refresh(feed)

    await _safe_publish(
        publisher,
        FeedUpdated(feed_id=feed.id, user_id=current_user.id),
    )

    return _orm_to_read(feed)


@router.delete("/{feed_id}", status_code=204)
async def delete_feed(
    feed_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
) -> None:
    """Delete a feed configuration and its secrets.

    Args:
        feed_id: The UUID of the feed to delete.
        current_user: Authenticated user.
        db: Database session.
        publisher: Redis event publisher.

    Raises:
        HTTPException: 404 if feed not found.
    """
    feed = await _get_user_feed(feed_id, current_user.id, db)

    # Hard-delete secret first (per design doc S9)
    if feed.secret is not None:
        await db.delete(feed.secret)

    # Delete associated runs
    runs_result = await db.execute(select(FeedRunORM).where(FeedRunORM.feed_id == feed.id))
    for run in runs_result.scalars().all():
        await db.delete(run)

    await db.delete(feed)
    await db.flush()

    await _safe_publish(
        publisher,
        FeedDeleted(feed_id=feed_id, user_id=current_user.id),
    )


@router.post("/{feed_id}/trigger", response_model=FeedRunRead, status_code=201)
async def trigger_feed(
    feed_id: UUID,
    body: FeedTriggerRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    publisher: Annotated[EventPublisher, Depends(get_event_publisher)],
) -> FeedRunRead:
    """Manually trigger a feed run for a specific meeting.

    Args:
        feed_id: The UUID of the feed to trigger.
        body: Contains the meeting_id to trigger for.
        current_user: Authenticated user.
        db: Database session.
        publisher: Redis event publisher.

    Returns:
        FeedRunRead for the created run.

    Raises:
        HTTPException: 404 if feed not found.
    """
    feed = await _get_user_feed(feed_id, current_user.id, db)

    direction = "outbound"
    if feed.direction in ("inbound", "bidirectional"):
        direction = "inbound"

    run = FeedRunORM(
        id=uuid4(),
        feed_id=feed.id,
        meeting_id=body.meeting_id,
        trigger="manual",
        direction=direction,
        status="pending",
    )
    db.add(run)
    await db.flush()

    # Publish a feed run event to Redis Streams for the worker to pick up
    from convene_core.events.definitions import FeedRunStarted

    await _safe_publish(
        publisher,
        FeedRunStarted(
            feed_run_id=run.id,
            feed_id=feed.id,
            meeting_id=body.meeting_id,
            direction=direction,
        ),
    )

    return _run_orm_to_read(run)


@router.get("/{feed_id}/runs", response_model=FeedRunListResponse)
async def list_feed_runs(
    feed_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    limit: int = 20,
) -> FeedRunListResponse:
    """List recent feed runs for a specific feed.

    Args:
        feed_id: The UUID of the feed.
        current_user: Authenticated user.
        db: Database session.
        limit: Maximum number of runs to return.

    Returns:
        FeedRunListResponse with run data.

    Raises:
        HTTPException: 404 if feed not found.
    """
    # Verify ownership
    await _get_user_feed(feed_id, current_user.id, db)

    result = await db.execute(
        select(FeedRunORM)
        .where(FeedRunORM.feed_id == feed_id)
        .order_by(FeedRunORM.started_at.desc())
        .limit(min(limit, 100))
    )
    runs = result.scalars().all()
    return FeedRunListResponse(
        items=[_run_orm_to_read(r) for r in runs],
        total=len(runs),
    )
