"""Redis pub/sub notification service."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from redis.asyncio import Redis

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class NotificationService:
    """Provides event subscription and notification publishing via Redis.

    Uses Redis pub/sub for real-time event distribution between
    services and connected clients.

    Attributes:
        _redis_url: Redis connection string.
        _redis: Lazily initialised Redis client.
    """

    def __init__(self, redis_url: str) -> None:
        """Initialise the notification service.

        Args:
            redis_url: Redis connection URL.
        """
        self._redis_url = redis_url
        self._redis: Redis | None = None  # type: ignore[type-arg]  # redis-py stubs incomplete

    async def _get_client(self) -> Redis:  # type: ignore[type-arg]  # redis-py stubs incomplete
        """Return or create the async Redis client.

        Returns:
            An initialised Redis async client.
        """
        if self._redis is None:
            self._redis = Redis.from_url(  # type: ignore[assignment]  # redis-py stubs incomplete
                self._redis_url,
                decode_responses=True,
            )
        return self._redis

    async def subscribe_events(
        self,
        event_types: list[str],
    ) -> AsyncIterator[dict[str, Any]]:
        """Subscribe to one or more Redis pub/sub channels.

        Each event type maps to a Redis channel name.  Incoming
        messages are expected to be JSON-encoded dictionaries.

        Args:
            event_types: List of channel names to subscribe to
                (e.g. ``["task.created", "meeting.ended"]``).

        Yields:
            Parsed JSON event dictionaries as they arrive.
        """
        client = await self._get_client()
        pubsub = client.pubsub()
        await pubsub.subscribe(*event_types)

        logger.info(
            "Subscribed to event channels: %s",
            ", ".join(event_types),
        )

        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue

                data = message.get("data")
                if isinstance(data, str):
                    try:
                        event = json.loads(data)
                        yield event
                    except json.JSONDecodeError:
                        logger.warning(
                            "Non-JSON message on channel %s: %s",
                            message.get("channel"),
                            data[:100],
                        )
        finally:
            await pubsub.unsubscribe(*event_types)
            await pubsub.aclose()

    async def publish_notification(
        self,
        channel: str,
        message: str,
    ) -> None:
        """Publish a message to a Redis pub/sub channel.

        Args:
            channel: The Redis channel to publish to.
            message: The JSON-encoded message string.
        """
        client = await self._get_client()
        receivers = await client.publish(channel, message)
        logger.debug(
            "Published to channel %s (%d receivers)",
            channel,
            receivers,
        )

    async def close(self) -> None:
        """Close the underlying Redis connection."""
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
