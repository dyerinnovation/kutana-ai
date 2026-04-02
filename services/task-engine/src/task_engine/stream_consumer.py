"""Redis Streams consumer for transcript.segment.final events."""

from __future__ import annotations

import asyncio
import json
import logging
import socket
from typing import TYPE_CHECKING

import redis.asyncio as redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

from kutana_core.events.definitions import TranscriptSegmentFinal

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from kutana_core.models.transcript import TranscriptSegment

logger = logging.getLogger(__name__)

# Stream and group defaults — must match EventPublisher in audio-service.
DEFAULT_STREAM_KEY = "kutana:events"
DEFAULT_GROUP_NAME = "task-engine"
DEFAULT_BLOCK_MS = 5_000  # How long XREADGROUP blocks waiting for new entries
DEFAULT_BATCH_SIZE = 10  # Max entries per XREADGROUP call
_MAX_BACKOFF_SECONDS = 30  # Cap on exponential back-off after Redis errors

# Event type we care about
_SEGMENT_EVENT_TYPE = "transcript.segment.final"


class StreamConsumer:
    """Reads transcript.segment.final events from a Redis Stream.

    Uses a Redis consumer group so that multiple instances of the
    task-engine can share the workload without reprocessing the same
    messages.  Each entry is acknowledged (XACK) only after the
    ``on_segment`` callback returns successfully.

    Attributes:
        _redis_url: Connection URL for the Redis server.
        _on_segment: Async callback invoked for every received segment.
        _stream_key: Redis stream key (shared with EventPublisher).
        _group_name: Consumer group name.
        _consumer_name: Unique name for this consumer instance.
        _block_ms: Milliseconds to block on each XREADGROUP call.
        _batch_size: Maximum messages to fetch per call.
        _stop_event: Internal flag used to request a graceful stop.
        _redis: Live Redis client (set after :meth:`start`).
    """

    def __init__(
        self,
        redis_url: str,
        on_segment: Callable[[TranscriptSegment], Awaitable[None]],
        group_name: str = DEFAULT_GROUP_NAME,
        consumer_name: str | None = None,
        stream_key: str = DEFAULT_STREAM_KEY,
        block_ms: int = DEFAULT_BLOCK_MS,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> None:
        """Initialise the consumer.

        Args:
            redis_url: Redis connection URL.
            on_segment: Async callback called with each :class:`TranscriptSegment`
                read from the stream.
            group_name: Consumer group name.  All instances sharing this
                name will split the stream entries between them.
            consumer_name: Unique name for this consumer within the group.
                Defaults to ``worker-<hostname>``.
            stream_key: Redis stream key to read from.
            block_ms: Milliseconds XREADGROUP blocks per call when the
                stream has no new entries.
            batch_size: Maximum entries to fetch per XREADGROUP call.
        """
        self._redis_url = redis_url
        self._on_segment = on_segment
        self._stream_key = stream_key
        self._group_name = group_name
        self._consumer_name = consumer_name or f"worker-{socket.gethostname()}"
        self._block_ms = block_ms
        self._batch_size = batch_size
        self._stop_event = asyncio.Event()
        self._redis: redis.Redis[str] | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect to Redis, ensure the consumer group exists, then run.

        This coroutine runs until :meth:`stop` is called or the task is
        cancelled.  It is intended to be wrapped in ``asyncio.create_task``
        by the service lifespan.
        """
        self._stop_event.clear()
        self._redis = redis.from_url(self._redis_url, decode_responses=True)
        logger.info(
            "StreamConsumer starting (stream=%s, group=%s, consumer=%s)",
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
        """Signal the consume loop to exit after the current iteration.

        Calling this method is safe even before :meth:`start` is awaited.
        """
        logger.info("StreamConsumer stop requested")
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _ensure_group(self) -> None:
        """Create the consumer group if it does not already exist.

        Uses ``XGROUP CREATE … $ MKSTREAM`` so the stream is also
        created if absent.  A ``BUSYGROUP`` error from Redis means the
        group already exists and is silently ignored.
        """
        assert self._redis is not None
        try:
            await self._redis.xgroup_create(
                self._stream_key,
                self._group_name,
                id="$",
                mkstream=True,
            )
            logger.info(
                "Created consumer group '%s' on stream '%s'",
                self._group_name,
                self._stream_key,
            )
        except ResponseError as exc:
            if "BUSYGROUP" in str(exc):
                logger.debug(
                    "Consumer group '%s' already exists — joining",
                    self._group_name,
                )
            else:
                raise

    async def _consume_loop(self) -> None:
        """Main XREADGROUP loop; runs until stop is signalled or cancelled.

        Uses exponential back-off (capped at :data:`_MAX_BACKOFF_SECONDS`)
        when Redis connection errors occur, so the service recovers
        automatically when the Redis server restarts.
        """
        assert self._redis is not None
        backoff = 1.0
        logger.info("StreamConsumer entering consume loop")

        while not self._stop_event.is_set():
            try:
                response: list[
                    tuple[str, list[tuple[str, dict[str, str]]]]
                ] | None = await self._redis.xreadgroup(
                    groupname=self._group_name,
                    consumername=self._consumer_name,
                    streams={self._stream_key: ">"},
                    count=self._batch_size,
                    block=self._block_ms,
                )
                backoff = 1.0  # reset on success

                if not response:
                    # Block timeout — no new entries; loop again
                    continue

                for _stream_name, entries in response:
                    for entry_id, fields in entries:
                        await self._handle_entry(entry_id, fields)

            except asyncio.CancelledError:
                logger.info("StreamConsumer cancelled — exiting loop")
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
                # Reconnect
                await self._close_redis()
                self._redis = redis.from_url(
                    self._redis_url, decode_responses=True
                )
                await self._ensure_group()
            except Exception:
                logger.exception("Unexpected error in consume loop")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _MAX_BACKOFF_SECONDS)

        logger.info("StreamConsumer loop exited cleanly")

    async def _handle_entry(
        self,
        entry_id: str,
        fields: dict[str, str],
    ) -> None:
        """Process a single Redis stream entry.

        Filters for :data:`_SEGMENT_EVENT_TYPE`, deserialises the payload,
        invokes the ``on_segment`` callback, then acknowledges the message.
        Entries with unrecognised event types are acknowledged and skipped.
        Malformed payloads are logged and acknowledged to avoid blocking
        the consumer group's pending-entry list (PEL).

        Args:
            entry_id: The Redis stream entry ID (used for XACK).
            fields: Mapping of ``event_type`` and ``payload`` from the stream.
        """
        assert self._redis is not None

        event_type = fields.get("event_type", "")

        if event_type != _SEGMENT_EVENT_TYPE:
            # Not our event — acknowledge and skip
            await self._ack(entry_id)
            return

        raw_payload = fields.get("payload", "")
        try:
            data = json.loads(raw_payload)
            event = TranscriptSegmentFinal.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            logger.exception(
                "Failed to parse %s payload (entry=%s) — acknowledging to "
                "prevent PEL build-up",
                _SEGMENT_EVENT_TYPE,
                entry_id,
            )
            await self._ack(entry_id)
            return

        try:
            await self._on_segment(event.segment)
        except Exception:
            logger.exception(
                "on_segment callback raised for entry=%s — acknowledging "
                "anyway to avoid repeated delivery",
                entry_id,
            )

        await self._ack(entry_id)
        logger.debug(
            "Processed and acknowledged entry %s (meeting=%s)",
            entry_id,
            event.meeting_id,
        )

    async def _ack(self, entry_id: str) -> None:
        """Acknowledge a stream entry so it leaves the PEL.

        Args:
            entry_id: The Redis stream entry ID to acknowledge.
        """
        assert self._redis is not None
        await self._redis.xack(self._stream_key, self._group_name, entry_id)

    async def _close_redis(self) -> None:
        """Close the Redis connection if open."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
