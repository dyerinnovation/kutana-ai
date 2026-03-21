"""Redis-based rate limiting middleware for API key authenticated requests.

Uses a sliding window counter per API key hash. Requests without
an X-API-Key header are not rate-limited (they use Bearer auth instead).
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import TYPE_CHECKING

from redis.asyncio import Redis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from api_server.deps import get_settings

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Default: 60 requests per minute per API key
DEFAULT_RATE_LIMIT = 60
DEFAULT_WINDOW_SECONDS = 60


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis sliding-window rate limiter keyed by API key hash.

    Attributes:
        rate_limit: Max requests per window.
        window_seconds: Window duration in seconds.
    """

    def __init__(
        self,
        app: ASGIApp,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ) -> None:
        super().__init__(app)
        self.rate_limit = rate_limit
        self.window_seconds = window_seconds

    async def dispatch(self, request: Request, call_next: ...) -> Response:
        """Check rate limit before dispatching the request.

        Args:
            request: The incoming request.
            call_next: The next middleware/handler.

        Returns:
            The response, or 429 if rate-limited.
        """
        api_key = request.headers.get("x-api-key")
        if not api_key:
            return await call_next(request)

        # Use a hash of the key for the Redis key (don't store raw keys)
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()[:16]
        redis_key = f"rate_limit:{key_hash}"

        settings = get_settings()
        try:
            redis: Redis = Redis.from_url(  # type: ignore[assignment]
                settings.redis_url, decode_responses=True
            )
            try:
                now = time.time()
                window_start = now - self.window_seconds

                pipe = redis.pipeline()
                # Remove expired entries
                pipe.zremrangebyscore(redis_key, 0, window_start)
                # Add current request
                pipe.zadd(redis_key, {str(now): now})
                # Count requests in window
                pipe.zcard(redis_key)
                # Set TTL so keys auto-expire
                pipe.expire(redis_key, self.window_seconds + 1)
                results = await pipe.execute()

                request_count = results[2]

                if request_count > self.rate_limit:
                    return JSONResponse(
                        status_code=429,
                        content={
                            "detail": "Rate limit exceeded",
                            "retry_after": self.window_seconds,
                        },
                        headers={
                            "Retry-After": str(self.window_seconds),
                            "X-RateLimit-Limit": str(self.rate_limit),
                            "X-RateLimit-Remaining": "0",
                        },
                    )

                response = await call_next(request)
                response.headers["X-RateLimit-Limit"] = str(self.rate_limit)
                response.headers["X-RateLimit-Remaining"] = str(
                    max(0, self.rate_limit - request_count)
                )
                return response
            finally:
                await redis.aclose()
        except Exception:
            # If Redis is down, allow the request through
            logger.warning("Rate limiting unavailable (Redis error)")
            return await call_next(request)
