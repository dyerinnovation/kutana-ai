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

    Starts the MeetingEventRelay, PresenceMaterializer, and
    PresenceReconciler background tasks for the Phase A.7 decoupled
    managed-agent lifecycle, and shuts them down gracefully on exit.

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

    # Start the meeting event relay + presence heartbeat if Anthropic
    # API key is configured. The relay handles meeting.ended shutdown,
    # the materializer maintains the presence Redis set from the shared
    # kutana:events stream, and the reconciler periodically warms /
    # shuts down managed agent sessions based on live participant count.
    relay_task: asyncio.Task[None] | None = None
    relay = None
    materializer_task: asyncio.Task[None] | None = None
    materializer = None
    reconciler_task: asyncio.Task[None] | None = None
    reconciler = None
    reconciler_redis = None

    if settings.anthropic_api_key:
        from redis.asyncio import Redis

        from api_server.agent_lifecycle import MeetingEventRelay
        from api_server.agent_presence_heartbeat import (
            PresenceMaterializer,
            PresenceReconciler,
        )
        from api_server.deps import _build_session_factory
        from api_server.event_publisher import EventPublisher

        db_factory = _build_session_factory(settings)
        relay = MeetingEventRelay(
            redis_url=settings.redis_url,
            api_key=settings.anthropic_api_key,
            db_factory=db_factory,
        )
        relay_task = asyncio.create_task(relay.start())
        logger.info("MeetingEventRelay started")

        materializer = PresenceMaterializer(redis_url=settings.redis_url)
        materializer_task = asyncio.create_task(materializer.start())
        logger.info("PresenceMaterializer started")

        # Dedicated Redis client for the reconciler's event publisher —
        # separate from the materializer's XREADGROUP connection so a
        # publish error can't stall the consume loop.
        reconciler_redis = Redis.from_url(  # type: ignore[type-arg]
            settings.redis_url,
            decode_responses=True,
        )
        reconciler = PresenceReconciler(
            db_factory=db_factory,
            settings=settings,
            publisher=EventPublisher(reconciler_redis),
            redis_url=settings.redis_url,
        )
        reconciler_task = asyncio.create_task(reconciler.start())
        logger.info("PresenceReconciler started")
    else:
        logger.info("ANTHROPIC_API_KEY not set — MeetingEventRelay and presence heartbeat disabled")

    yield

    # Shutdown — reverse start order so nothing tries to publish into
    # a Redis client that has already been closed.
    if reconciler is not None:
        await reconciler.stop()
    if reconciler_task is not None:
        reconciler_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reconciler_task
    if reconciler_redis is not None:
        with contextlib.suppress(Exception):
            await reconciler_redis.aclose()

    if materializer is not None:
        await materializer.stop()
    if materializer_task is not None:
        materializer_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await materializer_task

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
