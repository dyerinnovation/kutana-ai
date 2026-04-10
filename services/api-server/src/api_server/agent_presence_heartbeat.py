"""Participant-presence heartbeat + materializer.

Why presence is materialized in api-server (not the gateway):
We derive "who is currently in a meeting" from the ``ParticipantJoined`` /
``ParticipantLeft`` events the agent-gateway already publishes to the
``kutana:events`` Redis stream (see
``services/agent-gateway/src/agent_gateway/human_session.py:426-466`` and
``agent_session.py:616-640``). Ownership of the events stays with the
gateway; api-server maintains a derived Redis set as a queryable index so
the reconciler can answer "does meeting X have at least one live
participant?" in O(1) without cross-service HTTP — and without adding a
new tracker to either service. ``MeetingEventRelay`` already reads the
same stream, so the precedent of materializing derived state in
api-server is established.

Two cooperating background tasks, both started from the api-server
lifespan hook alongside ``MeetingEventRelay``:

1. :class:`PresenceMaterializer` — consumes ``kutana:events`` via its
   own dedicated consumer group ``presence-materializer`` (distinct from
   ``MeetingEventRelay``'s ``agent-lifecycle`` group so neither competes
   for messages).
     - ``participant.joined`` → ``SADD kutana:presence:{meeting_id} {participant_id}``
     - ``participant.left``   → ``SREM kutana:presence:{meeting_id} {participant_id}``
   Set semantics absorb out-of-order delivery and duplicate events.
   Empty sets are left in place (SCARD returns 0) — do not DEL them.

2. :class:`PresenceReconciler` — every
   ``PRESENCE_HEARTBEAT_INTERVAL_SEC`` (default 30s), walks every
   ``MeetingStatus.ACTIVE`` meeting and compares live presence to
   selected-template state:
     - ``SCARD > 0`` — warm any selected template that is missing an
       active ``HostedAgentSessionORM`` row via the shared
       :func:`api_server.managed_agent_activation._warm_agent_in_background`
       helper (reusing its ``_warming_tasks`` idempotency map).
     - ``SCARD == 0`` — end every active session for the meeting (best-
       effort Anthropic ``end_session``, mark DB row ``stopped``, record
       billing usage) and publish :class:`AgentSessionStopped` so the
       per-agent frontend spinner can flip back to ``warming`` if people
       rejoin.

Known limitation: if api-server is down longer than the ``kutana:events``
stream ``MAXLEN`` window (10,000 entries), the materializer can miss a
trailing ``ParticipantLeft`` and over-count presence. Set semantics
self-heal on the next ``ParticipantJoined`` / ``ParticipantLeft`` for
that meeting. Phase B item: add a one-time reconcile-from-source on
startup once the gateway exposes a snapshot endpoint or Redis key.

On ``meeting.ended``: the existing ``on_meeting_ended`` handler in
``agent_lifecycle.py`` stays the final backstop — this module only
operates on ``MeetingStatus.ACTIVE`` meetings, so once the status flips
to ``completed`` the reconciler naturally stops touching it.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import math
import os
import socket
from datetime import UTC, datetime
from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

import redis.asyncio as aioredis
from pydantic import BaseModel, Field
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from sqlalchemy import select

from api_server.managed_agent_activation import (
    _warm_agent_in_background,
    _warming_tasks,
)
from api_server.managed_agents import end_session
from kutana_core.database.models import (
    HostedAgentSessionORM,
    MeetingORM,
    MeetingSelectedTemplateORM,
    UsageRecordORM,
)
from kutana_core.models.meeting import MeetingStatus

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from api_server.deps import Settings
    from api_server.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STREAM_KEY = "kutana:events"
MATERIALIZER_GROUP = "presence-materializer"
PRESENCE_KEY_PREFIX = "kutana:presence:"
BATCH_SIZE = 20
BLOCK_MS = 5_000
_MAX_BACKOFF_SECONDS = 30

# Event type constants (mirror kutana_core.events.definitions.ParticipantJoined/Left)
_EVENT_PARTICIPANT_JOINED = "participant.joined"
_EVENT_PARTICIPANT_LEFT = "participant.left"

PRESENCE_HEARTBEAT_INTERVAL_SEC: int = int(os.environ.get("PRESENCE_HEARTBEAT_INTERVAL_SEC", "30"))


def presence_key(meeting_id: UUID) -> str:
    """Return the Redis set key that holds live participant IDs for a meeting.

    Args:
        meeting_id: The meeting to build the key for.

    Returns:
        The Redis key string ``kutana:presence:{meeting_id}``.
    """
    return f"{PRESENCE_KEY_PREFIX}{meeting_id}"


# ---------------------------------------------------------------------------
# Local event: AgentSessionStopped
# ---------------------------------------------------------------------------


class AgentSessionStopped(BaseModel):
    """Emitted when the presence reconciler shuts down a managed agent session.

    Flows through the agent gateway → frontend WebSocket so the per-agent
    spinner can flip back to ``warming`` (reconciled on next join) or
    ``stopped`` depending on frontend policy.

    Defined locally in this module rather than in ``kutana-core`` to
    keep the presence-heartbeat work in scope for this task. Promote to
    ``packages/kutana-core/src/kutana_core/events/definitions.py`` in a
    follow-up once a second consumer needs it.

    Attributes:
        event_id: Unique identifier for this event instance.
        timestamp: When the event was created (UTC).
        meeting_id: Meeting whose agent session was stopped.
        template_id: Template whose session was stopped.
        reason: Short reason code (e.g. ``"no_participants"``).
    """

    event_type: ClassVar[str] = "agent.session.stopped"
    event_id: UUID = Field(default_factory=lambda: UUID(int=0))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    meeting_id: UUID
    template_id: UUID
    reason: str = "no_participants"

    def to_dict(self) -> dict[str, object]:
        """Serialize to a dict matching the ``BaseEvent`` wire format.

        Returns:
            Dictionary representation with the ``event_type`` field set.
        """
        data = self.model_dump(mode="json")
        data["event_type"] = self.event_type
        return data


# ---------------------------------------------------------------------------
# Presence query
# ---------------------------------------------------------------------------


async def count_room_participants(
    redis_client: aioredis.Redis[str],
    meeting_id: UUID,
) -> int:
    """Return the number of live participants for a meeting.

    Reads from the Redis set maintained by :class:`PresenceMaterializer`.
    A meeting with no key or an empty set returns ``0``.

    Args:
        redis_client: Async Redis client.
        meeting_id: Meeting to query.

    Returns:
        Number of distinct participant IDs currently in the meeting.
    """
    count = await redis_client.scard(presence_key(meeting_id))
    return int(count or 0)


# ---------------------------------------------------------------------------
# Presence materializer (Redis Streams consumer)
# ---------------------------------------------------------------------------


class PresenceMaterializer:
    """Materializes ``participant.joined`` / ``participant.left`` into a Redis set.

    Runs as a background task started from the api-server lifespan hook.
    Uses its own consumer group (``presence-materializer``) on the shared
    ``kutana:events`` stream so it does not compete with
    ``MeetingEventRelay``'s ``agent-lifecycle`` group — both see every
    message independently.

    Attributes:
        _redis_url: Redis connection URL.
        _consumer_name: Per-host consumer name for the group.
        _stop_event: Signals the consume loop to exit.
        _redis: Active Redis client (rebuilt on reconnect).
    """

    def __init__(self, redis_url: str) -> None:
        """Initialise the materializer.

        Args:
            redis_url: Redis connection URL (same as the rest of api-server).
        """
        self._redis_url = redis_url
        self._consumer_name = f"presence-{socket.gethostname()}"
        self._stop_event = asyncio.Event()
        self._redis: aioredis.Redis[str] | None = None

    async def start(self) -> None:
        """Connect to Redis and begin consuming presence events.

        Runs until :meth:`stop` is called. Intended to be wrapped in
        ``asyncio.create_task()`` by the service lifespan hook.
        """
        self._stop_event.clear()
        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        logger.info(
            "PresenceMaterializer starting (stream=%s, group=%s)",
            STREAM_KEY,
            MATERIALIZER_GROUP,
        )
        try:
            await self._ensure_group()
            await self._consume_loop()
        finally:
            await self._close_redis()

    async def stop(self) -> None:
        """Signal the consume loop to exit."""
        logger.info("PresenceMaterializer stop requested")
        self._stop_event.set()

    async def _ensure_group(self) -> None:
        """Create the consumer group if it does not already exist."""
        assert self._redis is not None
        try:
            await self._redis.xgroup_create(STREAM_KEY, MATERIALIZER_GROUP, id="$", mkstream=True)
            logger.info("Created consumer group '%s'", MATERIALIZER_GROUP)
        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                logger.debug("Consumer group '%s' already exists", MATERIALIZER_GROUP)
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
                    groupname=MATERIALIZER_GROUP,
                    consumername=self._consumer_name,
                    streams={STREAM_KEY: ">"},
                    count=BATCH_SIZE,
                    block=BLOCK_MS,
                )
                backoff = 1.0

                if not response:
                    continue

                for _stream_name, entries in response:
                    for entry_id, fields in entries:
                        await self._handle_entry(entry_id, fields)

            except asyncio.CancelledError:
                logger.info("PresenceMaterializer cancelled")
                raise
            except RedisConnectionError as exc:
                if self._stop_event.is_set():
                    break
                logger.warning(
                    "PresenceMaterializer Redis connection error: %s — retrying in %.0fs",
                    exc,
                    backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)
                await self._close_redis()
                self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
                await self._ensure_group()
            except Exception:
                logger.exception("Unexpected error in PresenceMaterializer")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)

    async def _handle_entry(
        self,
        entry_id: str,
        fields: dict[str, str],
    ) -> None:
        """Process a single stream entry and ack it.

        Only ``participant.joined`` and ``participant.left`` mutate
        presence state; every other event type is acked without
        side-effects so the group pointer advances.

        Args:
            entry_id: Redis stream entry ID.
            fields: Entry fields (``event_type``, ``payload``).
        """
        assert self._redis is not None
        event_type = fields.get("event_type", "")

        if event_type in (_EVENT_PARTICIPANT_JOINED, _EVENT_PARTICIPANT_LEFT):
            await self._apply_presence_event(event_type, fields.get("payload", ""))

        # Ack even for ignored event types so the group pointer advances.
        try:
            await self._redis.xack(STREAM_KEY, MATERIALIZER_GROUP, entry_id)
        except Exception:
            logger.exception("Failed to ack presence entry %s", entry_id)

    async def _apply_presence_event(self, event_type: str, raw_payload: str) -> None:
        """Parse a participant event and mutate the presence set.

        Args:
            event_type: Either ``participant.joined`` or ``participant.left``.
            raw_payload: JSON payload string from the stream entry.
        """
        assert self._redis is not None
        try:
            data = json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.warning("PresenceMaterializer: malformed payload")
            return

        meeting_id_str = data.get("meeting_id")
        participant_id_str = data.get("participant_id")
        if not meeting_id_str or not participant_id_str:
            return

        try:
            meeting_id = UUID(str(meeting_id_str))
        except ValueError:
            return

        key = presence_key(meeting_id)
        participant_id = str(participant_id_str)

        if event_type == _EVENT_PARTICIPANT_JOINED:
            await self._redis.sadd(key, participant_id)
            logger.debug(
                "Presence: SADD %s %s (meeting=%s)",
                key,
                participant_id,
                meeting_id,
            )
        else:  # participant.left
            await self._redis.srem(key, participant_id)
            logger.debug(
                "Presence: SREM %s %s (meeting=%s)",
                key,
                participant_id,
                meeting_id,
            )
            # Do not DEL the key on empty — SCARD returns 0 either way.

    async def _close_redis(self) -> None:
        """Close the Redis connection if one is open."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


