"""FastAPI application entry point for the Kutana AI API server."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI

from api_server.deps import get_settings
from api_server.middleware import setup_cors
from api_server.observability import setup_logging, setup_prometheus, setup_sentry
from api_server.rate_limit import RateLimitMiddleware
from api_server.request_id import RequestIdMiddleware
from api_server.routes.agent_keys import router as agent_keys_router
from api_server.routes.agent_templates import router as agent_templates_router
from api_server.routes.agents import router as agents_router
from api_server.routes.auth import router as auth_router
from api_server.routes.billing import router as billing_router
from api_server.routes.feeds import router as feeds_router
from api_server.routes.health import router as health_router
from api_server.routes.integrations import router as integrations_router
from api_server.routes.meetings import router as meetings_router
from api_server.routes.summaries import router as summaries_router
from api_server.routes.tasks import router as tasks_router
from api_server.routes.token import router as token_router
from api_server.routes.turns import router as turns_router

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

# Initialise observability before anything else
_settings = get_settings()
setup_logging(log_format=_settings.log_format)
setup_sentry(dsn=_settings.sentry_dsn, service_name="api-server")

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Starts the MeetingEventRelay background task for managed agent
    lifecycle wiring, and shuts it down gracefully on exit.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to the ASGI server while the app is running.
    """
    logger.info("api-server starting up")

    # Initialise Langfuse if keys are configured
    settings = get_settings()
    if settings.langfuse_secret_key and settings.langfuse_public_key:
        from api_server.langfuse_client import init_langfuse

        init_langfuse(
            secret_key=settings.langfuse_secret_key,
            public_key=settings.langfuse_public_key,
            host=settings.langfuse_host,
        )
    else:
        logger.info("LANGFUSE keys not set — Langfuse tracing disabled")

    # Start the meeting event relay if Anthropic API key is configured
    relay_task: asyncio.Task[None] | None = None
    relay = None

    if settings.anthropic_api_key:
        from api_server.agent_lifecycle import MeetingEventRelay
        from api_server.deps import _build_session_factory

        db_factory = _build_session_factory(settings)
        relay = MeetingEventRelay(
            redis_url=settings.redis_url,
            api_key=settings.anthropic_api_key,
            db_factory=db_factory,
        )
        relay_task = asyncio.create_task(relay.start())
        logger.info("MeetingEventRelay started")
    else:
        logger.info("ANTHROPIC_API_KEY not set — MeetingEventRelay disabled")

    yield

    # Shutdown
    if relay is not None:
        await relay.stop()
    if relay_task is not None:
        relay_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await relay_task

    # Flush Langfuse
    from api_server.langfuse_client import flush_langfuse

    flush_langfuse()

    logger.info("api-server shutting down")


app = FastAPI(
    title="Kutana AI API",
    description=("REST and WebSocket API for the Kutana AI meeting assistant"),
    version="0.1.0",
    lifespan=lifespan,
)

setup_cors(app)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(RateLimitMiddleware)
setup_prometheus(app)

app.include_router(health_router)
app.include_router(auth_router, prefix="/v1")
app.include_router(billing_router, prefix="/v1")
app.include_router(meetings_router, prefix="/v1")
app.include_router(tasks_router, prefix="/v1")
app.include_router(agents_router, prefix="/v1")
app.include_router(agent_keys_router, prefix="/v1")
app.include_router(agent_templates_router, prefix="/v1")
app.include_router(feeds_router, prefix="/v1")
app.include_router(integrations_router, prefix="/v1")
app.include_router(summaries_router, prefix="/v1")
app.include_router(token_router, prefix="/v1")
app.include_router(turns_router, prefix="/v1")
