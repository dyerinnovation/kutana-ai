"""Transcript segment windowing for LLM task extraction.

Segments arrive one-at-a-time from the Redis Stream consumer.  The
windower accumulates them per-meeting and emits time-boxed
:class:`SegmentWindow` batches once enough transcript has accumulated.
Consecutive windows overlap so that commitments made near a window
boundary are captured by at least one window.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from kutana_core.models.transcript import TranscriptSegment

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# Default window / overlap durations (seconds)
DEFAULT_WINDOW_SECONDS: float = 180.0  # 3 minutes
DEFAULT_OVERLAP_SECONDS: float = 30.0  # 30-second overlap between windows


class SegmentWindow(BaseModel):
    """A time-bounded batch of transcript segments ready for LLM extraction.

    Attributes:
        meeting_id: ID of the meeting these segments belong to.
        segments: Ordered list of transcript segments in this window.
        window_start: Window start offset in seconds from meeting start.
        window_end: Window end offset in seconds from meeting start.
        is_final: ``True`` when this is the last window emitted for the
            meeting (produced by :meth:`SegmentWindower.flush`).
    """

    meeting_id: UUID
    segments: list[TranscriptSegment] = Field(default_factory=list)
    window_start: float
    window_end: float
    is_final: bool = False

    @model_validator(mode="after")
    def _validate_window(self) -> SegmentWindow:
        """Validate that window_end is greater than window_start."""
        if self.window_end <= self.window_start:
            msg = "window_end must be greater than window_start"
            raise ValueError(msg)
        return self

    @property
    def duration(self) -> float:
        """Duration of this window in seconds."""
        return self.window_end - self.window_start

    @property
    def text(self) -> str:
        """Concatenated transcript text for all segments in the window."""
        return " ".join(s.text for s in self.segments)


class SegmentWindower:
    """Accumulates transcript segments and emits time-windowed batches.

    Segments are buffered per-meeting in arrival order.  When the
    accumulated span from the current window-start position reaches
    ``window_size_seconds``, a :class:`SegmentWindow` is emitted to
    the ``on_window`` callback and the buffer is pruned so that the
    *next* window begins ``overlap_seconds`` before the end of the
    emitted window.

    This overlap ensures that commitments made near a window boundary
    are included in at least one extraction window.

    Call :meth:`flush` when a meeting ends to emit any remaining
    segments as a final window (marked :attr:`SegmentWindow.is_final`).

    Example::

        async def handle_window(window: SegmentWindow) -> None:
            tasks = await llm.extract_tasks(window.segments, context="")

        windower = SegmentWindower(on_window=handle_window)
        async for segment in stream:
            await windower.add_segment(segment)
        await windower.flush(meeting_id)

    Attributes:
        _window_size: Target window duration in seconds.
        _overlap: Overlap duration in seconds between consecutive windows.
        _on_window: Async callback invoked with each :class:`SegmentWindow`.
        _buffers: Per-meeting segment buffer (append-only until pruned).
        _window_starts: Per-meeting current window start offset (seconds).
    """

    def __init__(
        self,
        on_window: Callable[[SegmentWindow], Awaitable[None]],
        window_size_seconds: float = DEFAULT_WINDOW_SECONDS,
        overlap_seconds: float = DEFAULT_OVERLAP_SECONDS,
    ) -> None:
        """Initialise the windower.

        Args:
            on_window: Async callback invoked with each completed
                :class:`SegmentWindow`.
            window_size_seconds: How many seconds of transcript to
                accumulate before emitting a window.  Must be strictly
                greater than ``overlap_seconds``.
            overlap_seconds: How many seconds of the previous window to
                retain at the start of the next window.

        Raises:
            ValueError: If ``overlap_seconds >= window_size_seconds``.
        """
        if overlap_seconds >= window_size_seconds:
            msg = (
                f"overlap_seconds ({overlap_seconds}) must be less than "
                f"window_size_seconds ({window_size_seconds})"
            )
            raise ValueError(msg)

        self._window_size = window_size_seconds
        self._overlap = overlap_seconds
        self._on_window = on_window
        self._buffers: dict[UUID, list[TranscriptSegment]] = {}
        self._window_starts: dict[UUID, float] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def add_segment(self, segment: TranscriptSegment) -> None:
        """Buffer a segment and emit a window when the span is reached.

        Creates a new per-meeting buffer on the first segment for a
        given meeting.  After appending, checks whether the buffered
        span from the current window start has reached
        ``window_size_seconds`` and emits one or more windows if so.

        Args:
            segment: Finalized transcript segment to buffer.
        """
        meeting_id = segment.meeting_id

        if meeting_id not in self._buffers:
            self._buffers[meeting_id] = []
            self._window_starts[meeting_id] = segment.start_time
            logger.debug(
                "Started new segment buffer for meeting %s (window_start=%.1f)",
                meeting_id,
                segment.start_time,
            )

        self._buffers[meeting_id].append(segment)
        await self._try_emit(meeting_id)

    async def flush(self, meeting_id: UUID) -> None:
        """Emit remaining buffered segments as a final window.

        Should be called when a meeting ends so that the tail-end of
        the transcript (which may never fill a full window) is still
        processed.  Has no effect when the buffer is already empty.

        After emitting the final window, the meeting's buffer and
        window-start state are removed.

        Args:
            meeting_id: Meeting whose remaining segments should be flushed.
        """
        segments = self._buffers.get(meeting_id)
        if not segments:
            logger.debug(
                "flush() called for meeting %s — buffer already empty; skipping",
                meeting_id,
            )
            return

        window_start = self._window_starts.get(meeting_id, segments[0].start_time)
        window_end = max(s.end_time for s in segments)

        # Ensure window_end is strictly greater than window_start
        if window_end <= window_start:
            window_end = window_start + 0.001  # minimal sentinel for empty flush

        window = SegmentWindow(
            meeting_id=meeting_id,
            segments=list(segments),
            window_start=window_start,
            window_end=window_end,
            is_final=True,
        )

        logger.info(
            "Flushing final window for meeting %s: %.1f–%.1fs (%d segments)",
            meeting_id,
            window_start,
            window_end,
            len(segments),
        )

        await self._on_window(window)
        self._cleanup(meeting_id)

    def clear(self, meeting_id: UUID) -> None:
        """Discard buffered state for a meeting without emitting.

        Useful for error recovery when a meeting terminates abnormally
        and the remaining segments should not be processed.

        Args:
            meeting_id: Meeting whose buffered state should be discarded.
        """
        self._cleanup(meeting_id)
        logger.debug("Cleared buffer for meeting %s", meeting_id)

    @property
    def active_meetings(self) -> frozenset[UUID]:
        """Meeting IDs that currently have buffered segments.

        Returns:
            Frozenset of active meeting :class:`~uuid.UUID` values.
        """
        return frozenset(self._buffers)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _try_emit(self, meeting_id: UUID) -> None:
        """Emit windows until the buffer span drops below the window size.

        Loops so that a burst of segments (e.g., on service startup
        replaying old entries) can emit multiple windows in one call.

        Args:
            meeting_id: Meeting to check for window readiness.
        """
        while True:
            segments = self._buffers.get(meeting_id)
            if not segments:
                break

            window_start = self._window_starts[meeting_id]
            latest_end = max(s.end_time for s in segments)

            if latest_end - window_start < self._window_size:
                # Not enough transcript accumulated yet
                break

            window_end = window_start + self._window_size

            # Collect every segment whose start is within this window.
            # Segments that straddle the boundary (start < window_end)
            # are included so no speech is silently truncated.
            window_segments = [s for s in segments if s.start_time < window_end]

            window = SegmentWindow(
                meeting_id=meeting_id,
                segments=window_segments,
                window_start=window_start,
                window_end=window_end,
                is_final=False,
            )

            logger.info(
                "Emitting window for meeting %s: %.1f–%.1fs (%d segments)",
                meeting_id,
                window_start,
                window_end,
                len(window_segments),
            )

            await self._on_window(window)

            # Slide the window forward.  The new start is placed
            # overlap_seconds before the old window end so that the
            # next window includes some previously-seen content.
            new_window_start = window_end - self._overlap
            self._window_starts[meeting_id] = new_window_start

            # Prune the buffer: drop any segment whose end is entirely
            # before the new window start (it won't be needed again).
            self._buffers[meeting_id] = [
                s for s in segments if s.end_time > new_window_start
            ]

    def _cleanup(self, meeting_id: UUID) -> None:
        """Remove per-meeting buffer and window-start state.

        Args:
            meeting_id: Meeting to remove from internal state.
        """
        self._buffers.pop(meeting_id, None)
        self._window_starts.pop(meeting_id, None)
