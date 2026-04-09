"""Meeting lifecycle wiring for Anthropic managed agent sessions.

Connects meeting events to Anthropic managed agent sessions:
- on_meeting_started: notifies active agents with meeting context
- TranscriptBatcher: batches transcript segments (30s windows) and pushes to agents
- on_meeting_ended: sends final summary request, closes sessions, records billing
- SessionEventProxy: streams Anthropic session events to Redis for frontend delivery
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import socket
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

import redis.asyncio as aioredis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from sqlalchemy import select

from api_server.managed_agents import end_session, send_message, stream_events
from kutana_core.database.models import (
    AgentTemplateORM,
    HostedAgentSessionORM,
    MeetingInviteORM,
    MeetingORM,
    UsageRecordORM,
    UserORM,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# Redis stream constants (shared with EventPublisher / task-engine)
STREAM_KEY = "kutana:events"
MAX_STREAM_LEN = 10_000
GROUP_NAME = "agent-lifecycle"
BLOCK_MS = 5_000
BATCH_SIZE = 10
_MAX_BACKOFF_SECONDS = 30

# Transcript batching window (seconds)
TRANSCRIPT_WINDOW_SECONDS = 30.0

# Anthropic event types we forward to the frontend
_PROXY_EVENT_TYPES = frozenset(
    {
        "agent.message",
        "agent.mcp_tool_use",
        "session.error",
        "session.status_idle",
        "span.model_request_end",
    }
)


# ---------------------------------------------------------------------------
# Meeting started handler
# ---------------------------------------------------------------------------


async def on_meeting_started(
    meeting_id: UUID,
    db: AsyncSession,
    api_key: str,
) -> None:
    """Notify all active hosted agent sessions that a meeting has started.

    For each active HostedAgentSession linked to this meeting, sends a
    user.message with meeting context (title, participants, agenda).

    Args:
        meeting_id: ID of the meeting that started.
        db: Async database session.
        api_key: Anthropic API key.
    """
    # Find active hosted sessions for this meeting
    result = await db.execute(
        select(HostedAgentSessionORM).where(
            HostedAgentSessionORM.meeting_id == meeting_id,
            HostedAgentSessionORM.status == "active",
            HostedAgentSessionORM.anthropic_session_id.is_not(None),
        )
    )
    sessions = result.scalars().all()

    if not sessions:
        logger.debug("No active hosted sessions for meeting %s", meeting_id)
        return

    # Fetch meeting context
    context = await _build_meeting_context(meeting_id, db)

    # Send context to each agent session
    for session in sessions:
        assert session.anthropic_session_id is not None
        try:
            await send_message(
                api_key,
                session.anthropic_session_id,
                context,
            )
            logger.info(
                "Sent meeting context to session %s (meeting %s)",
                session.id,
                meeting_id,
            )
        except Exception:
            logger.exception(
                "Failed to send meeting context to session %s",
                session.id,
            )


async def _build_meeting_context(meeting_id: UUID, db: AsyncSession) -> str:
    """Build a meeting context message for agent consumption.

    Args:
        meeting_id: ID of the meeting.
        db: Async database session.

    Returns:
        Formatted string with meeting title, participants, and agenda.
    """
    # Fetch meeting
    result = await db.execute(select(MeetingORM).where(MeetingORM.id == meeting_id))
    meeting = result.scalar_one_or_none()

    title = meeting.title or "Untitled Meeting" if meeting else "Unknown Meeting"

    # Fetch invited participants
    invite_result = await db.execute(
        select(UserORM.email, UserORM.name)
        .join(MeetingInviteORM, MeetingInviteORM.user_id == UserORM.id)
        .where(MeetingInviteORM.meeting_id == meeting_id)
    )
    participants = invite_result.all()
    participant_lines = "\n".join(f"- {row.name or row.email}" for row in participants)

    return (
        f"## Meeting Started: {title}\n\n"
        f"**Meeting ID:** {meeting_id}\n"
        f"**Started at:** {datetime.now(tz=UTC).isoformat()}\n\n"
        f"### Participants\n{participant_lines or '(none yet)'}\n\n"
        "The meeting is now live. Listen for transcript segments and "
        "participate according to your role."
    )


# ---------------------------------------------------------------------------
# Meeting ended handler
# ---------------------------------------------------------------------------


async def on_meeting_ended(
    meeting_id: UUID,
    db: AsyncSession,
    api_key: str,
) -> None:
    """Handle meeting end: request summaries, close sessions, record billing.

    For each active HostedAgentSession:
    1. Send a final summary request
    2. Wait for session.status_idle (with timeout)
    3. End the Anthropic session
    4. Update DB: set ended_at, status=stopped
    5. Record usage in UsageRecordORM

    Args:
        meeting_id: ID of the meeting that ended.
        db: Async database session.
        api_key: Anthropic API key.
    """
    result = await db.execute(
        select(HostedAgentSessionORM).where(
            HostedAgentSessionORM.meeting_id == meeting_id,
            HostedAgentSessionORM.status == "active",
        )
    )
    sessions = result.scalars().all()

    if not sessions:
        logger.debug("No active hosted sessions to close for meeting %s", meeting_id)
        return

    for session in sessions:
        await _close_session(session, db, api_key)

    await db.flush()
    logger.info(
        "Closed %d hosted agent session(s) for meeting %s",
        len(sessions),
        meeting_id,
    )


async def _close_session(
    session: HostedAgentSessionORM,
    db: AsyncSession,
    api_key: str,
) -> None:
    """Close a single hosted agent session with summary request and billing.

    Args:
        session: The hosted agent session to close.
        db: Async database session.
        api_key: Anthropic API key.
    """
    now = datetime.now(tz=UTC)

    if session.anthropic_session_id:
        # Send final summary request
        try:
            await send_message(
                api_key,
                session.anthropic_session_id,
                "The meeting has ended. Please provide a brief summary of key "
                "points, action items, and decisions made during this meeting.",
            )
        except Exception:
            logger.exception(
                "Failed to send summary request to session %s",
                session.id,
            )

        # Wait for the agent to finish processing (with timeout)
        try:
            await _wait_for_idle(api_key, session.anthropic_session_id, timeout=30.0)
        except TimeoutError:
            logger.warning(
                "Timeout waiting for session %s to become idle",
                session.id,
            )

        # End the Anthropic session
        try:
            await end_session(api_key, session.anthropic_session_id)
        except Exception:
            logger.exception(
                "Failed to end Anthropic session %s",
                session.anthropic_session_id,
            )

    # Update DB
    session.status = "stopped"
    session.ended_at = now

    # Record billing usage
    await _record_usage(session, db, now)


async def _wait_for_idle(
    api_key: str,
    session_id: str,
    timeout: float = 30.0,
) -> None:
    """Wait for an Anthropic session to reach idle status.

    Streams events until session.status_idle is received or timeout expires.

    Args:
        api_key: Anthropic API key.
        session_id: Anthropic session ID.
        timeout: Maximum seconds to wait.

    Raises:
        TimeoutError: If idle not reached within timeout.
    """

    async def _watch() -> None:
        async for event in stream_events(api_key, session_id):
            event_type = getattr(event, "type", None)
            if event_type == "session.status_idle":
                return

    try:
        await asyncio.wait_for(_watch(), timeout=timeout)
    except TimeoutError as exc:
        raise TimeoutError(f"Session {session_id} did not idle within {timeout}s") from exc


async def _record_usage(
    session: HostedAgentSessionORM,
    db: AsyncSession,
    ended_at: datetime,
) -> None:
    """Record session-hours billing usage for a closed session.

    Args:
        session: The hosted agent session with started_at and ended_at set.
        db: Async database session.
        ended_at: When the session ended.
    """
    duration = ended_at - session.started_at
    duration_seconds = max(int(duration.total_seconds()), 1)
    billing_period = ended_at.strftime("%Y-%m")

    usage = UsageRecordORM(
        user_id=session.user_id,
        resource_type="managed_agent",
        resource_id=session.id,
        started_at=session.started_at,
        ended_at=ended_at,
        duration_seconds=duration_seconds,
        billing_period=billing_period,
    )
    db.add(usage)
    logger.info(
        "Recorded usage for session %s: %d seconds (period %s)",
        session.id,
        duration_seconds,
        billing_period,
    )


# ---------------------------------------------------------------------------
# Session event proxy (Anthropic → Redis → frontend)
# ---------------------------------------------------------------------------


class SessionEventProxy:
    """Streams events from an Anthropic session and publishes them to Redis.

    The agent-gateway EventRelay picks these up from the kutana:events
    stream and forwards them to all WebSocket clients in the meeting room.

    Each proxy runs as a background asyncio task for one Anthropic session.

    Attributes:
        _api_key: Anthropic API key.
        _session_id: Anthropic session ID.
        _meeting_id: Meeting this session belongs to.
        _agent_name: Agent display name for event payloads.
        _redis: Async Redis client for publishing.
    """

    def __init__(
        self,
        api_key: str,
        anthropic_session_id: str,
        meeting_id: UUID,
        agent_name: str,
        redis_client: aioredis.Redis[str],
    ) -> None:
        """Initialise the event proxy.

        Args:
            api_key: Anthropic API key.
            anthropic_session_id: Anthropic session ID to stream from.
            meeting_id: Meeting UUID for event routing.
            agent_name: Agent display name.
            redis_client: Live Redis client for publishing events.
        """
        self._api_key = api_key
        self._session_id = anthropic_session_id
        self._meeting_id = meeting_id
        self._agent_name = agent_name
        self._redis = redis_client
        self._token_usage: dict[str, int] = {"input_tokens": 0, "output_tokens": 0}

    async def run(self) -> None:
        """Stream Anthropic session events and publish to Redis.

        Runs until the stream ends, the session closes, or the task
        is cancelled. Reconnects on transient errors.
        """
        backoff = 1.0
        while True:
            try:
                async for event in stream_events(self._api_key, self._session_id):
                    await self._handle_event(event)
                # Stream ended normally (session closed)
                logger.info(
                    "Event proxy for session %s ended (stream closed)",
                    self._session_id,
                )
                return
            except asyncio.CancelledError:
                logger.info("Event proxy for session %s cancelled", self._session_id)
                raise
            except Exception:
                logger.exception(
                    "Event proxy error for session %s — retrying in %.0fs",
                    self._session_id,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)

    async def _handle_event(self, event: Any) -> None:
        """Process a single Anthropic SSE event.

        Filters for relevant event types and publishes them to the
        kutana:events Redis stream with meeting_id for routing.

        Args:
            event: Anthropic SSE event object.
        """
        event_type = getattr(event, "type", None)
        if not event_type:
            return

        # Track token usage from model requests
        if event_type == "span.model_request_end":
            usage = getattr(event, "usage", None)
            if usage:
                self._token_usage["input_tokens"] += getattr(usage, "input_tokens", 0)
                self._token_usage["output_tokens"] += getattr(usage, "output_tokens", 0)
            # Don't forward billing spans to frontend
            return

        if event_type not in _PROXY_EVENT_TYPES:
            return

        # Build payload for the frontend
        payload = self._build_payload(event_type, event)
        if payload is None:
            return

        # Publish to Redis stream for EventRelay pickup
        try:
            payload_json = json.dumps(payload, default=str)
            await self._redis.xadd(
                STREAM_KEY,
                {"event_type": event_type, "payload": payload_json},
                maxlen=MAX_STREAM_LEN,
                approximate=True,
            )
        except Exception:
            logger.warning(
                "Failed to publish %s event for session %s",
                event_type,
                self._session_id,
            )

    def _build_payload(self, event_type: str, event: Any) -> dict[str, Any] | None:
        """Build a Redis-publishable payload from an Anthropic event.

        Args:
            event_type: The event type string.
            event: Anthropic SSE event object.

        Returns:
            Dict payload for Redis, or None to skip this event.
        """
        base: dict[str, Any] = {
            "meeting_id": str(self._meeting_id),
            "agent_name": self._agent_name,
            "anthropic_session_id": self._session_id,
            "timestamp": time.time(),
        }

        if event_type == "agent.message":
            # Extract text content from the message
            content = ""
            raw_content = getattr(event, "content", None)
            if isinstance(raw_content, list):
                for block in raw_content:
                    if getattr(block, "type", None) == "text":
                        content += getattr(block, "text", "")
            elif isinstance(raw_content, str):
                content = raw_content
            if not content:
                return None
            base["content"] = content
            base["text"] = content

        elif event_type == "agent.mcp_tool_use":
            base["tool_name"] = getattr(event, "name", None) or getattr(
                event, "tool_name", "unknown"
            )
            base["server_name"] = getattr(event, "server_name", "kutana")

        elif event_type == "session.error":
            error = getattr(event, "error", None)
            base["error"] = str(error) if error else "Unknown error"
            base["message"] = base["error"]

        elif event_type == "session.status_idle":
            pass  # base fields are sufficient

        return base

    @property
    def token_usage(self) -> dict[str, int]:
        """Accumulated token usage from this session."""
        return dict(self._token_usage)


# ---------------------------------------------------------------------------
# Transcript batcher (Redis Stream consumer)
# ---------------------------------------------------------------------------


class TranscriptBatcher:
    """Batches transcript segments from Redis Streams and pushes to agents.

    Reads transcript.segment.final events from the kutana:events stream,
    accumulates them per-meeting in 30-second windows, and sends batched
    transcript text to all active Anthropic managed agent sessions for
    that meeting.

    Uses a Redis consumer group so multiple instances share the workload.

    Attributes:
        _redis_url: Redis connection URL.
        _api_key: Anthropic API key.
        _db_factory: Async session factory for database access.
    """

    def __init__(
        self,
        redis_url: str,
        api_key: str,
        db_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Initialise the transcript batcher.

        Args:
            redis_url: Redis connection URL.
            api_key: Anthropic API key for managed agent communication.
            db_factory: Async session factory for database access.
        """
        self._redis_url = redis_url
        self._api_key = api_key
        self._db_factory = db_factory
        self._consumer_name = f"lifecycle-{socket.gethostname()}"
        self._stop_event = asyncio.Event()
        self._redis: aioredis.Redis[str] | None = None

        # Per-meeting segment buffer: {meeting_id: [(speaker, text, timestamp)]}
        self._buffers: dict[UUID, list[tuple[str, str, float]]] = {}
        self._last_flush: dict[UUID, float] = {}

        # Event proxy tasks: {anthropic_session_id: (task, proxy)}
        self._proxy_tasks: dict[str, tuple[asyncio.Task[None], SessionEventProxy]] = {}

    async def start(self) -> None:
        """Connect to Redis and begin consuming transcript events.

        Runs until stop() is called. Intended to be wrapped in
        asyncio.create_task() by the service lifespan.
        """
        self._stop_event.clear()
        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        logger.info(
            "TranscriptBatcher starting (stream=%s, group=%s)",
            STREAM_KEY,
            GROUP_NAME,
        )

        try:
            await self._ensure_group()
            await self._consume_loop()
        finally:
            # Flush remaining buffers on shutdown
            for meeting_id in list(self._buffers):
                await self._flush_buffer(meeting_id)
            # Cancel all event proxy tasks
            await self._stop_all_proxies()
            await self._close_redis()

    async def stop(self) -> None:
        """Signal the consume loop to exit."""
        logger.info("TranscriptBatcher stop requested")
        self._stop_event.set()

    async def _stop_all_proxies(self) -> None:
        """Cancel all running event proxy tasks."""
        for session_id, (task, _proxy) in list(self._proxy_tasks.items()):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            logger.debug("Stopped event proxy for session %s", session_id)
        self._proxy_tasks.clear()

    async def _ensure_group(self) -> None:
        """Create the consumer group if it does not exist."""
        assert self._redis is not None
        try:
            await self._redis.xgroup_create(STREAM_KEY, GROUP_NAME, id="$", mkstream=True)
            logger.info("Created consumer group '%s'", GROUP_NAME)
        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                logger.debug("Consumer group '%s' already exists", GROUP_NAME)
            else:
                raise

    async def _consume_loop(self) -> None:
        """Main XREADGROUP loop with exponential backoff on errors."""
        assert self._redis is not None
        backoff = 1.0

        while not self._stop_event.is_set():
            try:
                response: (
                    list[tuple[str, list[tuple[str, dict[str, str]]]]] | None
                ) = await self._redis.xreadgroup(
                    groupname=GROUP_NAME,
                    consumername=self._consumer_name,
                    streams={STREAM_KEY: ">"},
                    count=BATCH_SIZE,
                    block=BLOCK_MS,
                )
                backoff = 1.0

                if not response:
                    # Check for time-based flushes even when no new events
                    await self._check_window_flushes()
                    continue

                for _stream_name, entries in response:
                    for entry_id, fields in entries:
                        await self._handle_entry(entry_id, fields)

                # Check for time-based flushes after processing entries
                await self._check_window_flushes()

            except asyncio.CancelledError:
                logger.info("TranscriptBatcher cancelled")
                raise
            except RedisConnectionError as exc:
                if self._stop_event.is_set():
                    break
                logger.warning(
                    "Redis connection error: %s — retrying in %.0fs",
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)
                await self._close_redis()
                self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
                await self._ensure_group()
            except Exception:
                logger.exception("Unexpected error in transcript batcher")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)

    async def _handle_entry(
        self,
        entry_id: str,
        fields: dict[str, str],
    ) -> None:
        """Process a single stream entry — buffer transcript segments.

        Also handles meeting.started and meeting.ended events to trigger
        lifecycle actions.

        Args:
            entry_id: Redis stream entry ID.
            fields: Entry fields (event_type, payload).
        """
        assert self._redis is not None
        event_type = fields.get("event_type", "")
        raw_payload = fields.get("payload", "")

        if event_type == "transcript.segment.final":
            await self._buffer_segment(raw_payload)
        elif event_type == "meeting.started":
            await self._handle_meeting_started(raw_payload)
        elif event_type == "meeting.ended":
            await self._handle_meeting_ended(raw_payload)

        # Acknowledge regardless of event type
        await self._redis.xack(STREAM_KEY, GROUP_NAME, entry_id)

    async def _buffer_segment(self, raw_payload: str) -> None:
        """Parse and buffer a transcript segment.

        Args:
            raw_payload: JSON string of the TranscriptSegmentFinal event.
        """
        try:
            data = json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.warning("Malformed transcript segment payload")
            return

        segment = data.get("segment", data)
        meeting_id_str = segment.get("meeting_id") or data.get("meeting_id")
        if not meeting_id_str:
            return

        try:
            meeting_id = UUID(str(meeting_id_str))
        except ValueError:
            return

        speaker = segment.get("speaker_name") or segment.get("speaker_id") or "Unknown"
        text = segment.get("text", "")
        timestamp = segment.get("start_time", 0.0)

        if not text.strip():
            return

        if meeting_id not in self._buffers:
            self._buffers[meeting_id] = []
            self._last_flush[meeting_id] = asyncio.get_event_loop().time()

        self._buffers[meeting_id].append((speaker, text, timestamp))

    async def _check_window_flushes(self) -> None:
        """Flush buffers that have accumulated for >= TRANSCRIPT_WINDOW_SECONDS."""
        now = asyncio.get_event_loop().time()
        for meeting_id in list(self._buffers):
            last = self._last_flush.get(meeting_id, now)
            if now - last >= TRANSCRIPT_WINDOW_SECONDS:
                await self._flush_buffer(meeting_id)

    async def _flush_buffer(self, meeting_id: UUID) -> None:
        """Send buffered transcript segments to active agents for a meeting.

        Args:
            meeting_id: Meeting whose buffer to flush.
        """
        segments = self._buffers.pop(meeting_id, [])
        self._last_flush.pop(meeting_id, None)

        if not segments:
            return

        # Format transcript batch
        lines: list[str] = []
        for speaker, text, ts in segments:
            minutes = int(ts // 60)
            seconds = int(ts % 60)
            lines.append(f"[{minutes:02d}:{seconds:02d}] {speaker}: {text}")

        transcript_text = f"## Transcript Update (meeting {meeting_id})\n\n" + "\n".join(lines)

        # Find active hosted sessions with Anthropic integration
        async with self._db_factory() as db:
            result = await db.execute(
                select(HostedAgentSessionORM.anthropic_session_id).where(
                    HostedAgentSessionORM.meeting_id == meeting_id,
                    HostedAgentSessionORM.status == "active",
                    HostedAgentSessionORM.anthropic_session_id.is_not(None),
                )
            )
            session_ids = [row[0] for row in result.all()]

        for session_id in session_ids:
            try:
                await send_message(self._api_key, session_id, transcript_text)
            except Exception:
                logger.exception(
                    "Failed to send transcript batch to session %s",
                    session_id,
                )

        logger.info(
            "Flushed %d transcript segments to %d agent(s) for meeting %s",
            len(segments),
            len(session_ids),
            meeting_id,
        )

    async def _handle_meeting_started(self, raw_payload: str) -> None:
        """Handle meeting.started event — send context to agents and start proxies.

        Args:
            raw_payload: JSON string of the MeetingStarted event.
        """
        try:
            data = json.loads(raw_payload)
            meeting_id = UUID(str(data["meeting_id"]))
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.warning("Malformed meeting.started payload")
            return

        async with self._db_factory() as db:
            await on_meeting_started(meeting_id, db, self._api_key)
            await db.commit()

        # Start event proxies for active sessions
        await self._start_proxies_for_meeting(meeting_id)

    async def _handle_meeting_ended(self, raw_payload: str) -> None:
        """Handle meeting.ended event — stop proxies, close sessions, record billing.

        Args:
            raw_payload: JSON string of the MeetingEnded event.
        """
        try:
            data = json.loads(raw_payload)
            meeting_id = UUID(str(data["meeting_id"]))
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.warning("Malformed meeting.ended payload")
            return

        # Flush any remaining transcript segments first
        await self._flush_buffer(meeting_id)

        # Stop event proxies for this meeting
        await self._stop_proxies_for_meeting(meeting_id)

        async with self._db_factory() as db:
            await on_meeting_ended(meeting_id, db, self._api_key)
            await db.commit()

    async def _start_proxies_for_meeting(self, meeting_id: UUID) -> None:
        """Start event proxies for all active hosted sessions in a meeting.

        Args:
            meeting_id: Meeting whose sessions should be proxied.
        """
        if self._redis is None:
            return

        async with self._db_factory() as db:
            result = await db.execute(
                select(
                    HostedAgentSessionORM.anthropic_session_id,
                    AgentTemplateORM.name,
                )
                .join(
                    AgentTemplateORM,
                    HostedAgentSessionORM.template_id == AgentTemplateORM.id,
                )
                .where(
                    HostedAgentSessionORM.meeting_id == meeting_id,
                    HostedAgentSessionORM.status == "active",
                    HostedAgentSessionORM.anthropic_session_id.is_not(None),
                )
            )
            rows = result.all()

        for anthropic_session_id, agent_name in rows:
            if anthropic_session_id in self._proxy_tasks:
                continue  # Already proxying

            proxy = SessionEventProxy(
                api_key=self._api_key,
                anthropic_session_id=anthropic_session_id,
                meeting_id=meeting_id,
                agent_name=agent_name,
                redis_client=self._redis,
            )
            task = asyncio.create_task(proxy.run())
            self._proxy_tasks[anthropic_session_id] = (task, proxy)
            logger.info(
                "Started event proxy for %s (session %s, meeting %s)",
                agent_name,
                anthropic_session_id,
                meeting_id,
            )

    async def _stop_proxies_for_meeting(self, meeting_id: UUID) -> None:
        """Stop event proxies for all sessions in a meeting.

        Args:
            meeting_id: Meeting whose proxies should be stopped.
        """
        meeting_str = str(meeting_id)
        to_remove: list[str] = []

        for session_id, (task, proxy) in self._proxy_tasks.items():
            if str(proxy._meeting_id) == meeting_str:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
                to_remove.append(session_id)
                logger.info(
                    "Stopped event proxy for %s (session %s)",
                    proxy._agent_name,
                    session_id,
                )

        for session_id in to_remove:
            del self._proxy_tasks[session_id]

    async def _close_redis(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
