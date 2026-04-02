"""Unit tests for SegmentWindower and SegmentWindow.

All tests are pure-Python — no Redis or database required.
"""

from __future__ import annotations

from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from kutana_core.models.transcript import TranscriptSegment
from task_engine.windower import (
    DEFAULT_OVERLAP_SECONDS,
    DEFAULT_WINDOW_SECONDS,
    SegmentWindow,
    SegmentWindower,
)

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_segment(
    meeting_id: UUID | None = None,
    start_time: float = 0.0,
    end_time: float = 5.0,
    text: str = "Test segment.",
    speaker_id: str = "spk_0",
) -> TranscriptSegment:
    """Build a minimal TranscriptSegment for testing."""
    return TranscriptSegment(
        meeting_id=meeting_id or uuid4(),
        speaker_id=speaker_id,
        text=text,
        start_time=start_time,
        end_time=end_time,
        confidence=0.95,
    )


def _make_windower(
    on_window: AsyncMock | None = None,
    window_size_seconds: float = 60.0,
    overlap_seconds: float = 10.0,
) -> tuple[SegmentWindower, AsyncMock]:
    """Build a SegmentWindower with a mock callback for testing."""
    cb = on_window or AsyncMock()
    windower = SegmentWindower(
        on_window=cb,
        window_size_seconds=window_size_seconds,
        overlap_seconds=overlap_seconds,
    )
    return windower, cb


# ---------------------------------------------------------------------------
# SegmentWindow model tests
# ---------------------------------------------------------------------------


class TestSegmentWindow:
    """Tests for the SegmentWindow Pydantic model."""

    def test_window_end_must_exceed_window_start(self) -> None:
        """window_end <= window_start raises ValueError."""
        with pytest.raises(ValueError, match="window_end must be greater"):
            SegmentWindow(
                meeting_id=uuid4(),
                window_start=10.0,
                window_end=10.0,
            )

    def test_duration_property(self) -> None:
        """duration returns window_end - window_start."""
        window = SegmentWindow(
            meeting_id=uuid4(),
            window_start=30.0,
            window_end=90.0,
        )
        assert window.duration == pytest.approx(60.0)

    def test_text_property_concatenates_segments(self) -> None:
        """text joins segment texts with spaces."""
        mid = uuid4()
        s1 = _make_segment(meeting_id=mid, start_time=0.0, end_time=3.0, text="Hello")
        s2 = _make_segment(meeting_id=mid, start_time=3.0, end_time=6.0, text="world")
        window = SegmentWindow(
            meeting_id=mid,
            segments=[s1, s2],
            window_start=0.0,
            window_end=6.0,
        )
        assert window.text == "Hello world"

    def test_text_property_empty_segments(self) -> None:
        """text returns empty string when there are no segments."""
        window = SegmentWindow(
            meeting_id=uuid4(),
            segments=[],
            window_start=0.0,
            window_end=1.0,
        )
        assert window.text == ""

    def test_is_final_defaults_false(self) -> None:
        """is_final is False by default."""
        window = SegmentWindow(meeting_id=uuid4(), window_start=0.0, window_end=1.0)
        assert window.is_final is False


# ---------------------------------------------------------------------------
# SegmentWindower initialisation tests
# ---------------------------------------------------------------------------


class TestSegmentWindowerInit:
    """Tests for SegmentWindower construction."""

    def test_raises_if_overlap_equals_window_size(self) -> None:
        """overlap_seconds == window_size_seconds raises ValueError."""
        with pytest.raises(ValueError, match="overlap_seconds"):
            SegmentWindower(on_window=AsyncMock(), window_size_seconds=60.0, overlap_seconds=60.0)

    def test_raises_if_overlap_exceeds_window_size(self) -> None:
        """overlap_seconds > window_size_seconds raises ValueError."""
        with pytest.raises(ValueError, match="overlap_seconds"):
            SegmentWindower(on_window=AsyncMock(), window_size_seconds=30.0, overlap_seconds=60.0)

    def test_default_constants_are_sane(self) -> None:
        """Default window and overlap values match the module constants."""
        windower = SegmentWindower(on_window=AsyncMock())
        assert windower._window_size == DEFAULT_WINDOW_SECONDS
        assert windower._overlap == DEFAULT_OVERLAP_SECONDS

    def test_active_meetings_empty_at_start(self) -> None:
        """No active meetings before any segments are added."""
        windower, _ = _make_windower()
        assert windower.active_meetings == frozenset()


