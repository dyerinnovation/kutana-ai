"""Redis Streams event publisher for api-server domain events."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from kutana_core.events.definitions import BaseEvent

logger = logging.getLogger(__name__)

STREAM_KEY = "kutana:events"
MAX_STREAM_LEN = 10_000


class EventPublisher:
    """Publishes BaseEvent instances to a Redis Stream.

    Designed for FastAPI dependency injection — accepts a live
    :class:`redis.asyncio.Redis` client rather than a URL so it can
    share the connection provided by :func:`api_server.deps.get_redis`.

    Attributes:
        _redis: Async Redis client provided by the caller.
    """

    def __init__(self, redis_client: Redis) -> None:  # type: ignore[type-arg]
        """Initialise the publisher with a live Redis client.

        Args:
            redis_client: An open async Redis client instance.
        """
        self._redis = redis_client

    async def publish(self, event: BaseEvent) -> str:
        """Publish a domain event to the Redis Stream.

        Args:
            event: A BaseEvent instance to publish.

        Returns:
            The Redis stream entry ID assigned by the server.
        """
        payload = json.dumps(event.to_dict(), default=str)
        entry_id: str = await self._redis.xadd(
            STREAM_KEY,
            {"event_type": event.event_type, "payload": payload},
            maxlen=MAX_STREAM_LEN,
            approximate=True,
        )
        logger.debug(
            "Published event %s: id=%s",
            event.event_type,
            entry_id,
        )
        return entry_id
