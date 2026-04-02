"""GCP Pub/Sub implementation of the MessageBus ABC.

Uses the ``google-cloud-pubsub`` async client.  Each Kutana topic maps
to a GCP Pub/Sub topic.  Each ``(topic, group)`` pair maps to a separate
GCP subscription, providing consumer-group load-balanced delivery.  Fan-out
subscriptions (``group=None``) create a unique subscription per subscriber.

Requires ``google-cloud-pubsub`` (install with ``uv add 'kutana-providers[gcp]'``).

Configuration environment variables::

    GCP_PROJECT_ID                  GCP project ID (required)
    GOOGLE_APPLICATION_CREDENTIALS  Path to service account JSON (optional if
                                    using Application Default Credentials)
    PUBSUB_TOPIC_PREFIX             Prefix for Pub/Sub topic names (default: kutana-)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any
from uuid import uuid4

from kutana_core.messaging.abc import MessageBus
from kutana_core.messaging.types import Message, Subscription

logger = logging.getLogger(__name__)

# Lazy import — google-cloud-pubsub is an optional dependency.
try:
    from google.api_core.exceptions import AlreadyExists  # type: ignore[import-untyped]
    from google.cloud import pubsub_v1  # type: ignore[import-untyped]

    _PUBSUB_AVAILABLE = True
except ImportError:
    _PUBSUB_AVAILABLE = False


def _require_pubsub() -> None:
    """Raise ImportError with install instructions if google-cloud-pubsub is missing."""
    if not _PUBSUB_AVAILABLE:
        msg = (
            "google-cloud-pubsub is required for PubSubMessageBus. "
            "Install it with: uv add 'kutana-providers[gcp]'"
        )
        raise ImportError(msg)


def _topic_to_pubsub_name(topic: str, prefix: str) -> str:
    """Convert a Kutana topic string to a valid Pub/Sub topic ID.

    Pub/Sub topic IDs allow letters, numbers, hyphens, underscores, periods,
    tildes, and percent signs (max 255 chars).  Asterisks and brackets are
    replaced with underscores.

    Args:
        topic: Kutana topic string (e.g. ``"meeting.abc.events"``).
        prefix: Prefix to prepend.

    Returns:
        A valid Pub/Sub topic ID.
    """
    import re

    name = re.sub(r"[^a-zA-Z0-9._~%-]", "_", topic)
    full = f"{prefix}{name}"
    return full[:255]


def _subscription_name_for_group(topic: str, group: str, prefix: str) -> str:
    """Return a Pub/Sub subscription ID for a (topic, group) consumer pair.

    Args:
        topic: Kutana topic string.
        group: Consumer group name.
        prefix: Topic prefix.

    Returns:
        A valid Pub/Sub subscription ID (max 255 chars).
    """
    base = _topic_to_pubsub_name(topic, prefix)
    combined = f"{base}--{group}"
    return combined[:255]


class PubSubMessageBus(MessageBus):
    """MessageBus implementation backed by GCP Pub/Sub.

    Each :meth:`publish` call creates the Pub/Sub topic if needed and
    publishes the message.  Each :meth:`subscribe` call creates a Pub/Sub
    subscription for the ``(topic, group)`` pair and starts a streaming-pull
    background task.

    Consumer groups are modelled as separate subscriptions sharing the same
    topic: all subscribers with the same *group* name share one subscription
    and receive messages in a load-balanced manner.

    Fan-out subscriptions (``group=None``) create a unique subscription per
    subscriber, ensuring every subscriber receives every message.

    Args:
        project_id: GCP project ID.
        topic_prefix: Prefix for Pub/Sub topic names. Defaults to ``"kutana-"``.
        max_messages: Maximum messages to pull per batch. Defaults to 10.
    """

    def __init__(
        self,
        project_id: str | None = None,
        topic_prefix: str = "kutana-",
        max_messages: int = 10,
    ) -> None:
        """Initialize the Pub/Sub message bus."""
        _require_pubsub()
        self._project_id = project_id or os.getenv("GCP_PROJECT_ID", "")
        if not self._project_id:
            msg = "GCP_PROJECT_ID environment variable is required for PubSubMessageBus."
            raise ValueError(msg)
        self._topic_prefix = topic_prefix
        self._max_messages = max_messages

        self._publisher: Any = None  # pubsub_v1.PublisherAsyncClient
        self._subscriber: Any = None  # pubsub_v1.SubscriberAsyncClient

        self._subscriptions: dict[str, Subscription] = {}
        self._tasks: list[asyncio.Task[None]] = []

        # Cache: topic -> full topic path
        self._topic_paths: dict[str, str] = {}
        # Cache: sub_id -> subscription path
        self._sub_paths: dict[str, str] = {}

    def _get_publisher(self) -> Any:
        """Return the PublisherAsyncClient, creating it on first call."""
        if self._publisher is None:
            self._publisher = pubsub_v1.PublisherAsyncClient()
        return self._publisher

    def _get_subscriber(self) -> Any:
        """Return the SubscriberAsyncClient, creating it on first call."""
        if self._subscriber is None:
            self._subscriber = pubsub_v1.SubscriberAsyncClient()
        return self._subscriber

    def _topic_path(self, topic: str) -> str:
        """Return the full Pub/Sub topic resource path for a Kutana topic.

        Args:
            topic: Kutana topic string.

        Returns:
            Full Pub/Sub topic path.
        """
        topic_id = _topic_to_pubsub_name(topic, self._topic_prefix)
        return f"projects/{self._project_id}/topics/{topic_id}"

    def _subscription_path(self, topic: str, group: str) -> str:
        """Return the full Pub/Sub subscription resource path.

        Args:
            topic: Kutana topic string.
            group: Consumer group name.

        Returns:
            Full Pub/Sub subscription path.
        """
        sub_id = _subscription_name_for_group(topic, group, self._topic_prefix)
        return f"projects/{self._project_id}/subscriptions/{sub_id}"

    async def _get_or_create_topic(self, topic: str) -> str:
        """Return the Pub/Sub topic path, creating the topic if needed.

        Args:
            topic: Kutana topic string.

        Returns:
            Full Pub/Sub topic path.
        """
        if topic in self._topic_paths:
            return self._topic_paths[topic]

        path = self._topic_path(topic)
        publisher = self._get_publisher()
        try:
            await publisher.create_topic(name=path)
            logger.debug("Created Pub/Sub topic %s", path)
        except AlreadyExists:
            logger.debug("Pub/Sub topic already exists: %s", path)
        self._topic_paths[topic] = path
        return path

    async def _get_or_create_subscription(
        self, topic: str, group: str
    ) -> str:
        """Return the Pub/Sub subscription path, creating it if needed.

        Args:
            topic: Kutana topic string.
            group: Consumer group / subscription name.

        Returns:
            Full Pub/Sub subscription path.
        """
        cache_key = f"{topic}::{group}"
        if cache_key in self._sub_paths:
            return self._sub_paths[cache_key]

        topic_path = await self._get_or_create_topic(topic)
        sub_path = self._subscription_path(topic, group)
        subscriber = self._get_subscriber()
        try:
            await subscriber.create_subscription(
                name=sub_path,
                topic=topic_path,
                ack_deadline_seconds=30,
            )
            logger.debug("Created Pub/Sub subscription %s", sub_path)
        except AlreadyExists:
            logger.debug("Pub/Sub subscription already exists: %s", sub_path)
        self._sub_paths[cache_key] = sub_path
        return sub_path

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
        """Publish a message to a GCP Pub/Sub topic.

        Creates the topic if it does not yet exist.

        Args:
            topic: Kutana topic string — maps to a Pub/Sub topic name.
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
        topic_path = await self._get_or_create_topic(topic)
        publisher = self._get_publisher()
        data = body.encode("utf-8")
        await publisher.publish(topic=topic_path, data=data)
        logger.debug("Published message %s to Pub/Sub %s", message.id, topic_path)
        return message.id

    async def subscribe(
        self,
        topic: str,
        handler: Any,
        group: str | None = None,
    ) -> Subscription:
        """Subscribe to a GCP Pub/Sub topic.

        Creates the topic and subscription if they do not exist, then starts
        a streaming-pull background task.

        Args:
            topic: Exact topic or fnmatch pattern.
            handler: Async callback ``async def handler(msg: Message) -> None``.
            group: Consumer group name for load-balanced delivery.

        Returns:
            A Subscription object.
        """
        is_pattern = any(c in topic for c in ("*", "?", "["))
        sub = Subscription(topic=topic, handler=handler, group=group)
        self._subscriptions[sub.subscription_id] = sub

        if not is_pattern:
            effective_group = group or sub.subscription_id[:16]
            await self._get_or_create_subscription(topic, effective_group)

        task: asyncio.Task[None] = asyncio.create_task(
            self._consume(sub), name=f"pubsub-sub-{sub.subscription_id[:8]}"
        )
        self._tasks.append(task)
        logger.debug(
            "PubSub subscribed to %s (group=%s, id=%s)",
            topic,
            group,
            sub.subscription_id,
        )
        return sub

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Remove an active subscription.

        Args:
            subscription: The subscription to remove.
        """
        self._subscriptions.pop(subscription.subscription_id, None)
        logger.debug(
            "PubSub unsubscribed from %s (id=%s)",
            subscription.topic,
            subscription.subscription_id,
        )

    async def ack(self, subscription: Subscription, message_id: str) -> None:
        """Acknowledge a Pub/Sub message.

        For fan-out subscriptions (group=None) acknowledgement is handled
        automatically. For group subscriptions the caller must pass the
        Pub/Sub ack_id received by the polling loop.

        Args:
            subscription: The subscription that received the message.
            message_id: The Pub/Sub ack_id for the message.
        """
        if subscription.group is None:
            return
        effective_group = subscription.group
        cache_key = f"{subscription.topic}::{effective_group}"
        sub_path = self._sub_paths.get(cache_key)
        if sub_path is None:
            return
        subscriber = self._get_subscriber()
        try:
            await subscriber.acknowledge(
                subscription=sub_path, ack_ids=[message_id]
            )
        except Exception:
            logger.exception("PubSub ack failed for message %s", message_id)

    async def close(self) -> None:
        """Cancel all subscriptions and release resources."""
        self._subscriptions.clear()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        import contextlib

        if self._publisher is not None:
            with contextlib.suppress(Exception):
                await self._publisher.transport.close()  # type: ignore[attr-defined]
            self._publisher = None
        if self._subscriber is not None:
            with contextlib.suppress(Exception):
                await self._subscriber.transport.close()  # type: ignore[attr-defined]
            self._subscriber = None
        logger.debug("PubSubMessageBus closed")

    # ------------------------------------------------------------------
    # Background poll loop
    # ------------------------------------------------------------------

    async def _consume(self, sub: Subscription) -> None:
        """Pull messages from Pub/Sub and dispatch them to the handler."""
        is_pattern = any(c in sub.topic for c in ("*", "?", "["))

        while sub.subscription_id in self._subscriptions:
            try:
                if is_pattern:
                    await self._consume_pattern(sub)
                    continue
                effective_group = sub.group or sub.subscription_id[:16]
                cache_key = f"{sub.topic}::{effective_group}"
                sub_path = self._sub_paths.get(cache_key)
                if sub_path is None:
                    sub_path = await self._get_or_create_subscription(
                        sub.topic, effective_group
                    )
                await self._pull_and_dispatch(sub, sub_path)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Error in PubSub consume loop for %s", sub.topic
                )
                await asyncio.sleep(1.0)

    async def _consume_pattern(self, sub: Subscription) -> None:
        """Handle pattern subscriptions by listing and matching topics."""
        import fnmatch

        subscriber = self._get_subscriber()
        try:
            response = await subscriber.list_subscriptions(
                project=f"projects/{self._project_id}"
            )
        except Exception:
            await asyncio.sleep(1.0)
            return

        pattern_id = _topic_to_pubsub_name(sub.topic, self._topic_prefix)
        async for sub_resource in response:
            topic_path: str = sub_resource.topic
            topic_id = topic_path.split("/")[-1]
            if fnmatch.fnmatch(topic_id, pattern_id):
                kutana_topic = topic_id.removeprefix(self._topic_prefix)
                effective_group = sub.group or sub.subscription_id[:16]
                cache_key = f"{kutana_topic}::{effective_group}"
                if cache_key not in self._sub_paths:
                    await self._get_or_create_subscription(
                        kutana_topic, effective_group
                    )
                sub_path = self._sub_paths.get(cache_key)
                if sub_path:
                    await self._pull_and_dispatch(sub, sub_path)

    async def _pull_and_dispatch(
        self, sub: Subscription, sub_path: str
    ) -> None:
        """Synchronously pull messages from Pub/Sub and dispatch them.

        Args:
            sub: The active subscription.
            sub_path: The full Pub/Sub subscription path.
        """
        subscriber = self._get_subscriber()
        response = await subscriber.pull(
            subscription=sub_path,
            max_messages=self._max_messages,
        )
        ack_ids: list[str] = []
        for received in response.received_messages:
            ack_id: str = received.ack_id
            data_bytes: bytes = received.message.data
            try:
                body = json.loads(data_bytes.decode("utf-8"))
                message = Message(
                    id=body.get("message_id", str(uuid4())),
                    topic=body.get("topic", sub.topic),
                    payload=body.get("payload", {}),
                    metadata=body.get("metadata", {}),
                    source=body.get("source", ""),
                )
                await sub.handler(message)
                ack_ids.append(ack_id)
            except Exception:
                logger.exception("Error dispatching PubSub message from %s", sub_path)

        if ack_ids:
            # Auto-acknowledge processed messages (caller can also use ack())
            try:
                await subscriber.acknowledge(
                    subscription=sub_path, ack_ids=ack_ids
                )
            except Exception:
                logger.exception("PubSub auto-ack failed for %s", sub_path)
