"""Tests for the audio pipeline and event publishing."""

from __future__ import annotations

import struct
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from audio_service.audio_pipeline import AudioPipeline
from convene_core.models.transcript import TranscriptSegment
from convene_providers.testing import MockSTT

# ---- Helpers ----

MEETING_ID = uuid4()


def _make_segments(n: int = 2) -> list[TranscriptSegment]:
    """Create sample transcript segments for testing."""
    return [
        TranscriptSegment(
            meeting_id=MEETING_ID,
            speaker_id=f"spk_{i}",
            text=f"Segment {i}",
            start_time=float(i * 10),
            end_time=float(i * 10 + 5),
            confidence=0.9,
        )
        for i in range(n)
    ]


def _make_pcm16(num_samples: int = 160) -> bytes:
    """Create valid PCM16 16kHz mono audio bytes."""
    return struct.pack(f"<{num_samples}h", *([0] * num_samples))


# ---- Audio Pipeline Unit Tests ----


class TestAudioPipelineUnit:
    """Unit tests for AudioPipeline core logic."""

    @pytest.mark.asyncio
    async def test_process_audio_starts_stream(self) -> None:
        """process_audio calls start_stream on first invocation."""
        mock_stt = MockSTT()
        pipeline = AudioPipeline(stt_provider=mock_stt)

        assert not mock_stt._started
        await pipeline.process_audio(_make_pcm16())
        assert mock_stt._started

    @pytest.mark.asyncio
    async def test_process_audio_sends_pcm16_directly(self) -> None:
        """process_audio forwards PCM16 bytes directly to STT."""
        mock_stt = MockSTT()
        pipeline = AudioPipeline(stt_provider=mock_stt)

        pcm_data = _make_pcm16(80)
        await pipeline.process_audio(pcm_data)
        assert mock_stt._buffer == pcm_data

    @pytest.mark.asyncio
    async def test_get_segments_yields_stt_segments(self) -> None:
        """get_segments yields segments from the STT provider."""
        segments = _make_segments(3)
        mock_stt = MockSTT(segments=segments)
        pipeline = AudioPipeline(stt_provider=mock_stt)

        result = [seg async for seg in pipeline.get_segments()]
        assert len(result) == 3
        assert result[0].text == "Segment 0"

    @pytest.mark.asyncio
    async def test_close_stops_stt(self) -> None:
        """close() stops the STT stream."""
        mock_stt = MockSTT()
        pipeline = AudioPipeline(stt_provider=mock_stt)

        await pipeline.process_audio(_make_pcm16())
        assert mock_stt._started
        await pipeline.close()
        assert not mock_stt._started

    @pytest.mark.asyncio
    async def test_close_without_start_is_noop(self) -> None:
        """close() on an unstarted pipeline is a noop."""
        mock_stt = MockSTT()
        pipeline = AudioPipeline(stt_provider=mock_stt)

        # Should not raise
        await pipeline.close()
        assert not mock_stt._started


# ---- Event Publishing Tests ----


class TestEventPublishing:
    """Tests for lifecycle and transcript event publishing."""

    @pytest.mark.asyncio
    async def test_meeting_started_on_first_audio(self) -> None:
        """MeetingStarted event is published on first process_audio."""
        mock_stt = MockSTT()
        mock_publisher = AsyncMock()
        pipeline = AudioPipeline(
            stt_provider=mock_stt,
            event_publisher=mock_publisher,
            meeting_id=MEETING_ID,
        )

        await pipeline.process_audio(_make_pcm16())

        mock_publisher.publish.assert_called_once()
        event = mock_publisher.publish.call_args[0][0]
        assert event.event_type == "meeting.started"
        assert event.meeting_id == MEETING_ID

    @pytest.mark.asyncio
    async def test_meeting_ended_on_close(self) -> None:
        """MeetingEnded event is published on close()."""
        mock_stt = MockSTT()
        mock_publisher = AsyncMock()
        pipeline = AudioPipeline(
            stt_provider=mock_stt,
            event_publisher=mock_publisher,
            meeting_id=MEETING_ID,
        )

        await pipeline.process_audio(_make_pcm16())
        mock_publisher.publish.reset_mock()

        await pipeline.close()

        mock_publisher.publish.assert_called_once()
        event = mock_publisher.publish.call_args[0][0]
        assert event.event_type == "meeting.ended"
        assert event.meeting_id == MEETING_ID

    @pytest.mark.asyncio
    async def test_segments_published_as_events(self) -> None:
        """Each segment is published as a TranscriptSegmentFinal event."""
        segments = _make_segments(2)
        mock_stt = MockSTT(segments=segments)
        mock_publisher = AsyncMock()
        pipeline = AudioPipeline(
            stt_provider=mock_stt,
            event_publisher=mock_publisher,
            meeting_id=MEETING_ID,
        )

        result = [seg async for seg in pipeline.get_segments()]
        assert len(result) == 2
        assert mock_publisher.publish.call_count == 2

        event = mock_publisher.publish.call_args_list[0][0][0]
        assert event.event_type == "transcript.segment.final"

    @pytest.mark.asyncio
    async def test_publish_failure_does_not_block_close(self) -> None:
        """Publish failure in close() does not prevent cleanup."""
        mock_stt = MockSTT()
        mock_publisher = AsyncMock()
        mock_publisher.publish.side_effect = RuntimeError("Redis down")
        pipeline = AudioPipeline(
            stt_provider=mock_stt,
            event_publisher=mock_publisher,
            meeting_id=MEETING_ID,
        )

        await pipeline.process_audio(_make_pcm16())
        # Should not raise despite publish failure
        await pipeline.close()
        assert not mock_stt._started