# ---------------------------------------------------------------------------
# add_segment tests
# ---------------------------------------------------------------------------


class TestAddSegment:
    """Tests for SegmentWindower.add_segment."""

    async def test_does_not_emit_below_window_size(self) -> None:
        """Callback is not called when buffered span < window_size."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        # 50 seconds of transcript — just under the 60s window
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=50.0))
        cb.assert_not_called()

    async def test_emits_window_when_span_reaches_window_size(self) -> None:
        """Callback is called exactly once when span hits window_size."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=60.0))
        cb.assert_called_once()

    async def test_emitted_window_has_correct_meeting_id(self) -> None:
        """Emitted window carries the correct meeting_id."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=60.0))
        window: SegmentWindow = cb.call_args[0][0]
        assert window.meeting_id == mid

    async def test_emitted_window_start_and_end_correct(self) -> None:
        """Emitted window has correct start and end times."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=60.0))
        window: SegmentWindow = cb.call_args[0][0]
        assert window.window_start == pytest.approx(0.0)
        assert window.window_end == pytest.approx(60.0)

    async def test_emitted_window_contains_correct_segments(self) -> None:
        """Segments within the window boundary are included."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        s1 = _make_segment(meeting_id=mid, start_time=0.0, end_time=30.0, text="First")
        s2 = _make_segment(meeting_id=mid, start_time=30.0, end_time=60.0, text="Second")
        await windower.add_segment(s1)
        await windower.add_segment(s2)
        window: SegmentWindow = cb.call_args[0][0]
        assert len(window.segments) == 2
        assert window.segments[0].text == "First"
        assert window.segments[1].text == "Second"

    async def test_is_final_false_for_regular_emit(self) -> None:
        """Windows emitted by add_segment are not marked final."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=60.0))
        window: SegmentWindow = cb.call_args[0][0]
        assert window.is_final is False

    async def test_buffer_pruned_after_emit(self) -> None:
        """Segments before the new overlap start are removed after emit."""
        windower, _ = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        # Two segments: 0–30s and 30–60s.  After emit, new window starts at 50s.
        # Only segments with end_time > 50 should remain.
        s1 = _make_segment(meeting_id=mid, start_time=0.0, end_time=30.0)
        s2 = _make_segment(meeting_id=mid, start_time=30.0, end_time=60.0)
        await windower.add_segment(s1)
        await windower.add_segment(s2)
        # s1 ends at 30, which is not > 50 (new window start), so it's pruned.
        # s2 ends at 60, which is > 50, so it remains.
        assert mid in windower._buffers
        remaining = windower._buffers[mid]
        assert all(s.end_time > 50.0 for s in remaining)

    async def test_overlap_segments_included_in_next_window(self) -> None:
        """Segments within the overlap zone appear in the next window."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        # First window: 0–60s.  After emit, new window_start = 50s.
        # Add a segment at 55–65s — it should appear in the second window.
        s1 = _make_segment(meeting_id=mid, start_time=0.0, end_time=60.0)
        s2 = _make_segment(meeting_id=mid, start_time=55.0, end_time=65.0, text="Overlap")
        s3 = _make_segment(meeting_id=mid, start_time=65.0, end_time=115.0, text="Filler")
        await windower.add_segment(s1)
        await windower.add_segment(s2)
        await windower.add_segment(s3)
        # Two windows should have been emitted by now
        assert cb.call_count == 2
        second_window: SegmentWindow = cb.call_args_list[1][0][0]
        texts = [s.text for s in second_window.segments]
        assert "Overlap" in texts

    async def test_multiple_windows_from_long_transcript(self) -> None:
        """Three non-overlapping windows are emitted for 180s of transcript."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        # 180 seconds covered by a single 180s segment triggers multiple emissions
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=180.0))
        assert cb.call_count == 3

    async def test_multiple_meetings_are_independent(self) -> None:
        """Segments for different meetings do not affect each other's windows."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid1 = uuid4()
        mid2 = uuid4()
        # Only fill window for meeting 1
        await windower.add_segment(_make_segment(meeting_id=mid1, start_time=0.0, end_time=60.0))
        # Add a short segment for meeting 2 (should not trigger window)
        await windower.add_segment(_make_segment(meeting_id=mid2, start_time=0.0, end_time=10.0))
        assert cb.call_count == 1
        emitted_window: SegmentWindow = cb.call_args[0][0]
        assert emitted_window.meeting_id == mid1

    async def test_active_meetings_updated_on_first_segment(self) -> None:
        """active_meetings includes the meeting after first segment is added."""
        windower, _ = _make_windower()
        mid = uuid4()
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=1.0))
        assert mid in windower.active_meetings


# ---------------------------------------------------------------------------
# flush() tests
# ---------------------------------------------------------------------------


class TestFlush:
    """Tests for SegmentWindower.flush."""

    async def test_flush_emits_remaining_segments(self) -> None:
        """flush() triggers on_window with buffered segments."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        seg = _make_segment(meeting_id=mid, start_time=0.0, end_time=20.0, text="Partial")
        await windower.add_segment(seg)
        await windower.flush(mid)
        cb.assert_called_once()
        window: SegmentWindow = cb.call_args[0][0]
        assert window.segments[0].text == "Partial"

    async def test_flush_marks_window_as_final(self) -> None:
        """Window emitted by flush() has is_final=True."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=20.0))
        await windower.flush(mid)
        window: SegmentWindow = cb.call_args[0][0]
        assert window.is_final is True

    async def test_flush_empty_buffer_does_not_call_callback(self) -> None:
        """flush() on an empty buffer does not invoke on_window."""
        windower, cb = _make_windower()
        await windower.flush(uuid4())
        cb.assert_not_called()

    async def test_flush_removes_meeting_from_active(self) -> None:
        """After flush, the meeting is removed from active_meetings."""
        windower, _ = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=20.0))
        assert mid in windower.active_meetings
        await windower.flush(mid)
        assert mid not in windower.active_meetings

    async def test_flush_window_start_matches_current_window_start(self) -> None:
        """flush() window_start reflects the current window-start position."""
        windower, cb = _make_windower(window_size_seconds=60.0, overlap_seconds=10.0)
        mid = uuid4()
        # First window emitted at 60s, new window_start = 50s
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=60.0))
        cb.reset_mock()
        # Add another short segment, not enough to trigger another full window
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=55.0, end_time=70.0))
        await windower.flush(mid)
        final_window: SegmentWindow = cb.call_args[0][0]
        # window_start should be 50 (60 - 10 overlap)
        assert final_window.window_start == pytest.approx(50.0)


# ---------------------------------------------------------------------------
# clear() tests
# ---------------------------------------------------------------------------


class TestClear:
    """Tests for SegmentWindower.clear."""

    async def test_clear_removes_meeting_from_active(self) -> None:
        """clear() removes the meeting from active_meetings without emitting."""
        windower, cb = _make_windower()
        mid = uuid4()
        await windower.add_segment(_make_segment(meeting_id=mid, start_time=0.0, end_time=1.0))
        windower.clear(mid)
        assert mid not in windower.active_meetings
        cb.assert_not_called()

    async def test_clear_unknown_meeting_does_not_raise(self) -> None:
        """clear() on a meeting with no buffer is a no-op."""
        windower, _ = _make_windower()
        windower.clear(uuid4())  # should not raise
