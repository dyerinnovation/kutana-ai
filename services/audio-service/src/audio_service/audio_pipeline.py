"""Audio pipeline for streaming PCM16 audio to STT providers."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from kutana_core.events.definitions import (
    MeetingEnded,
    MeetingStarted,
    TranscriptSegmentFinal,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from uuid import UUID

    from audio_service.event_publisher import EventPublisher
    from kutana_core.interfaces.stt import STTProvider
    from kutana_core.models.transcript import TranscriptSegment

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Audio buffering constants
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_RETRY_DELAY_S = 0.5
_MAX_BUFFER_BYTES = 5 * 1024 * 1024  # 5 MB


class AudioPipeline:
    """Streams PCM16 16 kHz mono audio through an STT provider.

    Publishes lifecycle events (MeetingStarted, MeetingEnded) and
    transcript segment events via an optional EventPublisher.  Buffers
    audio on STT send failure and retries to avoid data loss.

    Attributes:
        _stt: The speech-to-text provider to stream audio to.
        _started: Whether the STT stream has been started.
        _event_publisher: Optional publisher for domain events.
        _meeting_id: Meeting ID for event attribution.
        _audio_buffer: Buffer for audio that failed to send.
    """

    def __init__(
        self,
        stt_provider: STTProvider,
        event_publisher: EventPublisher | None = None,
        meeting_id: UUID | None = None,
        speaker_name: str | None = None,
    ) -> None:
        """Initialise the audio pipeline.

        Args:
            stt_provider: An STT provider implementing the STTProvider ABC.
            event_publisher: Optional EventPublisher for domain events.
            meeting_id: Meeting ID for event attribution.
            speaker_name: Display name of the speaker for this pipeline.
        """
        self._stt = stt_provider
        self._started = False
        self._event_publisher = event_publisher
        self._meeting_id = meeting_id
        self._speaker_name = speaker_name
        self._audio_buffer: bytearray = bytearray()

    async def start(self) -> None:
        """Eagerly start the STT stream.

        Call at pipeline creation to avoid cold start latency
        on the first audio chunk.  Safe to call multiple times.
        """
        await self._ensure_started()

    async def _ensure_started(self) -> None:
        """Start the STT stream if it hasn't been started yet.

        Publishes a MeetingStarted event on first audio receipt.
        """
        if not self._started:
            await self._stt.start_stream()
            self._started = True
            if self._event_publisher is not None and self._meeting_id is not None:
                try:
                    await self._event_publisher.publish(MeetingStarted(meeting_id=self._meeting_id))
                except Exception:
                    logger.exception("Failed to publish MeetingStarted event")

    async def process_audio(self, chunk: bytes) -> None:
        """Send a PCM16 16 kHz mono audio chunk to the STT provider.

        On send failure, buffers audio and retries to avoid data loss.

        Args:
            chunk: PCM16 16 kHz mono audio bytes.
        """
        await self._ensure_started()

        # Flush any previously buffered audio first
        await self._flush_buffer()

        # Send current chunk with retry
        await self._send_with_retry(chunk)

    async def _send_with_retry(self, data: bytes) -> None:
        """Send audio to STT with retry logic.

        Args:
            data: PCM16 audio bytes to send.
        """
        for attempt in range(_MAX_RETRIES):
            try:
                await self._stt.send_audio(data)
                return
            except Exception:
                if attempt < _MAX_RETRIES - 1:
                    logger.warning(
                        "STT send_audio failed (attempt %d/%d), retrying",
                        attempt + 1,
                        _MAX_RETRIES,
                    )
                    await asyncio.sleep(_RETRY_DELAY_S)
                else:
                    logger.warning(
                        "STT send_audio failed after %d attempts, buffering",
                        _MAX_RETRIES,
                    )
                    self._buffer_audio(data)

    def _buffer_audio(self, data: bytes) -> None:
        """Append audio to the buffer, dropping oldest on overflow.

        Args:
            data: Audio bytes to buffer.
        """
        self._audio_buffer.extend(data)
        if len(self._audio_buffer) > _MAX_BUFFER_BYTES:
            overflow = len(self._audio_buffer) - _MAX_BUFFER_BYTES
            self._audio_buffer = self._audio_buffer[overflow:]
            logger.warning(
                "Audio buffer overflow: dropped %d bytes (oldest)",
                overflow,
            )

    async def _flush_buffer(self) -> None:
        """Attempt to send buffered audio before new audio."""
        if not self._audio_buffer:
            return

        buffered = bytes(self._audio_buffer)
        self._audio_buffer.clear()

        try:
            await self._stt.send_audio(buffered)
            logger.info("Flushed %d bytes of buffered audio", len(buffered))
        except Exception:
            logger.warning("Failed to flush audio buffer, re-buffering")
            self._buffer_audio(buffered)

    async def get_segments(self) -> AsyncIterator[TranscriptSegment]:
        """Yield finalised transcript segments from the STT provider.

        Publishes each segment as a TranscriptSegmentFinal event.
        Skips silently if the STT stream has not been started yet
        (no audio received).

        Yields:
            TranscriptSegment instances as they become available.
        """
        if not self._started:
            return
        async for segment in self._stt.get_transcript():
            if self._speaker_name and not segment.speaker_name:
                segment.speaker_name = self._speaker_name
            yield segment
            if self._event_publisher is not None and self._meeting_id is not None:
                try:
                    await self._event_publisher.publish(
                        TranscriptSegmentFinal(
                            meeting_id=self._meeting_id,
                            segment=segment,
                        )
                    )
                except Exception:
                    logger.exception("Failed to publish TranscriptSegmentFinal event")

    def reset_provider(self, new_stt: STTProvider) -> None:
        """Swap the STT provider and reset stream state.

        This allows the AudioBridge to inject a fresh provider after
        a connection failure without recreating the entire pipeline.

        Args:
            new_stt: A fresh STT provider instance to replace the current one.
        """
        self._stt = new_stt
        self._started = False
        self._audio_buffer.clear()
        logger.info("STT provider reset on pipeline (meeting_id=%s)", self._meeting_id)

    async def close(self) -> None:
        """Close the STT stream and publish MeetingEnded event."""
        if self._started:
            await self._stt.close()
            self._started = False
            if self._event_publisher is not None and self._meeting_id is not None:
                try:
                    await self._event_publisher.publish(MeetingEnded(meeting_id=self._meeting_id))
                except Exception:
                    logger.exception("Failed to publish MeetingEnded event")
