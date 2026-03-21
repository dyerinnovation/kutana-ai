"""Batch collector service for the Meeting Insight Stream pipeline.

Subscribes to the transcript topic for a meeting, buffers segments in a
rolling time window, and dispatches extraction batches to registered
extractors when the window closes.  Extracted entities are published back
to the message bus under per-meeting insight topics.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from convene_core.extraction.types import (
    BatchSegment,
    ExtractionResult,
    TranscriptBatch,
)
from convene_core.models.transcript import TranscriptSegment

if TYPE_CHECKING:
    from convene_core.extraction.abc import Extractor
    from convene_core.messaging.abc import MessageBus
    from convene_core.messaging.types import Message, Subscription

logger = logging.getLogger(__name__)


class BatchCollector:
    """Collects transcript segments into timed batches for entity extraction.

    Subscribes to ``meeting.{meeting_id}.transcript``, buffers incoming
    segments, and flushes a ``TranscriptBatch`` to all registered extractors
    once the configured window elapses.  Extracted entities are published to:

    - ``meeting.{meeting_id}.insights`` — full ``ExtractionResult`` payload
    - ``meeting.{meeting_id}.insights.{entity_type}`` — per-type payloads

    Args:
        bus: The message bus used for subscribe/publish operations.
        meeting_id: ID of the meeting to collect segments for.
        extractors: List of ``Extractor`` instances to run on each batch.
        batch_window_seconds: How long to buffer segments before flushing.
            Defaults to 30 seconds.
    """

    def __init__(
        self,
        bus: MessageBus,
        meeting_id: str,
        extractors: list[Extractor],
        batch_window_seconds: float = 30.0,
    ) -> None:
        """Initialize the batch collector."""
        self._bus = bus
        self._meeting_id = meeting_id
        self._extractors = extractors
        self._batch_window_seconds = batch_window_seconds
        self._buffer: list[BatchSegment] = []
        self._previous_batch: list[BatchSegment] = []
        self._subscription: Subscription | None = None
        self._flush_task: asyncio.Task[None] | None = None
        self._running: bool = False
        self._last_flush: datetime = datetime.now(tz=UTC)

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Subscribe to the transcript topic and start the flush loop."""
        topic = f"meeting.{self._meeting_id}.transcript"
        self._subscription = await self._bus.subscribe(topic, self._on_message)
        self._running = True
        self._last_flush = datetime.now(tz=UTC)
        self._flush_task = asyncio.create_task(
            self._flush_loop(),
            name=f"collector-flush-{self._meeting_id[:8]}",
        )
        logger.info("BatchCollector started for meeting %s", self._meeting_id)

    async def stop(self) -> None:
        """Stop collecting, cancel the flush loop, and perform a final flush."""
        self._running = False

        if self._flush_task is not None:
            self._flush_task.cancel()
            await asyncio.gather(self._flush_task, return_exceptions=True)
            self._flush_task = None

        if self._subscription is not None:
            await self._bus.unsubscribe(self._subscription)
            self._subscription = None

        # Final flush for any remaining buffered segments.
        if self._buffer:
            await self._process_batch()

        logger.info("BatchCollector stopped for meeting %s", self._meeting_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _on_message(self, message: Message) -> None:
        """Handle an incoming transcript message from the bus.

        Args:
            message: The bus message whose payload is a serialised
                ``TranscriptSegment``.
        """
        try:
            segment = TranscriptSegment.model_validate(message.payload)
            batch_seg = BatchSegment(
                segment_id=str(segment.id),
                speaker=segment.speaker_id,
                text=segment.text,
                start_time=segment.start_time,
                end_time=segment.end_time,
            )
            self._buffer.append(batch_seg)
        except Exception:
            logger.exception(
                "BatchCollector: failed to parse transcript message on topic %s",
                message.topic,
            )

    async def _flush_loop(self) -> None:
        """Background loop that flushes the buffer when the window expires."""
        while self._running:
            try:
                await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break

            elapsed = (datetime.now(tz=UTC) - self._last_flush).total_seconds()
            if elapsed >= self._batch_window_seconds and self._buffer:
                await self._process_batch()

    async def _process_batch(self) -> None:
        """Snapshot the buffer, build a ``TranscriptBatch``, and run extractors."""
        if not self._buffer:
            return

        batch = TranscriptBatch(
            meeting_id=self._meeting_id,
            segments=list(self._buffer),
            context_segments=list(self._previous_batch),
            batch_window_seconds=self._batch_window_seconds,
        )
        # Rotate the buffer: current → context, clear buffer
        self._previous_batch = list(self._buffer)
        self._buffer.clear()
        self._last_flush = datetime.now(tz=UTC)

        for extractor in self._extractors:
            try:
                result = await extractor.extract(batch)
                await self._publish_result(result)
            except Exception:
                logger.exception(
                    "Extractor %r failed on batch %s",
                    extractor.name,
                    batch.batch_id,
                )

    async def _publish_result(self, result: ExtractionResult) -> None:
        """Publish an ``ExtractionResult`` to the bus.

        Publishes the full result to the base insights topic, then publishes
        per-entity-type payloads to the typed sub-topics.

        Args:
            result: The extraction result to publish.
        """
        base_topic = f"meeting.{self._meeting_id}.insights"

        # Full result on the base topic
        await self._bus.publish(
            base_topic,
            result.model_dump(mode="json"),
            source="batch-collector",
        )

        # Group entities by type and publish to per-type topics
        by_type: dict[str, list[Any]] = {}
        for entity in result.entities:
            by_type.setdefault(entity.entity_type, []).append(
                entity.model_dump(mode="json")
            )

        for entity_type, entity_dicts in by_type.items():
            await self._bus.publish(
                f"{base_topic}.{entity_type}",
                {
                    "batch_id": result.batch_id,
                    "entities": entity_dicts,
                },
                source="batch-collector",
            )

        logger.debug(
            "Published %d entities from batch %s",
            len(result.entities),
            result.batch_id,
        )