# ---------------------------------------------------------------------------
# Reconciler helpers
# ---------------------------------------------------------------------------


async def _list_active_meetings(
    db_factory: async_sessionmaker[AsyncSession],
) -> list[MeetingORM]:
    """Return every meeting currently in ``MeetingStatus.ACTIVE``.

    Args:
        db_factory: Async session factory.

    Returns:
        A list of ``MeetingORM`` rows with status ``active``. Empty list
        if the query fails or there are no active meetings.
    """
    async with db_factory() as db:
        result = await db.execute(
            select(MeetingORM).where(MeetingORM.status == MeetingStatus.ACTIVE.value)
        )
        return list(result.scalars().all())


async def _list_active_sessions(
    db_factory: async_sessionmaker[AsyncSession],
    meeting_id: UUID,
) -> list[HostedAgentSessionORM]:
    """Return active hosted agent sessions for a meeting.

    Filters to rows with an ``anthropic_session_id`` so in-flight warms
    (row inserted but Anthropic session not yet started) are not
    reaped — their ``_warm_agent_in_background`` task will clean up on
    its own.

    Args:
        db_factory: Async session factory.
        meeting_id: Meeting to query.

    Returns:
        A list of active ``HostedAgentSessionORM`` rows.
    """
    async with db_factory() as db:
        result = await db.execute(
            select(HostedAgentSessionORM).where(
                HostedAgentSessionORM.meeting_id == meeting_id,
                HostedAgentSessionORM.status == "active",
                HostedAgentSessionORM.anthropic_session_id.is_not(None),
            )
        )
        return list(result.scalars().all())


