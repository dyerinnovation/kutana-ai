"""Local speech-to-text provider using faster-whisper."""

from __future__ import annotations

import asyncio
import logging
import math
import tempfile
import wave
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from convene_core.interfaces.stt import STTProvider
from convene_core.models.transcript import TranscriptSegment

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class WhisperSTT(STTProvider):
    """Local STT provider using faster-whisper. No API key required.

    Buffers raw PCM16 16kHz mono audio and transcribes it using the
    faster-whisper library, which runs CTranslate2-optimized Whisper
    models locally.
    """

    def __init__(
        self,
        model_size: str = "small",
        meeting_id: UUID | None = None,
    ) -> None:
        """Initialize the Whisper STT provider.

        Args:
            model_size: Whisper model size (tiny, base, small,
                medium, large-v2, etc.).
            meeting_id: Optional meeting ID to tag transcript
                segments.
        """
        self._model_size = model_size
        self._meeting_id = meeting_id or uuid4()
        self._model: object | None = None
        self._buffer = b""
        self._running = False

    def _load_model(self) -> None:
        """Load the faster-whisper model synchronously.

        This is called inside ``asyncio.to_thread`` so it does
        not block the event loop.
        """
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self._model_size,
            device="cpu",
            compute_type="int8",
        )
        logger.info(
            "Loaded faster-whisper model: %s",
            self._model_size,
        )

    async def start_stream(self) -> None:
        """Initialize a new streaming transcription session.

        Resets the internal audio buffer and lazily loads the
        Whisper model if it has not been loaded yet.
        """
        self._buffer = b""
        self._running = True

        if self._model is None:
            await asyncio.to_thread(self._load_model)

        logger.info("Whisper streaming session started.")

    async def send_audio(self, chunk: bytes) -> None:
        """Append raw PCM16 audio bytes to the internal buffer.

        Args:
            chunk: Raw PCM16 audio bytes at 16kHz mono.
        """
        if not self._running:
            msg = "Stream not started. Call start_stream() first."
            raise RuntimeError(msg)

        self._buffer += chunk

    async def get_transcript(
        self,
    ) -> AsyncIterator[TranscriptSegment]:
        """Transcribe buffered audio and yield transcript segments.

        Writes the PCM16 buffer to a temporary WAV file, runs
        faster-whisper transcription in a background thread, and
        yields a ``TranscriptSegment`` for each detected segment.

        Yields:
            TranscriptSegment instances (speaker_id is None since
            faster-whisper does not perform diarization).
        """
        if self._model is None:
            msg = "Model not loaded. Call start_stream() first."
            raise RuntimeError(msg)

        if not self._buffer:
            return

        # Write buffer to a temporary WAV file (delete=False because
        # the file must persist for faster-whisper to read it; we
        # clean up manually in the finally block).
        tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
            suffix=".wav",
            delete=False,
        )
        try:
            with wave.open(tmp.name, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(self._buffer)

            # Run transcription in a thread to avoid blocking
            segments_raw, _info = await asyncio.to_thread(
                self._model.transcribe,  # type: ignore[union-attr]  # _model is set before use
                tmp.name,
            )
            # Materialise the generator in the thread
            segment_list = await asyncio.to_thread(
                list,
                segments_raw,
            )

            # Clear the buffer so the next call only transcribes new audio
            self._buffer = b""

            for seg in segment_list:
                # Guard against zero-length segments
                end_time = seg.end
                if end_time <= seg.start:
                    end_time = seg.start + 0.01

                # avg_logprob is negative; convert to 0.0-1.0 range
                confidence = max(0.0, min(1.0, math.exp(seg.avg_logprob)))

                yield TranscriptSegment(
                    meeting_id=self._meeting_id,
                    speaker_id=None,
                    text=seg.text.strip(),
                    start_time=seg.start,
                    end_time=end_time,
                    confidence=confidence,
                )
        finally:
            import os

            os.unlink(tmp.name)

    async def close(self) -> None:
        """Clear the audio buffer and stop the session."""
        self._buffer = b""
        self._running = False
        logger.info("Whisper streaming session closed.")
