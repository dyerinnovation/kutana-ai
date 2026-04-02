"""NATS JetStream implementation of the MessageBus ABC.

Uses the ``nats-py`` async client with JetStream for durable, at-least-once
delivery.  Each Kutana topic maps directly to a JetStream subject.  Consumer
groups are implemented via JetStream durable consumers sharing the same
``deliver_group`` — messages are load-balanced across members.

NATS subjects support native wildcard matching (``*`` for a single token,
``>`` for multiple tokens), making topic pattern matching first-class.

Requires ``nats-py`` (install with ``uv add 'kutana-providers[nats]'``).

Configuration environment variables::

    NATS_URL            NATS server URL (default: nats://localhost:4222)
    NATS_CREDENTIALS    Path to NATS credentials file (optional)
    NATS_STREAM_NAME    JetStream stream name (default: CONVENE)
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
from typing import Any
from uuid import uuid4

from kutana_core.messaging.abc import MessageBus
from kutana_core.messaging.types import Message, Subscription

logger = logging.getLogger(__name__)

# Lazy import — nats-py is an optional dependency.
try:
    import nats  # type: ignore[import-untyped]
    import nats.aio.client  # type: ignore[import-untyped]
    import nats.js  # type: ignore[import-untyped]
    import nats.js.api  # type: ignore[import-untyped]

    _NATS_AVAILABLE = True
except ImportError:
    _NATS_AVAILABLE = False


def _require_nats() -> None:
    """Raise ImportError with install instructions if nats-py is missing."""
    if not _NATS_AVAILABLE:
        msg = (
            "nats-py is required for NATSMessageBus. "
            "Install it with: uv add 'kutana-providers[nats]'"
        )
        raise ImportError(msg)


def _topic_to_subject(topic: str) -> str:
    """Convert a Kutana topic string to a NATS subject.

    Kutana topics use dot-separated tokens (``"meeting.abc.events"``),
    which are already valid NATS subjects.  The fnmatch ``*`` wildcard
    (matches a single path component) maps 1:1 to NATS ``*``.

    Args:
        topic: Kutana topic string.

    Returns:
        NATS subject string.
    """
    return topic


def _consumer_name(topic: str, group: str) -> str:
    """Return a JetStream durable consumer name for a (topic, group) pair.

    Args:
        topic: NATS subject string.
        group: Consumer group name.

    Returns:
        A valid JetStream consumer name (alphanumeric + hyphen/underscore,
        max 256 chars).
    """
    import re

    combined = f"{topic}-{group}"
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", combined)
    return safe[:256]


class NATSMessageBus(MessageBus):
    """MessageBus implementation backed by NATS JetStream.

    Each :meth:`publish` call ensures the JetStream stream exists then
    publishes to a subject.  Each :meth:`subscribe` call creates a durable
    JetStream consumer and starts a background subscription task.

    Consumer groups are implemented via JetStream queue groups: all consumers
    sharing the same *group* bind to the same durable consumer with the same
    ``deliver_group``, receiving messages in a load-balanced manner.

    Fan-out subscriptions (``group=None``) create an ephemeral push consumer
    per subscriber.

    NATS subject wildcards (``*``, ``>``) map directly to JetStream subject
    filters.

    Args:
        url: NATS server URL. Defaults to ``"nats://localhost:4222"``.
        credentials_path: Path to a NATS credentials file (optional).
        stream_name: JetStream stream name. Defaults to ``"CONVENE"``.
        stream_subjects: Subject filters for the stream. Defaults to ``[">"]``
            (capture all subjects).
    """

    def __init__(
        self,
        url: str | None = None,
        credentials_path: str | None = None,
        stream_name: str | None = None,
        stream_subjects: list[str] | None = None,
    ) -> None:
        """Initialize the NATS JetStream message bus."""
        _require_nats()
        self._url = url or os.getenv("NATS_URL", "nats://localhost:4222")
        self._credentials_path = credentials_path or os.getenv("NATS_CREDENTIALS")
        self._stream_name = stream_name or os.getenv("NATS_STREAM_NAME", "CONVENE")
        self._stream_subjects = stream_subjects or [">"]

        self._nc: Any = None  # nats.aio.client.Client
        self._js: Any = None  # nats.js.JetStreamContext

        self._subscriptions: dict[str, Subscription] = {}
        self._nats_subs: dict[str, Any] = {}  # sub_id -> NATS subscription object
        self._tasks: list[asyncio.Task[None]] = []
        self._stream_created = False

    async def _get_client(self) -> Any:
        """Return connected NATS client, connecting on first call."""
        if self._nc is None or not self._nc.is_connected:
            connect_opts: dict[str, Any] = {"servers": [self._url]}
            if self._credentials_path:
                connect_opts["credentials"] = self._credentials_path
            self._nc = await nats.connect(**connect_opts)
            self._js = self._nc.jetstream()
            logger.debug("Connected to NATS at %s", self._url)
        return self._nc

    async def _get_jetstream(self) -> Any:
        """Return JetStream context, ensuring the stream exists."""
        await self._get_client()
        if not self._stream_created:
            await self._ensure_stream()
        return self._js

    async def _ensure_stream(self) -> None:
        """Create the JetStream stream if it does not exist."""
        try:
            await self._js.find_stream(self._stream_name)
            logger.debug("NATS stream %s already exists", self._stream_name)
        except Exception:
            # Stream not found — create it
            config = nats.js.api.StreamConfig(
                name=self._stream_name,
                subjects=self._stream_subjects,
                retention=nats.js.api.RetentionPolicy.LIMITS,
                max_age=86400,  # 1 day in seconds
                storage=nats.js.api.StorageType.FILE,
                duplicate_window=60,
            )
            await self._js.add_stream(config=config)
            logger.debug(
                "Created NATS stream %s with subjects %s",
                self._stream_name,
                self._stream_subjects,
            )
        self._stream_created = True

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
        """Publish a message to a NATS JetStream subject.

        Args:
            topic: Kutana topic string — maps directly to a NATS subject.
            payload: JSON-serializable message payload.
            metadata: Optional routing metadata.
            source: Name of the publishing service.

        Returns:
            The unique message UUID assigned to this message.
        """
        message = Message(
            topic=topic,
            payload=payload,
            metadata=metadata or {},
            source=source,
        )
        body = json.dumps({
            "message_id": message.id,
            "topic": message.topic,
            "payload": message.payload,
            "metadata": message.metadata,
            "timestamp": message.timestamp.isoformat(),
            "source": message.source,
        })
        subject = _topic_to_subject(topic)
        js = await self._get_jetstream()
        await js.publish(subject, body.encode("utf-8"))
        logger.debug("Published message %s to NATS subject %s", message.id, subject)
        return message.id

    async def subscribe(
        self,
        topic: str,
        handler: Any,
        group: str | None = None,
    ) -> Subscription:
        """Subscribe to a NATS JetStream subject.

        For consumer group subscriptions (``group`` is not None) a durable
        JetStream push consumer with a queue group is created, providing
        load-balanced delivery.

        For fan-out subscriptions (``group=None``) an ephemeral push consumer
        is created per subscriber, receiving all messages independently.

        Args:
            topic: Exact NATS subject or wildcard pattern (e.g.
                ``"meeting.*.events"`` or ``"meeting.>"``).
            handler: Async callback ``async def handler(msg: Message) -> None``.
            group: Consumer group name for load-balanced delivery.

        Returns:
            A Subscription object.
        """
        sub = Subscription(topic=topic, handler=handler, group=group)
        self._subscriptions[sub.subscription_id] = sub

        js = await self._get_jetstream()
        subject = _topic_to_subject(topic)

        nats_sub: Any
        if group is not None:
            durable = _consumer_name(subject, group)
            nats_sub = await js.subscribe(
                subject,
                queue=group,
                durable=durable,
                cb=self._make_handler(sub),
            )
        else:
            # Ephemeral fan-out consumer
            nats_sub = await js.subscribe(
                subject,
                cb=self._make_handler(sub),
            )

        self._nats_subs[sub.subscription_id] = nats_sub
        logger.debug(
            "NATS subscribed to %s (group=%s, id=%s)",
            topic,
            group,
            sub.subscription_id,
        )
        return sub

    def _make_handler(
        self, sub: Subscription
    ) -> Any:
        """Create a NATS message callback that dispatches to the subscription handler.

        Args:
            sub: The Subscription whose handler should be called.

        Returns:
            An async callback compatible with nats-py subscribe.
        """

        async def callback(nats_msg: Any) -> None:
            if sub.subscription_id not in self._subscriptions:
                return
            try:
                body = json.loads(nats_msg.data.decode("utf-8"))
                message = Message(
                    id=body.get("message_id", str(uuid4())),
                    topic=body.get("topic", sub.topic),
                    payload=body.get("payload", {}),
                    metadata=body.get("metadata", {}),
                    source=body.get("source", ""),
                )
                await sub.handler(message)
                # Auto-ack for JetStream push consumers
                await nats_msg.ack()
            except Exception:
                logger.exception(
                    "Error dispatching NATS message for topic %s", sub.topic
                )
                with contextlib.suppress(Exception):
                    await nats_msg.nak()

        return callback

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Remove an active subscription and drain the NATS sub.

        Args:
            subscription: The subscription to remove.
        """
        self._subscriptions.pop(subscription.subscription_id, None)
        nats_sub = self._nats_subs.pop(subscription.subscription_id, None)
        if nats_sub is not None:
            try:
                await nats_sub.unsubscribe()
            except Exception:
                logger.exception("Error unsubscribing NATS sub for %s", subscription.topic)
        logger.debug(
            "NATS unsubscribed from %s (id=%s)",
            subscription.topic,
            subscription.subscription_id,
        )

    async def ack(self, subscription: Subscription, message_id: str) -> None:
        """No-op — NATS JetStream messages are auto-acked in the callback.

        JetStream push consumers automatically acknowledge messages once the
        callback completes without raising.  Explicit ack via receipt handle
        is not needed for this push-consumer model.

        Args:
            subscription: The subscription that received the message.
            message_id: Unused — ack is handled in the message callback.
        """
        # Push consumers auto-ack in _make_handler callback.
        pass

    async def close(self) -> None:
        """Drain all subscriptions and close the NATS connection."""
        self._subscriptions.clear()

        # Unsubscribe all NATS subs
        for nats_sub in self._nats_subs.values():
            with contextlib.suppress(Exception):
                await nats_sub.unsubscribe()
        self._nats_subs.clear()

        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        if self._nc is not None:
            with contextlib.suppress(Exception):
                await self._nc.drain()
            self._nc = None
            self._js = None
        logger.debug("NATSMessageBus closed")
