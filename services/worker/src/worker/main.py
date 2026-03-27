"""FastAPI application entry point for the Convene AI worker service."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database setup (shared with feed consumers)
# ---------------------------------------------------------------------------

_DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://convene:convene@localhost:5432/convene",
)
_REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
_CONVENE_MCP_URL = os.environ.get("CONVENE_MCP_URL", "http://localhost:3001/mcp")
_CONVENE_MCP_TOKEN = os.environ.get("CONVENE_MCP_TOKEN", "")

_engine = create_async_engine(_DATABASE_URL, pool_pre_ping=True)
_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    _engine, class_=AsyncSession, expire_on_commit=False
)

# Background tasks for stream consumers
_background_tasks: list[asyncio.Task[None]] = []


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Starts FeedDispatcher and FeedRunner as background tasks on startup
    and gracefully stops them on shutdown.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to the ASGI server while the app is running.
    """
    logger.info("worker starting up")

    # Start feed consumers
    from worker.feed_dispatcher import FeedDispatcher
    from worker.feed_runner import FeedRunner

    dispatcher = FeedDispatcher(
        redis_url=_REDIS_URL,
        session_factory=_session_factory,
    )
    runner = FeedRunner(
        redis_url=_REDIS_URL,
        session_factory=_session_factory,
        convene_mcp_url=_CONVENE_MCP_URL,
        convene_mcp_token=_CONVENE_MCP_TOKEN,
    )

    dispatcher_task = asyncio.create_task(dispatcher.start(), name="feed-dispatcher")
    runner_task = asyncio.create_task(runner.start(), name="feed-runner")
    _background_tasks.extend([dispatcher_task, runner_task])

    logger.info("Feed consumers started: FeedDispatcher + FeedRunner")

    yield

    logger.info("worker shutting down — stopping feed consumers")
    await dispatcher.stop()
    await runner.stop()

    # Cancel tasks if they haven't exited yet
    for task in _background_tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*_background_tasks, return_exceptions=True)
    _background_tasks.clear()

    logger.info("worker shut down")


app = FastAPI(
    title="Convene AI Worker",
    description="Background worker for feed dispatch, notifications, and integrations",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response model for the health check endpoint.

    Attributes:
        status: Current health status of the service.
        service: Name of the service reporting health.
    """

    status: str
    service: str


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return the health status of the worker service.

    Returns:
        HealthResponse with status and service name.
    """
    return HealthResponse(status="healthy", service="worker")
