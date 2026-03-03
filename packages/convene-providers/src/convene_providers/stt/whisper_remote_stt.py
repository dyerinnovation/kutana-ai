"""Remote speech-to-text provider using a vLLM-served Whisper model."""

from __future__ import annotations

import logging
import math
import tempfile
import wave
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import httpx

from convene_core.interfaces.stt import STTProvider
from convene_core.models.transcript import TranscriptSegment

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


class WhisperRemoteSTT(STTProvider):
    """Remote STT provider that calls an OpenAI-compatible Whisper API.

    Buffers raw PCM16 16kHz mono audio and transcribes it by POSTing
    a WAV file to a remote ``/audio/transcriptions`` endpoint (e.g.
    vLLM serving ``openai/whisper-large-v3`` on DGX Spark).
    """

    def __init__(
        self,
        api_url: str,
        meeting_id: UUID | None = None,
    ) -> None:
        """Initialize the remote Whisper STT provider.

        Args:
            api_url: Base URL of the OpenAI-compatible API
                (e.g. ``http://spark-b0f2.local/convene-stt/v1``).
            meeting_id: Optional meeting ID to tag transcript segments.
        """
        self._api_url = api_url.rstrip("/")
        self._meeting_id = meeting_id or uuid4()
        self._buffer = b""
        self._running = False
        self._client: httpx.AsyncClient | None = None

    async def start_stream(self) -> None:
        """Initialize a new streaming transcription session."""
        self._buffer = b""
        self._running = True
        self._client = httpx.AsyncClient(timeout=120.0)
        logger.info("Remote Whisper streaming session started.")

    async def send_audio(self, chunk: bytes) -> None:
        """Append raw PCM16 audio bytes to the internal buffer.

        Args:
            chunk: Raw PCM16 audio bytes at 16kHz mono.
        """
        if not self._running:
            msg = "Stream not started. Call start_stream() first."
            raise RuntimeError(msg)
        self._buffer += chunk

    async def get_transcript(self) -> AsyncIterator[TranscriptSegment]:
        """Transcribe buffered audio via the remote Whisper API.

        Writes the PCM16 buffer to a temporary WAV file, POSTs it
        to the remote endpoint, and yields a ``TranscriptSegment``
        for each detected segment.

        Yields:
            TranscriptSegment instances (speaker_id is None since
            Whisper does not perform diarization).
        """
        if self._client is None:
            msg = "Client not initialized. Call start_stream() first."
            raise RuntimeError(msg)

        if not self._buffer:
            return

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

            with open(tmp.name, "rb") as f:
                wav_bytes = f.read()

            response = await self._client.post(
                f"{self._api_url}/audio/transcriptions",
                files={"file": ("audio.wav", wav_bytes, "audio/wav")},
                data={
                    "model": "openai/whisper-large-v3",
                    "response_format": "verbose_json",
                },
            )
            response.raise_for_status()
            result = response.json()

            # Clear the buffer so the next call only transcribes new audio
            self._buffer = b""

            segments = result.get("segments", [])
            if not segments:
                # Fallback: API returned plain text without segments
                text = result.get("text", "").strip()
                if text:
                    yield TranscriptSegment(
                        meeting_id=self._meeting_id,
                        speaker_id=None,
                        text=text,
                        start_time=0.0,
                        end_time=0.01,
                        confidence=1.0,
                    )
                return

            for seg in segments:
                end_time = seg.get("end", 0.0)
                start_time = seg.get("start", 0.0)
                if end_time <= start_time:
                    end_time = start_time + 0.01

                # avg_logprob is negative; convert to 0.0-1.0 range
                raw_logprob = seg.get("avg_logprob")
                if raw_logprob is not None:
                    confidence = max(0.0, min(1.0, math.exp(raw_logprob)))
                else:
                    confidence = 1.0

                yield TranscriptSegment(
                    meeting_id=self._meeting_id,
                    speaker_id=None,
                    text=seg.get("text", "").strip(),
                    start_time=start_time,
                    end_time=end_time,
                    confidence=confidence,
                )
        finally:
            import os

            os.unlink(tmp.name)

    async def close(self) -> None:
        """Clear the audio buffer and close the HTTP client."""
        self._buffer = b""
        self._running = False
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        logger.info("Remote Whisper streaming session closed.")