async def _list_selected_templates(
    db_factory: async_sessionmaker[AsyncSession],
    meeting_id: UUID,
) -> list[MeetingSelectedTemplateORM]:
    """Return the template selection rows for a meeting.

    Args:
        db_factory: Async session factory.
        meeting_id: Meeting to query.

    Returns:
        A list of ``MeetingSelectedTemplateORM`` rows (may be empty).
    """
    async with db_factory() as db:
        result = await db.execute(
            select(MeetingSelectedTemplateORM).where(
                MeetingSelectedTemplateORM.meeting_id == meeting_id
            )
        )
        return list(result.scalars().all())


async def _end_session_and_mark_stopped(
    session_id: UUID,
    db_factory: async_sessionmaker[AsyncSession],
    anthropic_api_key: str,
) -> None:
    """Close an Anthropic session and persist the stopped-state transition.

    Best-effort: if the Anthropic ``end_session`` call fails (session
    already stopped, network error, etc.) the DB row is still marked
    stopped and a usage record is written for billing. Idempotent: if
    the row is already ``stopped`` this returns without doing anything.

    Args:
        session_id: Primary key of the ``HostedAgentSessionORM`` row.
        db_factory: Async session factory.
        anthropic_api_key: API key for the Anthropic end-session call.
    """
    async with db_factory() as db:
        row = (
            await db.execute(
                select(HostedAgentSessionORM).where(HostedAgentSessionORM.id == session_id)
            )
        ).scalar_one_or_none()
        if row is None or row.status != "active":
            return

        if row.anthropic_session_id and anthropic_api_key:
            with contextlib.suppress(Exception):
                await end_session(anthropic_api_key, row.anthropic_session_id)

        now = datetime.now(tz=UTC)
        row.status = "stopped"
        row.ended_at = now

        # Record billing usage — the presence-driven shutdown is still a
        # billable span. Matches the pattern in agent_lifecycle._record_usage.
        duration = now - row.started_at
        duration_seconds = max(math.ceil(duration.total_seconds()), 1)
        db.add(
            UsageRecordORM(
                user_id=row.user_id,
                resource_type="managed_agent",
                resource_id=row.id,
                started_at=row.started_at,
                ended_at=now,
                duration_seconds=duration_seconds,
                billing_period=now.strftime("%Y-%m"),
            )
        )
        await db.commit()
        logger.info(
            "Presence-reconciler stopped session %s (meeting=%s, duration=%ds)",
            row.id,
            row.meeting_id,
            duration_seconds,
        )


