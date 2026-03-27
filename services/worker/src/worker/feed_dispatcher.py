"""FeedDispatcher — consumes meeting events and creates feed runs.

Subscribes to ``convene:events`` on the ``feed-dispatcher`` consumer group.
When a ``meeting.started`` or ``meeting.ended`` event arrives, queries the
database for matching feeds and enqueues ``FeedRun`` records to the
``convene:feed-runs`` stream for the FeedRunner to pick up.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError
from sqlalchemy import select

from convene_core.database.models import FeedORM, FeedRunORM

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

DEFAULT_STREAM_KEY = "convene:events"
DEFAULT_GROUP_NAME = "feed-dispatcher"
FEED_RUNS_STREAM = "convene:feed-runs"
DEFAULT_BLOCK_MS = 5_000
DEFAULT_BATCH_SIZE = 10
_MAX_BACKOFF_SECONDS = 30

_MEETING_STARTED = "meeting.started"
_MEETING_ENDED = "meeting.ended"


class FeedDispatcher:
    """Reads meeting events and dispatches feed runs to a secondary stream.

    Attributes:
        _redis_url: Redis connection URL.
        _session_factory: SQLAlchemy async session factory.
        _stream_key: Redis stream key for events.
        _group_name: Consumer group name.
        _consumer_name: Unique consumer name.
        _block_ms: XREADGROUP block timeout.
        _batch_size: Max entries per read.
    """

    def __init__(
        self,
        redis_url: str,
        session_factory: async_sessionmaker[AsyncSession],
        stream_key: str = DEFAULT_STREAM_KEY,
        group_name: str = DEFAULT_GROUP_NAME,
        consumer_name: str | None = None,
        block_ms: int = DEFAULT_BLOCK_MS,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        """Initialise the dispatcher.

        Args:
            redis_url: Redis connection URL.
            session_factory: SQLAlchemy async session factory for DB queries.
            stream_key: Redis stream key to consume from.
            group_name: Consumer group name.
            consumer_name: Unique name for this consumer instance.
            block_ms: Milliseconds XREADGROUP blocks per call.
            batch_size: Max entries per XREADGROUP call.
        """
        self._redis_url = redis_url
        self._session_factory = session_factory
        self._stream_key = stream_key
        self._group_name = group_name
        self._consumer_name = consumer_name or f"feed-dispatcher-{socket.gethostname()}"
        self._block_ms = block_ms
        self._batch_size = batch_size
        self._stop_event = asyncio.Event()
        self._redis: redis.Redis[str] | None = None

    async def start(self) -> None:
        """Connect to Redis, ensure consumer group, then run the consume loop."""
        self._stop_event.clear()
        self._redis = redis.from_url(self._redis_url, decode_responses=True)
        logger.info(
            "FeedDispatcher starting (stream=%s, group=%s, consumer=%s)",
            self._stream_key,
            self._group_name,
            self._consumer_name,
        )
        try:
            await self._ensure_group()
            await self._consume_loop()
        finally:
            await self._close_redis()

    async def stop(self) -> None:
        """Signal the consume loop to exit."""
        logger.info("FeedDispatcher stop requested")
        self._stop_event.set()

    async def _ensure_group(self) -> None:
        """Create the consumer group if it does not exist."""
        assert self._redis is not None
        try:
            await self._redis.xgroup_create(
                self._stream_key,
                self._group_name,
                id="$",
                mkstream=True,
            )
            logger.info("Created consumer group '%s'", self._group_name)
        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                logger.debug("Consumer group '%s' already exists", self._group_name)
            else:
                raise

    async def _consume_loop(self) -> None:
        """Main XREADGROUP loop with exponential backoff on errors."""
        assert self._redis is not None
        backoff = 1.0

        while not self._stop_event.is_set():
            try:
                response = await self._redis.xreadgroup(
                    groupname=self._group_name,
                    consumername=self._consumer_name,
                    streams={self._stream_key: ">"},
                    count=self._batch_size,
                    block=self._block_ms,
                )
                backoff = 1.0

                if not response:
                    continue

                for _stream_name, entries in response:
                    for entry_id, fields in entries:
                        await self._handle_entry(entry_id, fields)

            except asyncio.CancelledError:
                logger.info("FeedDispatcher cancelled")
                raise
            except RedisConnectionError as exc:
                if self._stop_event.is_set():
                    break
                logger.warning("Redis connection error: %s — retrying in %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)
                await self._close_redis()
                self._redis = redis.from_url(self._redis_url, decode_responses=True)
                await self._ensure_group()
            except Exception:
                logger.exception("Unexpected error in FeedDispatcher consume loop")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)

        logger.info("FeedDispatcher loop exited")

    async def _handle_entry(self, entry_id: str, fields: dict[str, str]) -> None:
        """Process a single stream entry.

        Filters for meeting.started and meeting.ended events, queries matching
        feeds, creates FeedRun records, and enqueues them.

        Args:
            entry_id: Redis stream entry ID.
            fields: Entry fields (event_type, payload).
        """
        assert self._redis is not None
        event_type = fields.get("event_type", "")

        if event_type not in (_MEETING_STARTED, _MEETING_ENDED):
            await self._ack(entry_id)
            return

        raw_payload = fields.get("payload", "")
        try:
            data = json.loads(raw_payload)
            meeting_id = UUID(data["meeting_id"])
        except (json.JSONDecodeError, KeyError, ValueError):
            logger.exception("Failed to parse %s payload (entry=%s)", event_type, entry_id)
            await self._ack(entry_id)
            return

        # Determine which feeds to trigger
        if event_type == _MEETING_STARTED:
            trigger_value = "meeting_started"
            directions = ("inbound", "bidirectional")
            run_direction = "inbound"
        else:
            trigger_value = "meeting_ended"
            directions = ("outbound", "bidirectional")
            run_direction = "outbound"

        # Query matching feeds
        async with self._session_factory() as session:
            result = await session.execute(
                select(FeedORM).where(
                    FeedORM.is_active.is_(True),
                    FeedORM.trigger == trigger_value,
                    FeedORM.direction.in_(directions),
                )
            )
            feeds = result.scalars().all()

            for feed in feeds:
                run_id = uuid4()
                run = FeedRunORM(
                    id=run_id,
                    feed_id=feed.id,
                    meeting_id=meeting_id,
                    trigger=trigger_value,
                    direction=run_direction,
                    status="pending",
                )
                session.add(run)

            await session.commit()

        # Enqueue feed runs to the feed-runs stream
        for feed in feeds:
            await self._redis.xadd(
                FEED_RUNS_STREAM,
                {
                    "event_type": "feed.run.pending",
                    "payload": json.dumps(
                        {
                            "feed_run_id": str(run_id),
                            "feed_id": str(feed.id),
                            "meeting_id": str(meeting_id),
                            "direction": run_direction,
                        },
                        default=str,
                    ),
                },
                maxlen=10_000,
                approximate=True,
            )
            logger.info(
                "Dispatched feed run: feed=%s meeting=%s direction=%s",
                feed.name,
                meeting_id,
                run_direction,
            )

        await self._ack(entry_id)

    async def _ack(self, entry_id: str) -> None:
        """Acknowledge a stream entry.

        Args:
            entry_id: The Redis stream entry ID to acknowledge.
        """
        assert self._redis is not None
        await self._redis.xack(self._stream_key, self._group_name, entry_id)

    async def _close_redis(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
