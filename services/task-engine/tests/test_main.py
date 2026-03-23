"""Unit tests for task-engine main module — _on_window pipeline orchestration.

All tests use mocked module-level state (LLM extractor, event publisher,
session factory).  No live Redis, LLM, or database connections are made.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

import task_engine.main as main_module
from convene_core.extraction.types import (
    BatchSegment,
    ExtractionResult,
    TaskEntity,
    TranscriptBatch,
)
from convene_core.models.transcript import TranscriptSegment
from task_engine.windower import SegmentWindow

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_segment(
    meeting_id: UUID | None = None,
    start_time: float = 0.0,
    end_time: float = 5.0,
    text: str = "Alice will send the report by Friday.",
) -> TranscriptSegment:
    """Create a minimal TranscriptSegment for testing."""
    return TranscriptSegment(
        meeting_id=meeting_id or uuid4(),
        speaker_id="spk_0",
        text=text,
        start_time=start_time,
        end_time=end_time,
        confidence=0.95,
    )


def _make_window(
    meeting_id: UUID | None = None,
    segments: list[TranscriptSegment] | None = None,
    is_final: bool = False,
    window_start: float = 0.0,
    window_end: float = 180.0,
) -> SegmentWindow:
    """Create a SegmentWindow with sensible defaults."""
    mid = meeting_id or uuid4()
    segs = segments if segments is not None else [_make_segment(meeting_id=mid)]
    return SegmentWindow(
        meeting_id=mid,
        segments=segs,
        window_start=window_start,
        window_end=window_end,
        is_final=is_final,
    )


def _make_task_entity(meeting_id: str, title: str = "Deploy service") -> TaskEntity:
    """Create a TaskEntity for testing."""
    return TaskEntity(
        meeting_id=meeting_id,
        batch_id=str(uuid4()),
        title=title,
    )


def _make_extraction_result(
    entities: list[Any] | None = None,
    batch_id: str | None = None,
) -> ExtractionResult:
    """Create an ExtractionResult for testing."""
    return ExtractionResult(
        batch_id=batch_id or str(uuid4()),
        entities=entities or [],
        processing_time_ms=42.0,
    )


class _MockExtractor:
    """Async mock extractor that returns a configurable result."""

    def __init__(self, result: ExtractionResult) -> None:
        self._result = result
        self.called_with: list[TranscriptBatch] = []

    async def extract(self, batch: TranscriptBatch) -> ExtractionResult:
        """Record the batch and return the preset result."""
        self.called_with.append(batch)
        return self._result

    async def close(self) -> None:
        """No-op close."""


# ---------------------------------------------------------------------------
# _on_window — no extractor configured
# ---------------------------------------------------------------------------


class TestOnWindowNoExtractor:
    """Tests for _on_window when LLM extractor is not configured."""

    async def test_returns_early_when_no_extractor(self) -> None:
        """_on_window is a no-op when _llm_extractor is None."""
        window = _make_window()

        with (
            patch.object(main_module, "_llm_extractor", None),
            patch.object(main_module, "_event_publisher", None),
        ):
            await main_module._on_window(window)
            # No exception raised — test passes

    async def test_final_window_clears_seen_keys_when_no_extractor(self) -> None:
        """Final window removes the meeting's seen_keys entry."""
        mid = uuid4()
        window = _make_window(meeting_id=mid, is_final=True)

        with patch.object(main_module, "_llm_extractor", None):
            main_module._seen_keys[mid] = {"some-key"}
            await main_module._on_window(window)
            assert mid not in main_module._seen_keys

    async def test_final_window_clears_context_cache_when_no_extractor(self) -> None:
        """Final window removes the meeting's context_cache entry."""
        mid = uuid4()
        window = _make_window(meeting_id=mid, is_final=True)
        fake_segs = [BatchSegment(segment_id="s1", text="hi", start_time=0, end_time=1)]

        with patch.object(main_module, "_llm_extractor", None):
            main_module._context_cache[mid] = fake_segs
            await main_module._on_window(window)
            assert mid not in main_module._context_cache


