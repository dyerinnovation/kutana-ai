"""FastAPI application entry point for the Convene AI task engine."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING

from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from task_engine.stream_consumer import StreamConsumer

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from convene_core.models.transcript import TranscriptSegment

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TaskEngineSettings(BaseSettings):
    """Task engine configuration from environment variables.

    Attributes:
        database_url: Async PostgreSQL connection string.
        redis_url: Redis connection string.
        extraction_window_seconds: Transcript buffer window for extraction.
        consumer_group: Redis consumer group name.
        consumer_name: Unique name for this consumer instance within the group.
            If empty, defaults to ``worker-<hostname>``.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://convene:convene@localhost:5432/convene"
    redis_url: str = "redis://localhost:6379/0"
    extraction_window_seconds: int = 180
    consumer_group: str = "task-engine"
    consumer_name: str = ""


# ---------------------------------------------------------------------------
# Segment handler
# ---------------------------------------------------------------------------


async def _on_segment(segment: TranscriptSegment) -> None:
    """Handle a single finalized transcript segment from the stream.

    In Phase 1D this is a thin receiver that logs the incoming segment.
    The full extraction pipeline (windowing → LLM → dedup → persist) will
    be wired in subsequent tasks.

    Args:
        segment: Finalized transcript segment from the Redis Stream.
    """
    logger.info(
        "Received transcript segment: meeting=%s speaker=%s text=%.80r",
        segment.meeting_id,
        segment.speaker_id,
        segment.text,
    )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

_consumer: StreamConsumer | None = None
_consumer_task: asyncio.Task[None] | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Creates a :class:`~task_engine.stream_consumer.StreamConsumer`, starts
    it as a background task on startup, and cancels it cleanly on shutdown.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to the ASGI server while the app is running.
    """
    global _consumer, _consumer_task

    settings = TaskEngineSettings()
    logger.info("task-engine starting up")

    _consumer = StreamConsumer(
        redis_url=settings.redis_url,
        on_segment=_on_segment,
        group_name=settings.consumer_group,
        consumer_name=settings.consumer_name or None,
    )
    _consumer_task = asyncio.create_task(_consumer.start())

    try:
        yield
    finally:
        logger.info("task-engine shutting down")
        if _consumer is not None:
            await _consumer.stop()
        if _consumer_task is not None:
            _consumer_task.cancel()
            with suppress(asyncio.CancelledError):
                await _consumer_task
        _consumer = None
        _consumer_task = None


app = FastAPI(
    title="Convene AI Task Engine",
    description="LLM-powered task extraction from meeting transcripts",
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
    """Return the health status of the task engine.

    Returns:
        HealthResponse with status and service name.
    """
    return HealthResponse(status="healthy", service="task-engine")
