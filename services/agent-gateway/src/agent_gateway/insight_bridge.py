"""Insight bridge for the agent gateway.

Subscribes to Redis Pub/Sub channels where the task-engine publishes
extracted entities (tasks, decisions, questions, etc.) and relays them
to WebSocket-connected participants as ``data.channel.insights.*`` events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

import redis.asyncio as aioredis

if TYPE_CHECKING:
    from agent_gateway.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

# Pattern matches all insight channels published by the task-engine:
#   meeting.{uuid}.insights
#   meeting.{uuid}.insights.task
#   meeting.{uuid}.insights.decision
#   etc.
_INSIGHT_PATTERN = "meeting.*.insights*"


class InsightBridge:
    """Bridges task-engine insight Pub/Sub and the gateway connection manager.

    Subscribes to ``meeting.*.insights*`` Redis Pub/Sub channels and
    broadcasts entities to sessions that have subscribed to the
    ``insights`` data channel.

    Attributes:
        manager: The gateway's ConnectionManager for session access.
    """

    def __init__(
        self,
        manager: ConnectionManager,
        redis_url: str = "redis://localhost:6379/0",
    ) -> None:
        """Initialise the insight bridge.

        Args:
            manager: The gateway connection manager.
            redis_url: Redis URL for the Pub/Sub subscriber connection.
        """
        self.manager = manager
        self._redis_url = redis_url
        self._pubsub_task: asyncio.Task[None] | None = None

    def start(self) -> None:
        """Start the Redis Pub/Sub subscriber for insight relay."""
        if self._pubsub_task is None or self._pubsub_task.done():
            self._pubsub_task = asyncio.create_task(
                self._pubsub_loop(),
                name="insight-bridge-pubsub",
            )
            logger.info("InsightBridge pub/sub subscriber started")

    async def stop(self) -> None:
        """Stop the pub/sub subscriber."""
        if self._pubsub_task and not self._pubsub_task.done():
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except asyncio.CancelledError:
                pass
        logger.info("InsightBridge stopped")

    async def _pubsub_loop(self) -> None:
        """Subscribe to Redis Pub/Sub and relay insight events to WS participants.

        Uses PSUBSCRIBE for pattern matching across per-meeting channels.
        """
        redis_client: aioredis.Redis = aioredis.from_url(  # type: ignore[type-arg]
            self._redis_url, decode_responses=True
        )
        pubsub = redis_client.pubsub()
        await pubsub.psubscribe(_INSIGHT_PATTERN)
        logger.info("InsightBridge subscribed to Redis pattern: %s", _INSIGHT_PATTERN)

        try:
            async for raw_msg in pubsub.listen():
                if raw_msg["type"] != "pmessage":
                    continue
                try:
                    channel: str = raw_msg["channel"]
                    data: dict[str, Any] = json.loads(raw_msg["data"])

                    # Extract meeting_id from channel name:
                    # "meeting.{uuid}.insights" or "meeting.{uuid}.insights.task"
                    parts = channel.split(".")
                    if len(parts) < 3:
                        continue
                    meeting_id = UUID(parts[1])

                    # Determine the data channel event type:
                    # "meeting.{uuid}.insights" → "data.channel.insights"
                    # "meeting.{uuid}.insights.task" → "data.channel.insights.task"
                    suffix = ".".join(parts[2:])
                    event_type = f"data.channel.{suffix}"

                    await self._broadcast_insight(meeting_id, event_type, data)
                except (KeyError, ValueError, json.JSONDecodeError) as exc:
                    logger.warning("Malformed insight pub/sub message: %s", exc)
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Unexpected error in insight pub/sub loop")
        finally:
            await pubsub.punsubscribe(_INSIGHT_PATTERN)
            await redis_client.aclose()
            logger.debug("InsightBridge pub/sub subscriber closed")

    async def _broadcast_insight(
        self,
        meeting_id: UUID,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Broadcast an insight event to all subscribed sessions in the meeting.

        Args:
            meeting_id: The meeting to broadcast to.
            event_type: The data.channel.insights.* event type.
            payload: The insight payload (entities list).
        """
        sessions = self.manager.get_meeting_sessions(meeting_id)
        delivered = 0
        for session in sessions:
            subscribed = getattr(session, "subscribed_channels", None)
            if subscribed and not any(
                event_type.startswith(f"data.channel.{ch}") for ch in subscribed
            ):
                continue
            try:
                await session.send_event(event_type, payload)
                delivered += 1
            except Exception:
                logger.warning(
                    "Failed to send insight event to session %s",
                    session.session_id,
                )
        if delivered:
            logger.info(
                "Insight broadcast: meeting=%s type=%s delivered=%d",
                meeting_id,
                event_type,
                delivered,
            )
