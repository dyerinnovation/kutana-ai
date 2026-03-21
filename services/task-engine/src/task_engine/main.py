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
from task_engine.windower import DEFAULT_OVERLAP_SECONDS, DEFAULT_WINDOW_SECONDS, SegmentWindower

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from convene_core.models.transcript import TranscriptSegment
    from task_engine.windower import SegmentWindow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TaskEngineSettings(BaseSettings):
    """Task engine configuration from environment variables.

    Attributes:
        database_url: Async PostgreSQL connection string.
        redis_url: Redis connection string.
        extraction_window_seconds: Transcript window size for LLM extraction.
        extraction_overlap_seconds: Overlap between consecutive extraction windows.
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
    extraction_window_seconds: float = DEFAULT_WINDOW_SECONDS
    extraction_overlap_seconds: float = DEFAULT_OVERLAP_SECONDS
    consumer_group: str = "task-engine"
    consumer_name: str = ""


# ---------------------------------------------------------------------------
# Window handler (stub — LLM extraction wired in next phase)
# ---------------------------------------------------------------------------


async def _on_window(window: SegmentWindow) -> None:
    """Handle a completed transcript window ready for task extraction.

    This is a thin logging stub for Phase 1D.  The full LLM-powered
    extraction pipeline (windowing → LLM → dedup → persist) will be
    wired in the next task (Complete LLM-powered task extraction pipeline).

    Args:
        window: A time-bounded batch of transcript segments.
    """
    logger.info(
        "Window ready for extraction: meeting=%s window=%.1f–%.1fs "
        "segments=%d is_final=%s",
        window.meeting_id,
        window.window_start,
        window.window_end,
        len(window.segments),
        window.is_final,
    )


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

_consumer: StreamConsumer | None = None
_consumer_task: asyncio.Task[None] | None = None
_windower: SegmentWindower | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Creates a :class:`~task_engine.windower.SegmentWindower` and a
    :class:`~task_engine.stream_consumer.StreamConsumer`.  Segments
    received from Redis are forwarded to the windower, which emits
    :class:`~task_engine.windower.SegmentWindow` batches once enough
    transcript has accumulated.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to the ASGI server while the app is running.
    """
    global _consumer, _consumer_task, _windower

    settings = TaskEngineSettings()
    logger.info(
        "task-engine starting up (window=%.0fs, overlap=%.0fs)",
        settings.extraction_window_seconds,
        settings.extraction_overlap_seconds,
    )

    _windower = SegmentWindower(
        on_window=_on_window,
        window_size_seconds=settings.extraction_window_seconds,
        overlap_seconds=settings.extraction_overlap_seconds,
    )

    async def _on_segment(segment: TranscriptSegment) -> None:
        """Route an incoming segment into the windower.

        Args:
            segment: Finalized transcript segment from the Redis Stream.
        """
        assert _windower is not None
        logger.debug(
            "Buffering segment: meeting=%s speaker=%s text=%.80r",
            segment.meeting_id,
            segment.speaker_id,
            segment.text,
        )
        await _windower.add_segment(segment)

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
        _windower = None


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
