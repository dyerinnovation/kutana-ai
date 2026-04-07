"""Turn management REST endpoints.

Thin REST layer over RedisTurnManager, allowing the CLI and other
HTTP clients to manage the speaker queue without a WebSocket connection.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID  # noqa: TC003 — runtime dep for FastAPI path params

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis  # noqa: TC002 — runtime dep for FastAPI DI

from api_server.auth_deps import CurrentUserOrAgent  # noqa: TC001 — runtime dep for FastAPI DI
from api_server.deps import get_redis
from kutana_providers.turn_management.redis_turn_manager import RedisTurnManager

router = APIRouter(prefix="/meetings/{meeting_id}/turns", tags=["turns"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RaiseHandRequest(BaseModel):
    """Request body for raising a hand.

    Attributes:
        priority: Queue priority — "normal" (FIFO) or "urgent" (front of queue).
        topic: Optional topic the participant wants to discuss.
    """

    priority: str = "normal"
    topic: str | None = None


class RaiseHandResponse(BaseModel):
    """Response after raising a hand.

    Attributes:
        queue_position: 1-based position in queue. 0 means immediately promoted.
        hand_raise_id: Unique ID assigned to this hand raise.
        was_promoted: True if immediately set as active speaker.
    """

    queue_position: int
    hand_raise_id: UUID
    was_promoted: bool


class QueueEntryResponse(BaseModel):
    """A single entry in the speaker queue.

    Attributes:
        participant_id: The participant waiting to speak.
        hand_raise_id: Unique hand raise event ID.
        priority: Queue priority level.
        topic: Optional discussion topic.
        raised_at: When the hand was raised (ISO 8601).
        position: 1-based queue position.
    """

    participant_id: UUID
    hand_raise_id: UUID
    priority: str
    topic: str | None = None
    raised_at: str
    position: int


class QueueStatusResponse(BaseModel):
    """Snapshot of the speaker queue.

    Attributes:
        meeting_id: The meeting this status belongs to.
        active_speaker_id: Current active speaker, or None.
        queue: Ordered list of participants waiting to speak.
    """

    meeting_id: UUID
    active_speaker_id: UUID | None = None
    queue: list[QueueEntryResponse] = Field(default_factory=list)


class FinishTurnResponse(BaseModel):
    """Response after finishing a speaking turn.

    Attributes:
        status: "finished" or "not_speaker".
        next_speaker_id: UUID of the next speaker, or None if queue is empty.
    """

    status: str
    next_speaker_id: UUID | None = None


class CancelHandResponse(BaseModel):
    """Response after cancelling a hand raise.

    Attributes:
        cancelled: True if a hand raise was removed.
    """

    cancelled: bool


# ---------------------------------------------------------------------------
# Dependency: build a RedisTurnManager from the Redis URL
# ---------------------------------------------------------------------------


async def _get_turn_manager(
    redis_client: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
) -> RedisTurnManager:
    """Build a RedisTurnManager sharing the request-scoped Redis URL.

    Args:
        redis_client: Redis client from dependency injection.

    Returns:
        A RedisTurnManager instance.
    """
    # Extract the connection URL from the client's connection pool
    url = redis_client.connection_pool.connection_kwargs.get("url")
    if url:
        return RedisTurnManager(redis_url=url)
    # Reconstruct URL from pool kwargs
    kwargs = redis_client.connection_pool.connection_kwargs
    host = kwargs.get("host", "localhost")
    port = kwargs.get("port", 6379)
    db = kwargs.get("db", 0)
    return RedisTurnManager(redis_url=f"redis://{host}:{port}/{db}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/raise", response_model=RaiseHandResponse, status_code=201)
async def raise_hand(
    meeting_id: UUID,
    body: RaiseHandRequest,
    current_user: CurrentUserOrAgent,
    turn_mgr: Annotated[RedisTurnManager, Depends(_get_turn_manager)],
) -> RaiseHandResponse:
    """Raise a hand to request a speaking turn.

    Args:
        meeting_id: The meeting UUID.
        body: Priority and optional topic.
        current_user: Authenticated user (used as participant ID).
        turn_mgr: Turn manager instance.

    Returns:
        RaiseHandResponse with queue position and hand raise ID.
    """
    try:
        result = await turn_mgr.raise_hand(
            meeting_id=meeting_id,
            participant_id=current_user.id,
            priority=body.priority,
            topic=body.topic,
        )
        return RaiseHandResponse(
            queue_position=result.queue_position,
            hand_raise_id=result.hand_raise_id,
            was_promoted=result.was_promoted,
        )
    finally:
        await turn_mgr.close()


@router.get("/status", response_model=QueueStatusResponse)
async def get_queue_status(
    meeting_id: UUID,
    _current_user: CurrentUserOrAgent,
    turn_mgr: Annotated[RedisTurnManager, Depends(_get_turn_manager)],
) -> QueueStatusResponse:
    """Get the current speaker queue for a meeting.

    Args:
        meeting_id: The meeting UUID.
        _current_user: Authenticated user (required for access).
        turn_mgr: Turn manager instance.

    Returns:
        QueueStatusResponse with active speaker and queue entries.
    """
    try:
        queue_status = await turn_mgr.get_queue_status(meeting_id)
        return QueueStatusResponse(
            meeting_id=queue_status.meeting_id,
            active_speaker_id=queue_status.active_speaker_id,
            queue=[
                QueueEntryResponse(
                    participant_id=entry.participant_id,
                    hand_raise_id=entry.hand_raise_id,
                    priority=entry.priority.value,
                    topic=entry.topic,
                    raised_at=entry.raised_at.isoformat(),
                    position=entry.position,
                )
                for entry in queue_status.queue
            ],
        )
    finally:
        await turn_mgr.close()


@router.post("/finish", response_model=FinishTurnResponse)
async def finish_turn(
    meeting_id: UUID,
    current_user: CurrentUserOrAgent,
    turn_mgr: Annotated[RedisTurnManager, Depends(_get_turn_manager)],
) -> FinishTurnResponse:
    """Mark your speaking turn as finished and advance the queue.

    Args:
        meeting_id: The meeting UUID.
        current_user: Authenticated user (must be the active speaker).
        turn_mgr: Turn manager instance.

    Returns:
        FinishTurnResponse with status and optional next speaker ID.
    """
    try:
        next_speaker = await turn_mgr.mark_finished_speaking(
            meeting_id=meeting_id,
            participant_id=current_user.id,
        )
        if next_speaker is None:
            # Could be "not_speaker" or "done" — check if we were the speaker
            speaker = await turn_mgr.get_active_speaker(meeting_id)
            if speaker == current_user.id:
                return FinishTurnResponse(status="not_speaker")
            return FinishTurnResponse(status="finished", next_speaker_id=None)
        return FinishTurnResponse(status="finished", next_speaker_id=next_speaker)
    finally:
        await turn_mgr.close()


@router.post("/cancel", response_model=CancelHandResponse)
async def cancel_hand_raise(
    meeting_id: UUID,
    current_user: CurrentUserOrAgent,
    turn_mgr: Annotated[RedisTurnManager, Depends(_get_turn_manager)],
) -> CancelHandResponse:
    """Cancel your raised hand and remove yourself from the queue.

    Args:
        meeting_id: The meeting UUID.
        current_user: Authenticated user.
        turn_mgr: Turn manager instance.

    Returns:
        CancelHandResponse indicating whether a hand raise was removed.
    """
    try:
        removed = await turn_mgr.cancel_hand_raise(
            meeting_id=meeting_id,
            participant_id=current_user.id,
        )
        return CancelHandResponse(cancelled=removed)
    finally:
        await turn_mgr.close()
