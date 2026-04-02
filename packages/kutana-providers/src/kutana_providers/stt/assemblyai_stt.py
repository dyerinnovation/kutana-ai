"""AssemblyAI real-time streaming STT provider."""

from __future__ import annotations

import base64
import json
import logging
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import websockets

from kutana_core.interfaces.stt import STTProvider
from kutana_core.models.transcript import TranscriptSegment

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

_REALTIME_WS_URL = "wss://api.assemblyai.com/v2/realtime/ws"
_SAMPLE_RATE = 16000


class AssemblyAISTT(STTProvider):
    """AssemblyAI real-time streaming speech-to-text provider.

    Connects via WebSocket to AssemblyAI's real-time transcription API
    and yields finalized transcript segments with speaker diarization.
    """

    def __init__(self, api_key: str, meeting_id: UUID | None = None) -> None:
        """Initialize the AssemblyAI STT provider.

        Args:
            api_key: AssemblyAI API key for authentication.
            meeting_id: Optional meeting ID to tag transcript segments.
        """
        self._api_key = api_key
        self._meeting_id = meeting_id or uuid4()
        self._ws: ClientConnection | None = None

    async def start_stream(self) -> None:
        """Open a WebSocket connection to AssemblyAI real-time API.

        Establishes the streaming session with speaker diarization
        enabled at 16kHz sample rate.
        """
        url = f"{_REALTIME_WS_URL}?sample_rate={_SAMPLE_RATE}"
        extra_headers = {"Authorization": self._api_key}
        self._ws = await websockets.connect(
            url,
            additional_headers=extra_headers,
        )
        # Wait for the SessionBegins message
        raw = await self._ws.recv()
        msg = json.loads(raw)
        if msg.get("message_type") != "SessionBegins":
            logger.warning(
                "Expected SessionBegins, got: %s",
                msg.get("message_type"),
            )
        logger.info(
            "AssemblyAI session started: %s",
            msg.get("session_id", "unknown"),
        )

    async def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk to AssemblyAI via WebSocket.

        The audio is base64-encoded and sent as a JSON message
        per AssemblyAI's real-time protocol.

        Args:
            chunk: Raw PCM16 audio bytes at 16kHz mono.
        """
        if self._ws is None:
            msg = "Stream not started. Call start_stream() first."
            raise RuntimeError(msg)

        encoded = base64.b64encode(chunk).decode("utf-8")
        payload = json.dumps({"audio_data": encoded})
        await self._ws.send(payload)

    async def get_transcript(self) -> AsyncIterator[TranscriptSegment]:
        """Yield finalized transcript segments from AssemblyAI.

        Reads WebSocket messages continuously and yields a
        TranscriptSegment for each FinalTranscript message.

        Yields:
            TranscriptSegment with speaker label, text, timing, and
            confidence from the finalized transcription.
        """
        if self._ws is None:
            msg = "Stream not started. Call start_stream() first."
            raise RuntimeError(msg)

        async for raw_message in self._ws:
            message = json.loads(raw_message)
            message_type = message.get("message_type", "")

            if message_type == "SessionTerminated":
                logger.info("AssemblyAI session terminated.")
                break

            if message_type != "FinalTranscript":
                continue

            text = message.get("text", "").strip()
            if not text:
                continue

            audio_start: float = message.get("audio_start", 0) / 1000.0
            audio_end: float = message.get("audio_end", 0) / 1000.0
            confidence: float = message.get("confidence", 1.0)

            # Extract speaker from words if diarization is enabled
            words = message.get("words", [])
            speaker: str | None = None
            if words:
                speaker = words[0].get("speaker", None)

            # Guard against zero-length segments
            if audio_end <= audio_start:
                audio_end = audio_start + 0.01

            yield TranscriptSegment(
                meeting_id=self._meeting_id,
                speaker_id=speaker,
                text=text,
                start_time=audio_start,
                end_time=audio_end,
                confidence=confidence,
            )

    async def close(self) -> None:
        """Send a terminate message and close the WebSocket connection."""
        if self._ws is not None:
            try:
                terminate_msg = json.dumps({"terminate_session": True})
                await self._ws.send(terminate_msg)
            except Exception:
                logger.debug(
                    "Could not send terminate message",
                    exc_info=True,
                )
            finally:
                await self._ws.close()
                self._ws = None
                logger.info("AssemblyAI WebSocket connection closed.")
