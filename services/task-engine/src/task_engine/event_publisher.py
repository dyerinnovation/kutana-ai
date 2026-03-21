"""Redis Streams event publisher for task-engine domain events."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

import redis.asyncio as redis

if TYPE_CHECKING:
    from convene_core.events.definitions import BaseEvent
    from convene_core.extraction.types import ExtractionResult

logger = logging.getLogger(__name__)

STREAM_KEY = "convene:events"
MAX_STREAM_LEN = 10_000


class EventPublisher:
    """Publishes BaseEvent instances to a Redis Stream.

    Each event is serialized to a stream entry with fields
    ``event_type`` and ``payload`` (JSON string).

    Attributes:
        _redis: Async Redis client connection.
    """

    def __init__(self, redis_url: str) -> None:
        """Initialise the publisher with a Redis connection.

        Args:
            redis_url: Redis connection URL (e.g. ``redis://localhost:6379/0``).
        """
        self._redis: redis.Redis[str] = redis.from_url(
            redis_url, decode_responses=True
        )

    async def publish(self, event: BaseEvent) -> str:
        """Publish a domain event to the Redis Stream.

        Args:
            event: A BaseEvent instance to publish.

        Returns:
            The Redis stream entry ID.
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

    async def publish_insights(
        self,
        meeting_id: str,
        result: ExtractionResult,
    ) -> None:
        """Publish an extraction result to meeting insights pub/sub channels.

        Publishes the full result to ``meeting.{meeting_id}.insights`` and
        per-entity-type payloads to ``meeting.{meeting_id}.insights.{entity_type}``.

        Args:
            meeting_id: The meeting UUID as a string.
            result: The deduplicated ExtractionResult to publish.
        """
        base_topic = f"meeting.{meeting_id}.insights"
        payload = json.dumps(result.model_dump(mode="json"), default=str)
        await self._redis.publish(base_topic, payload)

        by_type: dict[str, list[Any]] = {}
        for entity in result.entities:
            by_type.setdefault(entity.entity_type, []).append(
                entity.model_dump(mode="json")
            )

        for entity_type, entities in by_type.items():
            await self._redis.publish(
                f"{base_topic}.{entity_type}",
                json.dumps(
                    {"batch_id": result.batch_id, "entities": entities},
                    default=str,
                ),
            )

        logger.info(
            "Published %d entities to %s",
            len(result.entities),
            base_topic,
        )

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._redis.aclose()
