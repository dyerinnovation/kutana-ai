"""Remote speech-to-text provider using a vLLM-served Whisper model."""

from __future__ import annotations

import asyncio
import logging
import math
import tempfile
import time
import wave
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import aiohttp

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

    Uses ``aiohttp`` instead of ``httpx`` because httpx hangs on
    IPv6 link-local addresses (no Happy Eyeballs support).
    """

    def __init__(
        self,
        api_url: str,
        meeting_id: UUID | None = None,
        request_timeout_s: float = 60.0,
    ) -> None:
        """Initialize the remote Whisper STT provider.

        Args:
            api_url: Base URL of the OpenAI-compatible API
                (e.g. ``http://spark-b0f2.local/convene-stt/v1``).
            meeting_id: Optional meeting ID to tag transcript segments.
            request_timeout_s: Per-request timeout in seconds for the
                Whisper HTTP POST call.
        """
        self._api_url = api_url.rstrip("/")
        self._meeting_id = meeting_id or uuid4()
        self._request_timeout_s = request_timeout_s
        self._buffer = b""
        self._running = False
        self._session: aiohttp.ClientSession | None = None

    async def start_stream(self) -> None:
        """Initialize a new streaming transcription session."""
        self._buffer = b""
        self._running = True
        timeout = aiohttp.ClientTimeout(total=self._request_timeout_s)
        self._session = aiohttp.ClientSession(timeout=timeout)
        logger.info("Remote Whisper streaming started (api_url=%s)", self._api_url)

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
        if self._session is None:
            msg = "Session not initialized. Call start_stream() first."
            raise RuntimeError(msg)

        if not self._buffer:
            logger.debug("get_transcript called with empty buffer, skipping")
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

            audio_duration_s = len(self._buffer) / 32000
            post_url = f"{self._api_url}/audio/transcriptions"
            logger.info(
                "Whisper POST: url=%s buffer_size=%d audio_duration=%.2fs",
                post_url, len(self._buffer), audio_duration_s,
            )
            t0 = time.monotonic()

            try:
                form = aiohttp.FormData()
                form.add_field(
                    "file",
                    wav_bytes,
                    filename="audio.wav",
                    content_type="audio/wav",
                )
                form.add_field("model", "openai/whisper-large-v3")
                form.add_field("response_format", "verbose_json")
                form.add_field("language", "en")

                async with self._session.post(post_url, data=form) as response:
                    response.raise_for_status()
                    elapsed = time.monotonic() - t0
                    result = await response.json()
                    logger.info(
                        "Whisper POST response: status=%d elapsed=%.2fs",
                        response.status, elapsed,
                    )
            except asyncio.TimeoutError:
                logger.error(
                    "Whisper POST timed out after %.1fs (url=%s)",
                    self._request_timeout_s, post_url,
                )
                self._buffer = b""
                return
            except aiohttp.ClientError:
                elapsed = time.monotonic() - t0
                logger.exception(
                    "Whisper POST failed after %.2fs (url=%s)",
                    elapsed, post_url,
                )
                self._buffer = b""
                return

            # Clear the buffer so the next call only transcribes new audio
            self._buffer = b""

            segments = result.get("segments", [])
            if not segments:
                # Fallback: API returned plain text without segments
                text = result.get("text", "").strip()
                if text:
                    logger.info("Whisper returned plain text (no segments), len=%d", len(text))
                    yield TranscriptSegment(
                        meeting_id=self._meeting_id,
                        speaker_id=None,
                        text=text,
                        start_time=0.0,
                        end_time=0.01,
                        confidence=1.0,
                    )
                else:
                    logger.info("Whisper returned no segments and no text")
                return

            seg_count = 0
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
                seg_count += 1
            logger.info("Whisper yielded %d segments", seg_count)
        finally:
            import os

            os.unlink(tmp.name)

    async def close(self) -> None:
        """Clear the audio buffer and close the HTTP session."""
        self._buffer = b""
        self._running = False
        if self._session is not None:
            await self._session.close()
            self._session = None
        logger.info("Remote Whisper streaming session closed.")
