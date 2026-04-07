"""Redis Streams implementation of the MessageBus ABC."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import redis.asyncio as aioredis

from kutana_core.messaging.abc import MessageBus
from kutana_core.messaging.types import Message, Subscription

logger = logging.getLogger(__name__)


class RedisStreamsMessageBus(MessageBus):
    """MessageBus implementation backed by Redis Streams.

    Uses ``XADD`` for publish, ``XREADGROUP`` for consumer group subscriptions
    (at-least-once, load-balanced), and ``XREAD`` for fan-out subscriptions.
    Consumer groups are created automatically on first subscribe. Topic patterns
    (fnmatch syntax, e.g. ``"meeting.*.insights"``) are resolved via Redis
    ``SCAN`` on each polling iteration.

    Args:
        url: Redis connection URL. Defaults to ``redis://localhost:6379/0``.
        consumer_name: Unique consumer identifier for this process. Defaults
            to a random ``kutana-<hex>`` string.
        poll_block_ms: Milliseconds to block on each XREAD/XREADGROUP call.
            Shorter values improve unsubscribe/close latency. Defaults to 500.
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        consumer_name: str | None = None,
        poll_block_ms: int = 500,
    ) -> None:
        self._url = url
        self._consumer_name = consumer_name or f"kutana-{uuid4().hex[:8]}"
        self._poll_block_ms = poll_block_ms
        self._redis: Any = None  # aioredis.Redis[str] once connected
        self._subscriptions: dict[str, Subscription] = {}
        self._tasks: list[asyncio.Task[None]] = []

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_redis(self) -> Any:
        """Return the Redis client, creating it on first call."""
        if self._redis is None:
            self._redis = aioredis.from_url(self._url, decode_responses=True)
        return self._redis

    def _make_entry(self, message: Message) -> dict[str, str]:
        """Serialise a Message to a Redis stream entry dict."""
        return {
            "message_id": message.id,
            "topic": message.topic,
            "payload": json.dumps(message.payload),
            "metadata": json.dumps(message.metadata),
            "timestamp": message.timestamp.isoformat(),
            "source": message.source,
        }

    def _parse_entry(self, fields: dict[str, str]) -> Message:
        """Deserialise a Redis stream entry dict to a Message."""
        timestamp_str = fields.get("timestamp", "")
        timestamp = (
            datetime.fromisoformat(timestamp_str)
            if timestamp_str
            else datetime.now(tz=UTC)
        )
        return Message(
            id=fields.get("message_id", ""),
            topic=fields.get("topic", ""),
            payload=json.loads(fields.get("payload", "{}")),
            metadata=json.loads(fields.get("metadata", "{}")),
            timestamp=timestamp,
            source=fields.get("source", ""),
        )

    # ------------------------------------------------------------------
    # MessageBus interface
    # ------------------------------------------------------------------

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        metadata: dict[str, str] | None = None,
        source: str = "",
    ) -> str:
        """Publish a message to a Redis Stream.

        Args:
            topic: Topic name used as the Redis stream key.
            payload: Message payload (JSON-serializable).
            metadata: Optional routing metadata.
            source: Publishing service name.

        Returns:
            The message's UUID (not the Redis stream entry ID).
        """
        redis = await self._get_redis()
        message = Message(
            topic=topic,
            payload=payload,
            metadata=metadata or {},
            source=source,
        )
        entry = self._make_entry(message)
        stream_id: str = await redis.xadd(topic, entry)
        logger.debug(
            "Published message %s to %s (stream_id=%s)",
            message.id,
            topic,
            stream_id,
        )
        return message.id

    async def subscribe(
        self,
        topic: str,
        handler: Any,
        group: str | None = None,
    ) -> Subscription:
        """Subscribe to a topic or fnmatch pattern.

        For exact (non-pattern) group subscriptions the consumer group is
        created immediately. For pattern subscriptions the group is created
        lazily as matching streams are discovered.

        Args:
            topic: Exact topic or fnmatch pattern (e.g. ``"meeting.*.events"``).
            handler: Async callback ``async def handler(msg: Message) -> None``.
            group: Consumer group name for load-balanced delivery.

        Returns:
            A Subscription representing this active subscription.
        """
        sub = Subscription(topic=topic, handler=handler, group=group)
        self._subscriptions[sub.subscription_id] = sub

        is_pattern = any(c in topic for c in ("*", "?", "["))
        if group is not None and not is_pattern:
            redis = await self._get_redis()
            try:
                await redis.xgroup_create(topic, group, id="$", mkstream=True)
                logger.debug("Created consumer group %s on stream %s", group, topic)
            except Exception:
                # Group already exists — that's fine
                logger.debug(
                    "Consumer group %s already exists on stream %s", group, topic
                )

        task: asyncio.Task[None] = asyncio.create_task(
            self._consume(sub), name=f"bus-sub-{sub.subscription_id[:8]}"
        )
        self._tasks.append(task)
        logger.debug(
            "Subscribed to %s (group=%s, id=%s)", topic, group, sub.subscription_id
        )
        return sub

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Remove an active subscription.

        Args:
            subscription: The subscription to remove.
        """
        self._subscriptions.pop(subscription.subscription_id, None)
        logger.debug(
            "Unsubscribed from %s (id=%s)",
            subscription.topic,
            subscription.subscription_id,
        )

    async def ack(self, subscription: Subscription, message_id: str) -> None:
        """Acknowledge a message in a consumer group.

        No-op for fan-out (non-group) subscriptions.

        Args:
            subscription: The subscription that received the message.
            message_id: The message ID to acknowledge (the ``Message.id`` UUID,
                stored as the ``message_id`` field in the stream entry).
        """
        if subscription.group is None:
            return
        redis = await self._get_redis()
        await redis.xack(subscription.topic, subscription.group, message_id)
        logger.debug(
            "Acked message %s in group %s on %s",
            message_id,
            subscription.group,
            subscription.topic,
        )

    async def close(self) -> None:
        """Cancel all subscriptions and close the Redis connection."""
        self._subscriptions.clear()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        logger.debug("RedisStreamsMessageBus closed")

    # ------------------------------------------------------------------
    # Background poll loop
    # ------------------------------------------------------------------

    async def _consume(self, sub: Subscription) -> None:
        """Background task that polls Redis and dispatches messages."""
        redis = await self._get_redis()
        is_pattern = any(c in sub.topic for c in ("*", "?", "["))
        # Per-stream last-seen IDs for XREAD (fan-out) subscriptions
        stream_last_ids: dict[str, str] = {}

        while sub.subscription_id in self._subscriptions:
            try:
                target_streams = (
                    await self._scan_matching_streams(redis, sub.topic)
                    if is_pattern
                    else [sub.topic]
                )
                if not target_streams:
                    await asyncio.sleep(0.1)
                    continue

                if sub.group is not None:
                    await self._read_group(redis, sub, target_streams)
                else:
                    await self._read_fanout(
                        redis, sub, target_streams, stream_last_ids
                    )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Error in consume loop for topic %s", sub.topic
                )
                await asyncio.sleep(1)

    async def _scan_matching_streams(
        self, redis: Any, pattern: str
    ) -> list[str]:
        """Return all Redis keys matching the given fnmatch pattern."""
        matched: list[str] = []
        cursor = 0
        while True:
            cursor, keys = await redis.scan(
                cursor=cursor, match=pattern, count=100
            )
            matched.extend(keys)
            if cursor == 0:
                break
        return matched

    async def _read_group(
        self,
        redis: Any,
        sub: Subscription,
        streams: list[str],
    ) -> None:
        """Read from streams using XREADGROUP (consumer group mode)."""
        assert sub.group is not None
        for stream in streams:
            # Lazily create the group for pattern-discovered streams
            with contextlib.suppress(Exception):
                await redis.xgroup_create(stream, sub.group, id="$", mkstream=True)

            results: list[Any] = await redis.xreadgroup(
                sub.group,
                self._consumer_name,
                {stream: ">"},
                count=10,
                block=self._poll_block_ms,
            )
            if results:
                await self._dispatch(results, sub)

    async def _read_fanout(
        self,
        redis: Any,
        sub: Subscription,
        streams: list[str],
        stream_last_ids: dict[str, str],
    ) -> None:
        """Read from streams using XREAD (fan-out mode)."""
        read_map = {s: stream_last_ids.get(s, "$") for s in streams}
        results: list[Any] = await redis.xread(
            read_map,
            count=10,
            block=self._poll_block_ms,
        )
        if results:
            for stream_key, entries in results:
                for entry_id, _fields in entries:
                    stream_last_ids[stream_key] = entry_id
            await self._dispatch(results, sub)

    async def _dispatch(
        self,
        results: list[Any],
        sub: Subscription,
    ) -> None:
        """Dispatch stream entries to the subscription handler."""
        for _stream_key, entries in results:
            for _entry_id, fields in entries:
                try:
                    message = self._parse_entry(fields)
                    await sub.handler(message)
                except Exception:
                    logger.exception(
                        "Error dispatching message from %s", sub.topic
                    )


def create_message_bus_from_env() -> MessageBus:
    """Create a MessageBus instance from environment variables.

    Reads ``KUTANA_MESSAGE_BUS`` to select the backend provider, then reads
    provider-specific environment variables to configure it.

    Supported backends:

    ``redis`` (default)
        Uses :class:`RedisStreamsMessageBus`.  Reads ``REDIS_URL``
        (default: ``redis://localhost:6379/0``).

    ``aws-sns-sqs``
        Uses :class:`~kutana_providers.messaging.aws_sns_sqs.SQSMessageBus`.
        Reads ``AWS_REGION``, ``AWS_ACCESS_KEY_ID``, ``AWS_SECRET_ACCESS_KEY``,
        and optionally ``AWS_SESSION_TOKEN``.  Requires ``aioboto3``.

    ``gcp-pubsub``
        Uses :class:`~kutana_providers.messaging.gcp_pubsub.PubSubMessageBus`.
        Reads ``GCP_PROJECT_ID`` and uses Application Default Credentials or
        ``GOOGLE_APPLICATION_CREDENTIALS``.  Requires ``google-cloud-pubsub``.

    ``nats``
        Uses :class:`~kutana_providers.messaging.nats_jetstream.NATSMessageBus`.
        Reads ``NATS_URL`` (default: ``nats://localhost:4222``) and optionally
        ``NATS_CREDENTIALS``.  Requires ``nats-py``.

    Returns:
        A configured MessageBus provider instance.

    Raises:
        ValueError: If ``KUTANA_MESSAGE_BUS`` names an unsupported backend.
    """
    import os


    backend = os.getenv("KUTANA_MESSAGE_BUS", "redis").lower()

    if backend == "redis":
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        return RedisStreamsMessageBus(url=redis_url)

    if backend == "aws-sns-sqs":
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        return SQSMessageBus(
            region=os.getenv("AWS_REGION", "us-east-1"),
            access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            session_token=os.getenv("AWS_SESSION_TOKEN"),
        )

    if backend == "gcp-pubsub":
        from kutana_providers.messaging.gcp_pubsub import PubSubMessageBus

        return PubSubMessageBus(
            project_id=os.getenv("GCP_PROJECT_ID"),
        )

    if backend == "nats":
        from kutana_providers.messaging.nats_jetstream import NATSMessageBus

        return NATSMessageBus(
            url=os.getenv("NATS_URL", "nats://localhost:4222"),
            credentials_path=os.getenv("NATS_CREDENTIALS"),
            stream_name=os.getenv("NATS_STREAM_NAME", "CONVENE"),
        )

    supported = ", ".join(["redis", "aws-sns-sqs", "gcp-pubsub", "nats"])
    msg = (
        f"Unsupported KUTANA_MESSAGE_BUS value: {backend!r}. "
        f"Supported backends: {supported}"
    )
    raise ValueError(msg)