# ---------------------------------------------------------------------------
# _on_window — LLM extraction called with correct batch
# ---------------------------------------------------------------------------


class TestOnWindowBatchConstruction:
    """Tests for TranscriptBatch construction inside _on_window."""

    async def test_batch_uses_window_meeting_id(self) -> None:
        """The batch's meeting_id matches the window's meeting_id."""
        mid = uuid4()
        segs = [_make_segment(meeting_id=mid)]
        window = _make_window(meeting_id=mid, segments=segs)

        mock_result = _make_extraction_result()
        extractor = _MockExtractor(mock_result)

        with (
            patch.object(main_module, "_llm_extractor", extractor),
            patch.object(main_module, "_event_publisher", None),
            patch.object(main_module, "_session_factory", None),
        ):
            await main_module._on_window(window)

        assert len(extractor.called_with) == 1
        assert extractor.called_with[0].meeting_id == str(mid)

    async def test_batch_segments_mapped_from_window(self) -> None:
        """BatchSegments have the same text and times as the source TranscriptSegments."""
        mid = uuid4()
        seg = _make_segment(meeting_id=mid, start_time=10.0, end_time=15.0, text="Deploy now")
        window = _make_window(meeting_id=mid, segments=[seg])

        mock_result = _make_extraction_result()
        extractor = _MockExtractor(mock_result)

        with (
            patch.object(main_module, "_llm_extractor", extractor),
            patch.object(main_module, "_event_publisher", None),
            patch.object(main_module, "_session_factory", None),
        ):
            await main_module._on_window(window)

        batch = extractor.called_with[0]
        assert len(batch.segments) == 1
        assert batch.segments[0].text == "Deploy now"
        assert batch.segments[0].start_time == 10.0
        assert batch.segments[0].end_time == 15.0

    async def test_batch_window_seconds_matches_window_duration(self) -> None:
        """batch_window_seconds equals window.duration."""
        mid = uuid4()
        window = _make_window(meeting_id=mid, window_start=0.0, window_end=180.0)

        mock_result = _make_extraction_result()
        extractor = _MockExtractor(mock_result)

        with (
            patch.object(main_module, "_llm_extractor", extractor),
            patch.object(main_module, "_event_publisher", None),
            patch.object(main_module, "_session_factory", None),
        ):
            await main_module._on_window(window)

        assert extractor.called_with[0].batch_window_seconds == pytest.approx(180.0)

    async def test_context_segments_empty_on_first_window(self) -> None:
        """First window for a meeting has no context_segments."""
        mid = uuid4()
        window = _make_window(meeting_id=mid)

        mock_result = _make_extraction_result()
        extractor = _MockExtractor(mock_result)

        # Ensure no prior context in cache
        main_module._context_cache.pop(mid, None)

        with (
            patch.object(main_module, "_llm_extractor", extractor),
            patch.object(main_module, "_event_publisher", None),
            patch.object(main_module, "_session_factory", None),
        ):
            await main_module._on_window(window)

        assert extractor.called_with[0].context_segments == []

    async def test_context_segments_populated_from_previous_window(self) -> None:
        """Second window receives context_segments from the first window's cache."""
        mid = uuid4()
        fake_ctx = [BatchSegment(segment_id="prev_1", text="prev text", start_time=0, end_time=2)]
        main_module._context_cache[mid] = fake_ctx

        window = _make_window(meeting_id=mid)
        mock_result = _make_extraction_result()
        extractor = _MockExtractor(mock_result)

        try:
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", None),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)

            assert extractor.called_with[0].context_segments == fake_ctx
        finally:
            main_module._context_cache.pop(mid, None)


# ---------------------------------------------------------------------------
# _on_window — context cache management
# ---------------------------------------------------------------------------


