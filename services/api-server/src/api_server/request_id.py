"""X-Request-ID middleware for request tracing."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

import structlog
from starlette.middleware.base import BaseHTTPMiddleware

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Propagate or generate an X-Request-ID header on every request.

    If the incoming request carries an ``X-Request-ID`` header the value
    is reused; otherwise a new UUID is generated. The ID is bound to
    structlog's context vars so all log entries within the request
    automatically include it.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: ...) -> Response:
        """Add request ID to response headers and logging context.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            The HTTP response with X-Request-ID header attached.
        """
        request_id = request.headers.get("x-request-id") or str(uuid4())

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )

        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
