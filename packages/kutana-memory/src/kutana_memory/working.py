"""Working memory layer backed by Redis.

Provides fast key-value storage per active meeting using Redis hashes.
Designed for ephemeral state that lives only while a meeting is active.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import redis.asyncio as aioredis

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)

_KEY_PREFIX = "kutana:working:"


def _meeting_key(meeting_id: UUID) -> str:
    """Build the Redis hash key for a meeting's working memory.

    Args:
        meeting_id: The meeting UUID.

    Returns:
        The Redis key string.
    """
    return f"{_KEY_PREFIX}{meeting_id}"


class WorkingMemory:
    """Redis-backed working memory for active meetings.

    Each meeting gets its own Redis hash. Keys within the hash are
    arbitrary strings (e.g., "current_speaker", "transcript_buffer").
    Data is ephemeral and should be cleared when the meeting ends.
    """

    def __init__(self, redis_url: str) -> None:
        """Initialize working memory with a Redis connection.

        Args:
            redis_url: Redis connection URL (e.g., redis://localhost:6379/0).
        """
        self._redis: aioredis.Redis = aioredis.from_url(  # type: ignore[assignment]
            redis_url,
            decode_responses=True,
        )

    async def store(self, meeting_id: UUID, key: str, value: str) -> None:
        """Store a key-value pair in a meeting's working memory.

        Args:
            meeting_id: The meeting to store data for.
            key: The field name within the meeting's hash.
            value: The string value to store.
        """
        redis_key = _meeting_key(meeting_id)
        await self._redis.hset(redis_key, key, value)  # type: ignore[arg-type]
        logger.debug(
            "Stored working memory: %s[%s]",
            redis_key,
            key,
        )

    async def retrieve(self, meeting_id: UUID, key: str) -> str | None:
        """Retrieve a value from a meeting's working memory.

        Args:
            meeting_id: The meeting to retrieve data from.
            key: The field name to look up.

        Returns:
            The stored string value, or None if the key does not exist.
        """
        redis_key = _meeting_key(meeting_id)
        value: str | None = await self._redis.hget(redis_key, key)  # type: ignore[assignment]
        return value

    async def get_all(self, meeting_id: UUID) -> dict[str, str]:
        """Retrieve all key-value pairs for a meeting's working memory.

        Args:
            meeting_id: The meeting to retrieve data from.

        Returns:
            Dictionary of all stored key-value pairs. Empty dict if
            no data exists.
        """
        redis_key = _meeting_key(meeting_id)
        data: dict[str, str] = await self._redis.hgetall(redis_key)  # type: ignore[assignment]
        return data

    async def clear(self, meeting_id: UUID) -> None:
        """Remove all working memory for a meeting.

        Should be called when a meeting ends to free Redis memory.

        Args:
            meeting_id: The meeting whose working memory to clear.
        """
        redis_key = _meeting_key(meeting_id)
        await self._redis.delete(redis_key)
        logger.info(
            "Cleared working memory for meeting %s.",
            meeting_id,
        )

    async def close(self) -> None:
        """Close the Redis connection."""
        await self._redis.aclose()