class TestOnWindowContextCache:
    """Tests for _context_cache updates inside _on_window."""

    async def test_cache_updated_after_extraction(self) -> None:
        """_context_cache is populated with the tail of the current window segments."""
        mid = uuid4()
        segs = [
            _make_segment(meeting_id=mid, start_time=float(i * 5), end_time=float(i * 5 + 4))
            for i in range(7)  # 7 segments; cache stores last 5
        ]
        window = _make_window(meeting_id=mid, segments=segs)

        mock_result = _make_extraction_result()
        extractor = _MockExtractor(mock_result)
        main_module._context_cache.pop(mid, None)

        try:
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", None),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)

            cached = main_module._context_cache.get(mid, [])
            assert len(cached) == main_module._CONTEXT_CACHE_MAX_SEGMENTS
        finally:
            main_module._context_cache.pop(mid, None)

    async def test_final_window_clears_context_cache(self) -> None:
        """Final window removes the meeting from _context_cache."""
        mid = uuid4()
        window = _make_window(meeting_id=mid, is_final=True)
        fake_ctx = [BatchSegment(segment_id="s1", text="x", start_time=0, end_time=1)]
        main_module._context_cache[mid] = fake_ctx

        mock_result = _make_extraction_result()
        extractor = _MockExtractor(mock_result)

        try:
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", None),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)

            assert mid not in main_module._context_cache
        finally:
            main_module._context_cache.pop(mid, None)


# ---------------------------------------------------------------------------
# _on_window — deduplication
# ---------------------------------------------------------------------------


class TestOnWindowDeduplication:
    """Tests for content-key deduplication inside _on_window."""

    async def test_duplicate_entity_filtered_on_second_window(self) -> None:
        """An entity seen in a prior window is filtered out in subsequent windows."""
        mid = uuid4()
        entity = _make_task_entity(meeting_id=str(mid), title="Deploy service")
        mock_result = _make_extraction_result(entities=[entity])
        extractor = _MockExtractor(mock_result)

        # Seed the seen_keys as if the entity was extracted in a previous window
        main_module._seen_keys[mid] = {entity.content_key()}

        window = _make_window(meeting_id=mid)
        publish_mock = AsyncMock()

        try:
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", MagicMock(publish_insights=publish_mock)),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)

            # Entity was a duplicate, so publish_insights should NOT be called
            publish_mock.assert_not_called()
        finally:
            main_module._seen_keys.pop(mid, None)
            main_module._context_cache.pop(mid, None)

    async def test_new_entity_added_to_seen_keys(self) -> None:
        """A newly extracted entity's content_key is added to _seen_keys."""
        mid = uuid4()
        entity = _make_task_entity(meeting_id=str(mid), title="Review PR")
        mock_result = _make_extraction_result(entities=[entity])
        extractor = _MockExtractor(mock_result)

        # Start with empty seen_keys for this meeting
        main_module._seen_keys.pop(mid, None)
        window = _make_window(meeting_id=mid)

        try:
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", None),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)

            assert entity.content_key() in main_module._seen_keys.get(mid, set())
        finally:
            main_module._seen_keys.pop(mid, None)
            main_module._context_cache.pop(mid, None)

    async def test_final_window_clears_seen_keys(self) -> None:
        """Final window removes the meeting from _seen_keys."""
        mid = uuid4()
        window = _make_window(meeting_id=mid, is_final=True)
        main_module._seen_keys[mid] = {"some-key"}

        mock_result = _make_extraction_result()
        extractor = _MockExtractor(mock_result)

        try:
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", None),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)

            assert mid not in main_module._seen_keys
        finally:
            main_module._seen_keys.pop(mid, None)
            main_module._context_cache.pop(mid, None)


# ---------------------------------------------------------------------------
# _on_window — event publishing
# ---------------------------------------------------------------------------


