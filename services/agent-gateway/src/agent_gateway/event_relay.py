"""Redis Streams consumer that relays events to connected agents."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

import redis.asyncio as redis

if TYPE_CHECKING:
    from agent_gateway.connection_manager import ConnectionManager

logger = logging.getLogger(__name__)

STREAM_KEY = "convene:events"
GROUP_NAME = "agent-gateway"
CONSUMER_NAME = "gateway-0"


class EventRelay:
    """Consumes events from Redis Streams and forwards them to agents.

    Creates a consumer group on the convene:events stream and routes
    events to connected agent sessions based on meeting_id and
    capabilities.

    Attributes:
        _redis: Async Redis client.
        _manager: Connection manager for looking up sessions.
        _running: Whether the relay loop is active.
    """

    def __init__(
        self,
        redis_url: str,
        connection_manager: ConnectionManager,
    ) -> None:
        """Initialise the event relay.

        Args:
            redis_url: Redis connection URL.
            connection_manager: The gateway connection manager.
        """
        self._redis: redis.Redis[str] = redis.from_url(
            redis_url, decode_responses=True
        )
        self._manager = connection_manager
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """Start consuming events from Redis Streams."""
        # Ensure consumer group exists
        try:
            await self._redis.xgroup_create(
                STREAM_KEY, GROUP_NAME, id="0", mkstream=True
            )
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        self._running = True
        self._task = asyncio.create_task(self._consume_loop())
        logger.info("Event relay started (group=%s)", GROUP_NAME)

    async def stop(self) -> None:
        """Stop the event relay."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        await self._redis.aclose()
        logger.info("Event relay stopped")

    async def _consume_loop(self) -> None:
        """Main loop: read events and dispatch to agents."""
        while self._running:
            try:
                results = await self._redis.xreadgroup(
                    GROUP_NAME,
                    CONSUMER_NAME,
                    {STREAM_KEY: ">"},
                    count=10,
                    block=1000,
                )

                if not results:
                    continue

                for _stream_name, messages in results:
                    for msg_id, fields in messages:
                        await self._handle_event(msg_id, fields)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in event relay loop")
                await asyncio.sleep(1)

    async def _handle_event(
        self,
        msg_id: str,
        fields: dict[str, str],
    ) -> None:
        """Process a single event from the stream.

        Args:
            msg_id: Redis stream message ID.
            fields: Message fields (event_type, payload).
        """
        event_type = fields.get("event_type", "")
        payload_str = fields.get("payload", "{}")

        try:
            payload: dict[str, Any] = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.warning("Invalid JSON in event payload: %s", msg_id)
            await self._ack(msg_id)
            return

        # Extract meeting_id for routing
        meeting_id_str = payload.get("meeting_id")
        if meeting_id_str:
            try:
                meeting_id = UUID(meeting_id_str)
            except ValueError:
                meeting_id = None
        else:
            meeting_id = None

        # Route event to matching agent sessions
        if meeting_id is not None:
            sessions = self._manager.get_meeting_sessions(meeting_id)
            for session in sessions:
                subscribed = getattr(session, "subscribed_channels", None)
                if self._should_relay(event_type, session.capabilities, subscribed_channels=subscribed):
                    try:
                        if event_type == "transcript.segment.final":
                            segment = payload.get("segment", {})
                            await session.send_transcript(
                                meeting_id=meeting_id,
                                speaker_id=segment.get("speaker_id"),
                                text=segment.get("text", ""),
                                start_time=segment.get("start_time", 0.0),
                                end_time=segment.get("end_time", 0.0),
                                confidence=segment.get("confidence", 1.0),
                            )
                        else:
                            await session.send_event(event_type, payload)
                    except Exception:
                        logger.warning(
                            "Failed to relay event %s to session %s",
                            event_type,
                            session.session_id,
                        )

        # Acknowledge the message
        await self._ack(msg_id)

    @staticmethod
    def _should_relay(
        event_type: str,
        capabilities: list[str],
        *,
        subscribed_channels: set[str] | None = None,
    ) -> bool:
        """Determine if an event should be relayed based on capabilities.

        Args:
            event_type: The event type string.
            capabilities: Agent's granted capabilities.
            subscribed_channels: Optional set of data channels the agent subscribes to.

        Returns:
            True if the event should be relayed.
        """
        # Transcript events require listen or transcribe capability
        if event_type.startswith("transcript."):
            return "listen" in capabilities or "transcribe" in capabilities

        # Task events require extract_tasks capability
        if event_type.startswith("task."):
            return "extract_tasks" in capabilities

        # Data channel events — route based on channel subscriptions
        if event_type.startswith("data.channel."):
            if subscribed_channels is None:
                return True  # No filter = receive all
            channel = event_type.removeprefix("data.channel.")
            return channel in subscribed_channels or "*" in subscribed_channels

        # Meeting/room/participant events go to all agents
        if event_type.startswith(("meeting.", "room.", "participant.", "agent.")):
            return True

        # Default: relay to all
        return True

    async def _ack(self, msg_id: str) -> None:
        """Acknowledge a processed message.

        Args:
            msg_id: The Redis stream message ID.
        """
        try:
            await self._redis.xack(STREAM_KEY, GROUP_NAME, msg_id)
        except Exception:
            logger.warning("Failed to acknowledge message %s", msg_id)
