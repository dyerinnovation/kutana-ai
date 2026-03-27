"""Per-agent, per-tool Redis sliding-window rate limiter.

Follows the portable provider-abstraction pattern used elsewhere in Convene AI.
The abstract base class (RateLimiter) can be swapped for testing or alternative
backends without changing callers.

Redis key pattern:
    convene:rate_limit:{agent_id}:{tool_name}   ZSET (score = unix timestamp)

Default per-tool limits (requests / minute):
    raise_hand              10
    send_chat_message       20
    publish_to_channel      20
    get_transcript          30
    get_chat_messages       30
    *                       60  (global default)
"""

from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from uuid import UUID

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-tool limits (requests per window)
# ---------------------------------------------------------------------------

TOOL_RATE_LIMITS: dict[str, tuple[int, int]] = {
    # tool_name: (max_requests, window_seconds)
    "raise_hand": (10, 60),
    "send_chat_message": (20, 60),
    "publish_to_channel": (20, 60),
    "get_transcript": (30, 60),
    "get_summary": (10, 60),
    "set_context": (10, 60),
    "get_chat_messages": (30, 60),
    "get_meeting_events": (30, 60),
    "get_channel_messages": (30, 60),
}

_DEFAULT_LIMIT = (60, 60)  # 60 req / 60 sec for unlisted tools


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------


class RateLimiter(ABC):
    """Abstract rate limiter interface."""

    @abstractmethod
    async def check(
        self,
        agent_id: UUID,
        tool_name: str,
    ) -> tuple[bool, int]:
        """Check whether *agent_id* may call *tool_name* right now.

        Increments the counter when the request is allowed.

        Args:
            agent_id: The agent's config UUID (from the MCP JWT).
            tool_name: The tool being invoked.

        Returns:
            ``(allowed, retry_after_seconds)`` — when *allowed* is False,
            callers should return a 429-style error and wait *retry_after_seconds*.
        """
        ...

    def error_response(self, tool_name: str, retry_after: int) -> str:
        """Build a JSON error string for a rate-limit rejection.

        Args:
            tool_name: The throttled tool name.
            retry_after: Seconds to wait before retrying.

        Returns:
            JSON string with ``error`` and ``retry_after`` keys.
        """
        return json.dumps({
            "error": "rate_limit_exceeded",
            "message": (
                f"Too many calls to '{tool_name}'. "
                f"Retry after {retry_after} seconds."
            ),
            "retry_after_seconds": retry_after,
        })


# ---------------------------------------------------------------------------
# Redis implementation
# ---------------------------------------------------------------------------


class RedisRateLimiter(RateLimiter):
    """Sliding-window rate limiter backed by Redis sorted sets.

    Each (agent_id, tool_name) pair gets its own ZSET. Members are
    ``str(timestamp)`` scored by the same timestamp, allowing O(log N)
    range queries to count requests in the current window.

    Args:
        redis_url: Redis connection URL.
    """

    def __init__(self, redis_url: str = "redis://localhost:6379/0") -> None:
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None  # type: ignore[type-arg]

    async def _get_redis(self) -> aioredis.Redis:  # type: ignore[type-arg]
        if self._redis is None:
            self._redis = aioredis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    async def check(
        self,
        agent_id: UUID,
        tool_name: str,
    ) -> tuple[bool, int]:
        """Sliding-window check and increment.

        Args:
            agent_id: Agent config UUID.
            tool_name: Tool being invoked.

        Returns:
            ``(allowed, retry_after_seconds)``
        """
        max_requests, window_seconds = TOOL_RATE_LIMITS.get(
            tool_name, _DEFAULT_LIMIT
        )

        r = await self._get_redis()
        key = f"convene:rate_limit:{agent_id}:{tool_name}"
        now = time.time()
        window_start = now - window_seconds

        try:
            pipe = r.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)   # drop expired
            pipe.zadd(key, {str(now): now})               # record this call
            pipe.zcard(key)                               # count in window
            pipe.expire(key, window_seconds + 1)          # auto-expire key
            results = await pipe.execute()

            count: int = results[2]

            if count > max_requests:
                logger.warning(
                    "rate_limit_exceeded agent_id=%s tool=%s count=%d limit=%d",
                    agent_id,
                    tool_name,
                    count,
                    max_requests,
                )
                return False, window_seconds

            return True, 0

        except Exception:
            # Redis unavailable — allow through rather than blocking legitimate use
            logger.warning("rate_limiter Redis error — allowing request through")
            return True, 0


# ---------------------------------------------------------------------------
# No-op implementation (for testing)
# ---------------------------------------------------------------------------


class NoOpRateLimiter(RateLimiter):
    """Rate limiter that always allows every request (use in tests)."""

    async def check(self, agent_id: UUID, tool_name: str) -> tuple[bool, int]:
        return True, 0