class TestOnWindowEventPublishing:
    """Tests for insights publishing inside _on_window."""

    async def test_publish_insights_called_with_unique_entities(self) -> None:
        """publish_insights is called with the deduplicated ExtractionResult."""
        mid = uuid4()
        entity = _make_task_entity(meeting_id=str(mid), title="Fix bug")
        mock_result = _make_extraction_result(entities=[entity])
        extractor = _MockExtractor(mock_result)

        publish_mock = AsyncMock()
        mock_publisher = MagicMock()
        mock_publisher.publish_insights = publish_mock

        window = _make_window(meeting_id=mid)
        main_module._seen_keys.pop(mid, None)

        try:
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", mock_publisher),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)

            publish_mock.assert_called_once()
            call_args = publish_mock.call_args
            result_arg: ExtractionResult = call_args[0][1]
            assert len(result_arg.entities) == 1
            assert result_arg.entities[0].content_key() == entity.content_key()
        finally:
            main_module._seen_keys.pop(mid, None)
            main_module._context_cache.pop(mid, None)

    async def test_no_publish_when_all_entities_are_duplicates(self) -> None:
        """publish_insights is not called when all entities are duplicates."""
        mid = uuid4()
        entity = _make_task_entity(meeting_id=str(mid), title="Fix bug")
        mock_result = _make_extraction_result(entities=[entity])
        extractor = _MockExtractor(mock_result)

        # Pre-seed the entity as already seen
        main_module._seen_keys[mid] = {entity.content_key()}

        publish_mock = AsyncMock()
        mock_publisher = MagicMock()
        mock_publisher.publish_insights = publish_mock

        window = _make_window(meeting_id=mid)

        try:
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", mock_publisher),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)

            publish_mock.assert_not_called()
        finally:
            main_module._seen_keys.pop(mid, None)
            main_module._context_cache.pop(mid, None)

    async def test_no_publish_when_no_entities_extracted(self) -> None:
        """publish_insights is not called when LLM returns no entities."""
        mid = uuid4()
        mock_result = _make_extraction_result(entities=[])
        extractor = _MockExtractor(mock_result)

        publish_mock = AsyncMock()
        mock_publisher = MagicMock()
        mock_publisher.publish_insights = publish_mock

        window = _make_window(meeting_id=mid)
        main_module._seen_keys.pop(mid, None)

        try:
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", mock_publisher),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)

            publish_mock.assert_not_called()
        finally:
            main_module._seen_keys.pop(mid, None)
            main_module._context_cache.pop(mid, None)

    async def test_publish_error_is_swallowed(self) -> None:
        """A publish failure does not propagate — extraction still completes."""
        mid = uuid4()
        entity = _make_task_entity(meeting_id=str(mid), title="Write tests")
        mock_result = _make_extraction_result(entities=[entity])
        extractor = _MockExtractor(mock_result)

        publish_mock = AsyncMock(side_effect=RuntimeError("Redis is down"))
        mock_publisher = MagicMock()
        mock_publisher.publish_insights = publish_mock

        window = _make_window(meeting_id=mid)
        main_module._seen_keys.pop(mid, None)

        try:
            # Should not raise
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", mock_publisher),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)
        finally:
            main_module._seen_keys.pop(mid, None)
            main_module._context_cache.pop(mid, None)

    async def test_no_publish_when_no_publisher(self) -> None:
        """No error when event_publisher is None (events silently skipped)."""
        mid = uuid4()
        entity = _make_task_entity(meeting_id=str(mid), title="Refactor code")
        mock_result = _make_extraction_result(entities=[entity])
        extractor = _MockExtractor(mock_result)

        window = _make_window(meeting_id=mid)
        main_module._seen_keys.pop(mid, None)

        try:
            with (
                patch.object(main_module, "_llm_extractor", extractor),
                patch.object(main_module, "_event_publisher", None),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)  # should not raise
        finally:
            main_module._seen_keys.pop(mid, None)
            main_module._context_cache.pop(mid, None)


