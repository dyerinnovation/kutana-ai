"""Meeting lifecycle wiring for Anthropic managed agent sessions.

Connects meeting events to Anthropic managed agent sessions:
- on_meeting_started: notifies active agents with meeting context
- TranscriptBatcher: batches transcript segments (30s windows) and pushes to agents
- on_meeting_ended: sends final summary request, closes sessions, records billing
- Event bridge: streams Anthropic session events and publishes to Redis for
  the gateway EventRelay to forward to browser WebSocket clients.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from datetime import UTC, datetime
from typing import TYPE_CHECKING
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
GROUP_NAME = "agent-lifecycle"
BLOCK_MS = 5_000
BATCH_SIZE = 10
_MAX_BACKOFF_SECONDS = 30

# Transcript batching window (seconds)
TRANSCRIPT_WINDOW_SECONDS = 30.0

# Event types we forward from Anthropic sessions to the frontend
_FORWARDED_EVENT_TYPES = frozenset({
    "agent.message",
    "agent.mcp_tool_use",
    "session.error",
    "session.status_idle",
})

# Active streaming tasks per Anthropic session (prevents duplicates)
_streaming_tasks: dict[str, asyncio.Task[None]] = {}


# ---------------------------------------------------------------------------
# Event bridge: Anthropic session events → Redis stream → frontend
# ---------------------------------------------------------------------------


async def _publish_agent_event(
    redis_conn: aioredis.Redis[str],
    event_type: str,
    meeting_id: UUID,
    agent_name: str,
    payload: dict[str, object],
) -> None:
    """Publish an agent event to the kutana:events Redis stream.

    The gateway EventRelay consumes these and forwards them to human
    WebSocket sessions. The browser MeetingRoomPage handles them in
    the agent activity panel.

    Args:
        redis_conn: Active Redis connection.
        event_type: Event type (e.g. "agent.message").
        meeting_id: Meeting this event belongs to.
        agent_name: Display name of the agent template.
        payload: Event-specific payload fields.
    """
    full_payload = {
        "meeting_id": str(meeting_id),
        "agent_name": agent_name,
        "timestamp": datetime.now(tz=UTC).timestamp(),
        **payload,
    }
    try:
        await redis_conn.xadd(
            STREAM_KEY,
            {"event_type": event_type, "payload": json.dumps(full_payload, default=str)},
            maxlen=10_000,
            approximate=True,
        )
    except Exception:
        logger.warning("Failed to publish %s for agent %s", event_type, agent_name)


async def stream_and_publish_events(
    api_key: str,
    anthropic_session_id: str,
    meeting_id: UUID,
    agent_name: str,
    redis_conn: aioredis.Redis[str],
) -> None:
    """Stream events from an Anthropic session and publish them to Redis.

    Runs until the session goes idle or an error occurs. Safe to run as
    a background asyncio task.

    Args:
        api_key: Anthropic API key.
        anthropic_session_id: The active Anthropic session to stream from.
        meeting_id: Meeting ID for routing events to the right WebSocket clients.
        agent_name: Agent template display name for the UI.
        redis_conn: Redis connection for publishing events.
    """
    try:
        async for event in stream_events(api_key, anthropic_session_id):
            event_type = getattr(event, "type", None)
            if event_type not in _FORWARDED_EVENT_TYPES:
                continue

            payload: dict[str, object] = {}
            if event_type == "agent.message":
                # Extract text content from the message
                content_blocks = getattr(event, "content", [])
                text_parts: list[str] = []
                for block in content_blocks:
                    if getattr(block, "type", None) == "text":
                        text_parts.append(getattr(block, "text", ""))
                payload["content"] = " ".join(text_parts) or "(no text)"
            elif event_type == "agent.mcp_tool_use":
                payload["tool_name"] = getattr(event, "name", None) or getattr(event, "tool_name", "unknown")
            elif event_type == "session.error":
                error_obj = getattr(event, "error", None)
                payload["message"] = (
                    getattr(error_obj, "message", str(error_obj))
                    if error_obj
                    else "Unknown error"
                )
            # session.status_idle needs no extra fields

            await _publish_agent_event(redis_conn, event_type, meeting_id, agent_name, payload)

            if event_type in ("session.status_idle", "session.error"):
                break
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(
            "Error streaming events for session %s (agent %s)",
            anthropic_session_id,
            agent_name,
        )
    finally:
        _streaming_tasks.pop(anthropic_session_id, None)


def start_event_streaming(
    api_key: str,
    anthropic_session_id: str,
    meeting_id: UUID,
    agent_name: str,
    redis_conn: aioredis.Redis[str],
) -> None:
    """Start streaming Anthropic session events as a background task.

    Idempotent: if a streaming task is already running for this session,
    this is a no-op.

    Args:
        api_key: Anthropic API key.
        anthropic_session_id: Anthropic session ID to stream from.
        meeting_id: Meeting ID for event routing.
        agent_name: Agent display name.
        redis_conn: Redis connection.
    """
    existing = _streaming_tasks.get(anthropic_session_id)
    if existing is not None and not existing.done():
        return

    task = asyncio.create_task(
        stream_and_publish_events(
            api_key, anthropic_session_id, meeting_id, agent_name, redis_conn,
        ),
        name=f"agent-events-{anthropic_session_id[:8]}",
    )
    _streaming_tasks[anthropic_session_id] = task


# ---------------------------------------------------------------------------
# Meeting started handler
# ---------------------------------------------------------------------------


async def on_meeting_started(
    meeting_id: UUID,
    db: AsyncSession,
    api_key: str,
    redis_conn: aioredis.Redis[str] | None = None,
) -> None:
    """Notify all active hosted agent sessions that a meeting has started.

    For each active HostedAgentSession linked to this meeting, sends a
    user.message with meeting context (title, participants, agenda).
    Starts background event streaming to publish agent responses to Redis.

    Args:
        meeting_id: ID of the meeting that started.
        db: Async database session.
        api_key: Anthropic API key.
        redis_conn: Redis connection for publishing agent events to the frontend.
    """
    # Find active hosted sessions with their template names
    result = await db.execute(
        select(HostedAgentSessionORM, AgentTemplateORM.name)
        .join(AgentTemplateORM, HostedAgentSessionORM.template_id == AgentTemplateORM.id)
        .where(
            HostedAgentSessionORM.meeting_id == meeting_id,
            HostedAgentSessionORM.status == "active",
            HostedAgentSessionORM.anthropic_session_id.is_not(None),
        )
    )
    rows = result.all()

    if not rows:
        logger.debug("No active hosted sessions for meeting %s", meeting_id)
        return

    # Fetch meeting context
    context = await _build_meeting_context(meeting_id, db)

    # Send context to each agent session and start event streaming
    for session, template_name in rows:
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
            # Start streaming Anthropic events → Redis → gateway → browser
            if redis_conn is not None:
                start_event_streaming(
                    api_key,
                    session.anthropic_session_id,
                    meeting_id,
                    template_name,
                    redis_conn,
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
            await self._close_redis()

    async def stop(self) -> None:
        """Signal the consume loop to exit."""
        logger.info("TranscriptBatcher stop requested")
        self._stop_event.set()

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

        # Find active hosted sessions with template names
        async with self._db_factory() as db:
            result = await db.execute(
                select(
                    HostedAgentSessionORM.anthropic_session_id,
                    AgentTemplateORM.name,
                )
                .join(AgentTemplateORM, HostedAgentSessionORM.template_id == AgentTemplateORM.id)
                .where(
                    HostedAgentSessionORM.meeting_id == meeting_id,
                    HostedAgentSessionORM.status == "active",
                    HostedAgentSessionORM.anthropic_session_id.is_not(None),
                )
            )
            rows = result.all()

        for anthropic_session_id, template_name in rows:
            try:
                await send_message(self._api_key, anthropic_session_id, transcript_text)
                # Start streaming agent response events → Redis → browser
                if self._redis is not None:
                    start_event_streaming(
                        self._api_key,
                        anthropic_session_id,
                        meeting_id,
                        template_name,
                        self._redis,
                    )
            except Exception:
                logger.exception(
                    "Failed to send transcript batch to session %s",
                    anthropic_session_id,
                )

        logger.info(
            "Flushed %d transcript segments to %d agent(s) for meeting %s",
            len(segments),
            len(rows),
            meeting_id,
        )

    async def _handle_meeting_started(self, raw_payload: str) -> None:
        """Handle meeting.started event — send context to agents.

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
            await on_meeting_started(meeting_id, db, self._api_key, redis_conn=self._redis)
            await db.commit()

    async def _handle_meeting_ended(self, raw_payload: str) -> None:
        """Handle meeting.ended event — close sessions and record billing.

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

        async with self._db_factory() as db:
            await on_meeting_ended(meeting_id, db, self._api_key)
            await db.commit()

    async def _close_redis(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