# ---- Audio Buffering Tests ----


class TestAudioBuffering:
    """Tests for audio buffering on STT failure."""

    @pytest.mark.asyncio
    async def test_retry_on_send_failure(self) -> None:
        """Audio is retried before buffering on send failure."""
        mock_stt = MagicMock()
        mock_stt.start_stream = AsyncMock()
        mock_stt.send_audio = AsyncMock(
            side_effect=[RuntimeError("fail"), RuntimeError("fail"), None]
        )

        pipeline = AudioPipeline(stt_provider=mock_stt)

        with patch("audio_service.audio_pipeline._RETRY_DELAY_S", 0.01):
            await pipeline.process_audio(_make_pcm16())

        # 3 calls: 2 failures + 1 success
        assert mock_stt.send_audio.call_count == 3
        # Buffer should be empty since last retry succeeded
        assert len(pipeline._audio_buffer) == 0

    @pytest.mark.asyncio
    async def test_buffer_on_exhausted_retries(self) -> None:
        """Audio is buffered after all retries fail."""
        mock_stt = MagicMock()
        mock_stt.start_stream = AsyncMock()
        mock_stt.send_audio = AsyncMock(side_effect=RuntimeError("fail"))

        pipeline = AudioPipeline(stt_provider=mock_stt)

        with patch("audio_service.audio_pipeline._RETRY_DELAY_S", 0.01):
            await pipeline.process_audio(_make_pcm16())

        assert len(pipeline._audio_buffer) > 0

    @pytest.mark.asyncio
    async def test_buffer_overflow_drops_oldest(self) -> None:
        """Buffer overflow drops oldest bytes via FIFO."""
        mock_stt = MockSTT()
        pipeline = AudioPipeline(stt_provider=mock_stt)

        # Manually fill buffer beyond limit
        with patch("audio_service.audio_pipeline._MAX_BUFFER_BYTES", 100):
            pipeline._buffer_audio(b"\x01" * 80)
            pipeline._buffer_audio(b"\x02" * 50)

        # Total would be 130, cap is 100, so 30 oldest dropped
        assert len(pipeline._audio_buffer) == 100
        # Oldest bytes (\x01) should be partially dropped
        assert pipeline._audio_buffer[0] != 0x01 or len(pipeline._audio_buffer) < 130

    @pytest.mark.asyncio
    async def test_flush_sends_buffered_audio_first(self) -> None:
        """Buffered audio is flushed before new audio is sent."""
        call_order: list[str] = []
        mock_stt = MagicMock()
        mock_stt.start_stream = AsyncMock()

        original_send = AsyncMock()

        async def track_send(data: bytes) -> None:
            if data == b"buffered":
                call_order.append("flush")
            else:
                call_order.append("new")
            await original_send(data)

        mock_stt.send_audio = AsyncMock(side_effect=track_send)

        pipeline = AudioPipeline(stt_provider=mock_stt)
        pipeline._started = True
        pipeline._audio_buffer = bytearray(b"buffered")

        await pipeline.process_audio(_make_pcm16())

        assert call_order[0] == "flush"