# ---------------------------------------------------------------------------
# _on_window — LLM extraction failure
# ---------------------------------------------------------------------------


class TestOnWindowLLMFailure:
    """Tests for LLM extraction failure handling in _on_window."""

    async def test_extraction_exception_does_not_propagate(self) -> None:
        """An LLM exception is caught and swallowed — _on_window returns normally."""
        mid = uuid4()
        window = _make_window(meeting_id=mid)

        failing_extractor = MagicMock()
        failing_extractor.extract = AsyncMock(side_effect=RuntimeError("LLM error"))

        with (
            patch.object(main_module, "_llm_extractor", failing_extractor),
            patch.object(main_module, "_event_publisher", None),
            patch.object(main_module, "_session_factory", None),
        ):
            await main_module._on_window(window)  # should not raise

    async def test_extraction_failure_on_final_window_clears_state(self) -> None:
        """LLM failure on final window still cleans up seen_keys and context_cache."""
        mid = uuid4()
        window = _make_window(meeting_id=mid, is_final=True)
        main_module._seen_keys[mid] = {"key"}
        main_module._context_cache[mid] = []

        failing_extractor = MagicMock()
        failing_extractor.extract = AsyncMock(side_effect=RuntimeError("LLM down"))

        try:
            with (
                patch.object(main_module, "_llm_extractor", failing_extractor),
                patch.object(main_module, "_event_publisher", None),
                patch.object(main_module, "_session_factory", None),
            ):
                await main_module._on_window(window)

            assert mid not in main_module._seen_keys
            assert mid not in main_module._context_cache
        finally:
            main_module._seen_keys.pop(mid, None)
            main_module._context_cache.pop(mid, None)


# ---------------------------------------------------------------------------
# _persist_task_entities
# ---------------------------------------------------------------------------


class TestPersistTaskEntities:
    """Tests for _persist_task_entities helper."""

    async def test_no_op_when_no_session_factory(self) -> None:
        """Does nothing when _session_factory is None."""
        mid = uuid4()
        entity = _make_task_entity(meeting_id=str(mid))

        with patch.object(main_module, "_session_factory", None):
            await main_module._persist_task_entities([entity], mid)
            # No exception — test passes

    async def test_no_op_when_no_task_entities(self) -> None:
        """Skips DB write when there are no task entities."""
        from convene_core.extraction.types import DecisionEntity

        mid = uuid4()
        decision = DecisionEntity(
            meeting_id=str(mid),
            batch_id=str(uuid4()),
            summary="Use PostgreSQL",
        )

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        with patch.object(main_module, "_session_factory", mock_factory):
            await main_module._persist_task_entities([decision], mid)

        mock_factory.assert_not_called()

    async def test_task_entity_persisted_to_db(self) -> None:
        """A TaskEntity results in a TaskORM being added to the session."""
        from convene_core.database.models import TaskORM

        mid = uuid4()
        entity = _make_task_entity(meeting_id=str(mid), title="Write report")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_factory = MagicMock(return_value=mock_session)

        with patch.object(main_module, "_session_factory", mock_factory):
            await main_module._persist_task_entities([entity], mid)

        assert mock_session.add.call_count == 1
        orm_obj = mock_session.add.call_args[0][0]
        assert isinstance(orm_obj, TaskORM)
        assert orm_obj.description == "Write report"
        assert orm_obj.meeting_id == mid

    async def test_db_error_is_swallowed(self) -> None:
        """A database error is caught and swallowed — does not propagate."""
        mid = uuid4()
        entity = _make_task_entity(meeting_id=str(mid), title="Fix tests")

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.commit.side_effect = RuntimeError("DB is down")
        mock_factory = MagicMock(return_value=mock_session)

        with patch.object(main_module, "_session_factory", mock_factory):
            await main_module._persist_task_entities([entity], mid)
            # No exception raised — test passes