def _spawn_warm(
    meeting: MeetingORM,
    selection: MeetingSelectedTemplateORM,
    db_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    publisher: EventPublisher,
) -> None:
    """Schedule a background warm for a selected template if not already warming.

    Uses the shared ``_warming_tasks`` idempotency map from
    ``managed_agent_activation`` so concurrent warms from the
    ``/start`` handler and the presence reconciler deduplicate.

    Args:
        meeting: Meeting the agent will join.
        selection: Selection row with the template and any overrides.
        db_factory: Async session factory.
        settings: Application settings.
        publisher: Event publisher for ``AgentSessionWarmed`` /
            ``AgentSessionFailed`` events.
    """
    if meeting.owner_id is None:
        logger.warning(
            "Skipping warm for meeting %s template %s: meeting has no owner_id",
            meeting.id,
            selection.template_id,
        )
        return

    key = (meeting.id, selection.template_id)
    existing = _warming_tasks.get(key)
    if existing is not None and not existing.done():
        logger.debug(
            "Warm already in flight for (meeting=%s, template=%s) — skipping",
            meeting.id,
            selection.template_id,
        )
        return

    task = asyncio.create_task(
        _warm_agent_in_background(
            db_factory=db_factory,
            settings=settings,
            user_id=meeting.owner_id,
            template_id=selection.template_id,
            meeting_id=meeting.id,
            system_prompt_override=selection.system_prompt_override,
            sop_id=selection.sop_id,
            publisher=publisher,
        ),
        name=f"presence-warm-{meeting.id}-{selection.template_id}",
    )
    _warming_tasks[key] = task
    logger.info(
        "Presence-reconciler spawned warm for template %s in meeting %s",
        selection.template_id,
        meeting.id,
    )


