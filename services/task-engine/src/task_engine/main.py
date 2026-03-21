"""FastAPI application entry point for the Convene AI task engine."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict

from convene_core.database.models import TaskORM
from convene_core.database.session import create_engine, create_session_factory
from convene_core.extraction.types import (
    AnyExtractedEntity,
    BatchSegment,
    ExtractionResult,
    TranscriptBatch,
)
from convene_providers.extraction.llm_extractor import LLMExtractor
from task_engine.event_publisher import EventPublisher
from task_engine.stream_consumer import StreamConsumer
from task_engine.windower import DEFAULT_OVERLAP_SECONDS, DEFAULT_WINDOW_SECONDS, SegmentWindower

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from convene_core.models.transcript import TranscriptSegment
    from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
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
        anthropic_api_key: Anthropic API key for LLM extraction.
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
    anthropic_api_key: str = ""
    extraction_window_seconds: float = DEFAULT_WINDOW_SECONDS
    extraction_overlap_seconds: float = DEFAULT_OVERLAP_SECONDS
    consumer_group: str = "task-engine"
    consumer_name: str = ""


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_consumer: StreamConsumer | None = None
_consumer_task: asyncio.Task[None] | None = None
_windower: SegmentWindower | None = None
_event_publisher: EventPublisher | None = None
_llm_extractor: LLMExtractor | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_db_engine: AsyncEngine | None = None

# Per-meeting in-memory content-key dedup: meeting_id -> set of seen keys
_seen_keys: dict[UUID, set[str]] = {}


# ---------------------------------------------------------------------------
# Extraction helpers
# ---------------------------------------------------------------------------


async def _persist_task_entities(
    entities: list[AnyExtractedEntity],
    meeting_id: UUID,
) -> None:
    """Persist TaskEntity objects to the tasks table.

    Silently skips on any database error so the service degrades
    gracefully when PostgreSQL is unavailable.

    Args:
        entities: All deduplicated entities from the extraction result.
        meeting_id: UUID of the meeting these entities belong to.
    """
    if _session_factory is None:
        return

    task_entities = [e for e in entities if e.entity_type == "task"]
    if not task_entities:
        return

    try:
        async with _session_factory() as session:
            for entity in task_entities:
                orm = TaskORM(
                    id=uuid4(),
                    meeting_id=meeting_id,
                    description=getattr(entity, "title", str(entity.id)),
                    priority=getattr(entity, "priority", "medium"),
                    status="pending",
                    source_utterance=getattr(entity, "source_segment_id", None),
                )
                session.add(orm)
            await session.commit()
        logger.info(
            "Persisted %d tasks to DB for meeting %s",
            len(task_entities),
            meeting_id,
        )
    except Exception:
        logger.warning(
            "Could not persist tasks to DB for meeting %s — skipping (graceful fallback)",
            meeting_id,
        )


# ---------------------------------------------------------------------------
# Window handler
# ---------------------------------------------------------------------------


async def _on_window(window: SegmentWindow) -> None:
    """Handle a completed transcript window: extract, dedup, publish, and persist.

    Args:
        window: A time-bounded batch of transcript segments ready for extraction.
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

    if not _llm_extractor:
        logger.debug("LLM extractor not configured — set ANTHROPIC_API_KEY to enable")
        if window.is_final:
            _seen_keys.pop(window.meeting_id, None)
        return

    # Build TranscriptBatch from window segments
    batch_segments = [
        BatchSegment(
            segment_id=str(s.id),
            speaker=s.speaker_id,
            text=s.text,
            start_time=s.start_time,
            end_time=s.end_time,
        )
        for s in window.segments
    ]
    batch = TranscriptBatch(
        meeting_id=str(window.meeting_id),
        segments=batch_segments,
        batch_window_seconds=window.duration,
    )

    # Call LLM extractor
    try:
        result = await _llm_extractor.extract(batch)
    except Exception:
        logger.exception("LLM extraction failed for meeting %s", window.meeting_id)
        if window.is_final:
            _seen_keys.pop(window.meeting_id, None)
        return

    if not result.entities:
        logger.info("No entities extracted for meeting %s", window.meeting_id)
        if window.is_final:
            _seen_keys.pop(window.meeting_id, None)
        return

    # In-memory dedup using content_key()
    meeting_seen = _seen_keys.setdefault(window.meeting_id, set())
    unique: list[AnyExtractedEntity] = []
    for entity in result.entities:
        key = entity.content_key()
        if not key or key not in meeting_seen:
            if key:
                meeting_seen.add(key)
            unique.append(entity)

    logger.info(
        "Extracted %d entities (%d unique after dedup) for meeting %s",
        len(result.entities),
        len(unique),
        window.meeting_id,
    )
    for entity in unique:
        label = entity.content_key() or str(entity.id)[:8]
        logger.info("  [%s] %s", entity.entity_type, label[:80])

    # Publish to Redis on meeting.{meeting_id}.insights
    if _event_publisher and unique:
        deduped_result = ExtractionResult(
            batch_id=result.batch_id,
            entities=unique,
            processing_time_ms=result.processing_time_ms,
        )
        try:
            await _event_publisher.publish_insights(str(window.meeting_id), deduped_result)
        except Exception:
            logger.exception(
                "Failed to publish insights for meeting %s", window.meeting_id
            )

    # Persist tasks to PostgreSQL (graceful fallback)
    await _persist_task_entities(unique, window.meeting_id)

    # Clean up dedup state for final window
    if window.is_final:
        _seen_keys.pop(window.meeting_id, None)


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Initialises the LLM extractor (if ANTHROPIC_API_KEY is set), a
    database session factory, a :class:`~task_engine.windower.SegmentWindower`,
    a :class:`~task_engine.event_publisher.EventPublisher`, and a
    :class:`~task_engine.stream_consumer.StreamConsumer`.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to the ASGI server while the app is running.
    """
    global _consumer, _consumer_task, _windower, _event_publisher
    global _llm_extractor, _session_factory, _db_engine

    settings = TaskEngineSettings()
    logger.info(
        "task-engine starting up (window=%.0fs, overlap=%.0fs)",
        settings.extraction_window_seconds,
        settings.extraction_overlap_seconds,
    )

    # LLM extractor — requires ANTHROPIC_API_KEY
    if settings.anthropic_api_key:
        _llm_extractor = LLMExtractor(api_key=settings.anthropic_api_key)
        logger.info("LLM extractor initialized (model=claude-sonnet-4-20250514)")
    else:
        logger.warning(
            "ANTHROPIC_API_KEY not set — LLM extraction disabled. "
            "Set ANTHROPIC_API_KEY to enable entity extraction."
        )

    # Database session factory (connection errors surface when first used)
    _db_engine = create_engine(settings.database_url)
    _session_factory = create_session_factory(_db_engine)

    _event_publisher = EventPublisher(redis_url=settings.redis_url)

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
        if _event_publisher is not None:
            await _event_publisher.close()
        if _llm_extractor is not None:
            await _llm_extractor.close()
        if _db_engine is not None:
            await _db_engine.dispose()
        _consumer = None
        _consumer_task = None
        _windower = None
        _event_publisher = None
        _llm_extractor = None
        _session_factory = None
        _db_engine = None
        _seen_keys.clear()


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
