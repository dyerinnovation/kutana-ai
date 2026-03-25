"""Deepgram real-time streaming STT provider."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlencode
from uuid import UUID, uuid4

import websockets

from convene_core.interfaces.stt import STTProvider
from convene_core.models.transcript import TranscriptSegment

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

_DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"


class DeepgramSTT(STTProvider):
    """Deepgram real-time streaming speech-to-text provider.

    Connects via WebSocket to Deepgram's live transcription API
    using the Nova-2 model with punctuation and diarization.

    Phantom word prevention:
        ``endpointing_ms`` (default 400) tells Deepgram to wait for
        400 ms of silence before finalizing an utterance.  Without this
        Deepgram uses its own default (~10–50 ms) which is too aggressive
        for meeting contexts and can commit results from brief background
        noise bursts.

        ``min_confidence`` (default 0.65) drops any final result whose
        confidence score is below the threshold.  Deepgram's confidence
        is well-calibrated: legitimate speech is typically ≥ 0.8;
        hallucinations from ambient noise tend to fall below 0.65.
    """

    def __init__(
        self,
        api_key: str,
        meeting_id: UUID | None = None,
        endpointing_ms: int = 400,
        min_confidence: float = 0.65,
    ) -> None:
        """Initialize the Deepgram STT provider.

        Args:
            api_key: Deepgram API key for authentication.
            meeting_id: Optional meeting ID to tag transcript segments.
            endpointing_ms: Milliseconds of silence Deepgram waits before
                finalizing an utterance.  Higher values reduce false finals
                from brief pauses; 300–500 ms is typical for meetings.
            min_confidence: Drop final results with confidence below this
                value.  Range [0.0, 1.0]; default 0.65.
        """
        self._api_key = api_key
        self._meeting_id = meeting_id or uuid4()
        self._endpointing_ms = endpointing_ms
        self._min_confidence = min_confidence
        self._ws: ClientConnection | None = None

    async def start_stream(self) -> None:
        """Open a WebSocket connection to Deepgram's live transcription API.

        Configures the stream with Nova-2 model, punctuation, and
        speaker diarization enabled.
        """
        params = urlencode(
            {
                "model": "nova-2",
                "punctuate": "true",
                "diarize": "true",
                "encoding": "linear16",
                "sample_rate": "16000",
                "channels": "1",
                # endpointing: ms of silence before Deepgram commits a final result.
                # The default is very short (~10 ms) which causes false finals from
                # brief background noise bursts in meeting environments.
                "endpointing": str(self._endpointing_ms),
                # smart_format: improves number/date/punctuation formatting.
                "smart_format": "true",
            }
        )
        url = f"{_DEEPGRAM_WS_URL}?{params}"
        extra_headers = {"Authorization": f"Token {self._api_key}"}
        self._ws = await websockets.connect(
            url,
            additional_headers=extra_headers,
        )
        logger.info("Deepgram streaming session started.")

    async def send_audio(self, chunk: bytes) -> None:
        """Send raw audio bytes to Deepgram via WebSocket.

        Deepgram accepts raw PCM audio bytes directly, no base64
        encoding is required.

        Args:
            chunk: Raw PCM16 audio bytes at 16kHz mono.
        """
        if self._ws is None:
            msg = "Stream not started. Call start_stream() first."
            raise RuntimeError(msg)

        await self._ws.send(chunk)

    async def get_transcript(self) -> AsyncIterator[TranscriptSegment]:
        """Yield finalized transcript segments from Deepgram.

        Reads WebSocket JSON messages and yields a TranscriptSegment
        for each result where is_final is true.

        Yields:
            TranscriptSegment with speaker attribution, text,
            timing, and confidence from finalized results.
        """
        if self._ws is None:
            msg = "Stream not started. Call start_stream() first."
            raise RuntimeError(msg)

        async for raw_message in self._ws:
            message = json.loads(raw_message)

            # Deepgram wraps results in a channel->alternatives structure
            channel = message.get("channel", {})
            alternatives = channel.get("alternatives", [])
            if not alternatives:
                continue

            is_final: bool = message.get("is_final", False)
            if not is_final:
                continue

            best = alternatives[0]
            transcript_text: str = best.get("transcript", "").strip()
            if not transcript_text:
                continue

            confidence: float = best.get("confidence", 1.0)

            # Drop low-confidence results — these are typically background noise
            # or brief ambient sounds being misidentified as speech.
            if confidence < self._min_confidence:
                logger.debug(
                    "Dropping low-confidence result (%.2f < %.2f): %r",
                    confidence,
                    self._min_confidence,
                    transcript_text[:60],
                )
                continue

            # Extract timing from the first and last word
            words: list[dict[str, object]] = best.get("words", [])
            start_time = 0.0
            end_time = 0.0
            speaker: str | None = None

            if words:
                first_word = words[0]
                last_word = words[-1]
                start_time = float(first_word.get("start", 0.0))
                end_time = float(last_word.get("end", 0.0))
                # Deepgram diarization returns speaker as int
                raw_speaker = first_word.get("speaker")
                if raw_speaker is not None:
                    speaker = f"speaker_{raw_speaker}"

            # Guard against zero-length segments
            if end_time <= start_time:
                end_time = start_time + 0.01

            yield TranscriptSegment(
                meeting_id=self._meeting_id,
                speaker_id=speaker,
                text=transcript_text,
                start_time=start_time,
                end_time=end_time,
                confidence=confidence,
            )

    async def close(self) -> None:
        """Send a close message and shut down the WebSocket connection."""
        if self._ws is not None:
            try:
                # Deepgram expects an empty byte string to signal end
                close_msg = json.dumps({"type": "CloseStream"})
                await self._ws.send(close_msg)
            except Exception:
                logger.debug(
                    "Could not send close message",
                    exc_info=True,
                )
            finally:
                await self._ws.close()
                self._ws = None
                logger.info("Deepgram WebSocket connection closed.")