# ---------------------------------------------------------------------------
# Reconcile tick
# ---------------------------------------------------------------------------


async def reconcile_active_meetings(
    db_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    publisher: EventPublisher,
    redis_client: aioredis.Redis[str],
) -> None:
    """Single reconcile pass: walk every active meeting and match state to presence.

    For every meeting in ``MeetingStatus.ACTIVE``:

    - ``SCARD(presence_key) > 0``: spawn warms for any selected templates
      without an active hosted session (idempotent via ``_warming_tasks``).
    - ``SCARD(presence_key) == 0``: end every active hosted session,
      mark the row stopped, record billing, and publish
      :class:`AgentSessionStopped`.

    Never modifies the meeting status — once a meeting flips to
    ``completed`` via ``POST /meetings/{id}/end`` this pass naturally
    stops touching it.

    Args:
        db_factory: Async session factory.
        settings: Application settings.
        publisher: Event publisher for agent lifecycle events.
        redis_client: Redis client for presence SCARD queries.
    """
    try:
        active_meetings = await _list_active_meetings(db_factory)
    except Exception:
        logger.exception("Presence-reconciler: failed to list active meetings")
        return

    for meeting in active_meetings:
        try:
            await _reconcile_meeting(
                meeting=meeting,
                db_factory=db_factory,
                settings=settings,
                publisher=publisher,
                redis_client=redis_client,
            )
        except Exception:
            logger.exception("Presence-reconciler: failed to reconcile meeting %s", meeting.id)


async def _reconcile_meeting(
    meeting: MeetingORM,
    db_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    publisher: EventPublisher,
    redis_client: aioredis.Redis[str],
) -> None:
    """Reconcile a single meeting against its current presence state.

    Args:
        meeting: ``MeetingORM`` row to reconcile.
        db_factory: Async session factory.
        settings: Application settings.
        publisher: Event publisher.
        redis_client: Redis client for SCARD.
    """
    participant_count = await count_room_participants(redis_client, meeting.id)
    active_sessions = await _list_active_sessions(db_factory, meeting.id)
    selected = await _list_selected_templates(db_factory, meeting.id)

    if participant_count > 0:
        active_template_ids = {s.template_id for s in active_sessions}
        missing = [sel for sel in selected if sel.template_id not in active_template_ids]
        if missing:
            logger.info(
                "Presence-reconciler: meeting %s has %d participants, warming %d missing template(s)",
                meeting.id,
                participant_count,
                len(missing),
            )
        for sel in missing:
            _spawn_warm(meeting, sel, db_factory, settings, publisher)
        return

    if not active_sessions:
        return

    logger.info(
        "Presence-reconciler: meeting %s has no participants, stopping %d active session(s)",
        meeting.id,
        len(active_sessions),
    )
    for sess in active_sessions:
        template_id = sess.template_id
        try:
            await _end_session_and_mark_stopped(sess.id, db_factory, settings.anthropic_api_key)
        except Exception:
            logger.exception("Failed to end session %s for meeting %s", sess.id, meeting.id)
            continue
        try:
            await publisher.publish(
                AgentSessionStopped(
                    meeting_id=meeting.id,
                    template_id=template_id,
                    reason="no_participants",
                )
            )
        except Exception:
            logger.exception(
                "Failed to publish AgentSessionStopped for meeting %s template %s",
                meeting.id,
                template_id,
            )


# ---------------------------------------------------------------------------
# Presence reconciler loop
# ---------------------------------------------------------------------------


class PresenceReconciler:
    """Runs :func:`reconcile_active_meetings` on a fixed interval.

    Single in-process instance per api-server replica. Horizontal
    scaling is a Phase B item (would require a Redis lock or sharding
    by ``meeting_id`` hash).

    Attributes:
        _db_factory: Async session factory.
        _settings: Application settings.
        _publisher: Event publisher for agent lifecycle events.
        _redis_url: Redis connection URL.
        _interval_sec: Seconds between reconcile passes.
        _stop_event: Signals the tick loop to exit.
        _redis: Active Redis client (rebuilt on reconnect).
    """

    def __init__(
        self,
        db_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        publisher: EventPublisher,
        redis_url: str,
        interval_sec: int = PRESENCE_HEARTBEAT_INTERVAL_SEC,
    ) -> None:
        """Initialise the reconciler.

        Args:
            db_factory: Async session factory.
            settings: Application settings.
            publisher: Event publisher for agent lifecycle events.
            redis_url: Redis connection URL.
            interval_sec: Seconds between ticks (default from env).
        """
        self._db_factory = db_factory
        self._settings = settings
        self._publisher = publisher
        self._redis_url = redis_url
        self._interval_sec = interval_sec
        self._stop_event = asyncio.Event()
        self._redis: aioredis.Redis[str] | None = None

    async def start(self) -> None:
        """Enter the reconcile tick loop until :meth:`stop` is called.

        Intended to be wrapped in ``asyncio.create_task()`` by the
        service lifespan hook.
        """
        self._stop_event.clear()
        self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        logger.info("PresenceReconciler starting (interval=%ds)", self._interval_sec)
        backoff = 1.0
        try:
            while not self._stop_event.is_set():
                try:
                    assert self._redis is not None
                    await reconcile_active_meetings(
                        db_factory=self._db_factory,
                        settings=self._settings,
                        publisher=self._publisher,
                        redis_client=self._redis,
                    )
                    backoff = 1.0
                except asyncio.CancelledError:
                    raise
                except RedisConnectionError as exc:
                    logger.warning(
                        "PresenceReconciler Redis error: %s — retrying in %.0fs",
                        exc,
                        backoff,
                    )
                    await self._close_redis()
                    self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)
                    continue
                except Exception:
                    logger.exception("PresenceReconciler tick failed")

                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(self._stop_event.wait(), timeout=self._interval_sec)
        finally:
            await self._close_redis()
            logger.info("PresenceReconciler stopped")

    async def stop(self) -> None:
        """Signal the tick loop to exit."""
        logger.info("PresenceReconciler stop requested")
        self._stop_event.set()

    async def _close_redis(self) -> None:
        """Close the Redis connection if one is open."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
