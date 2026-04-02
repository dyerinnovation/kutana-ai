"""Deepgram real-time streaming STT provider."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from typing import TYPE_CHECKING
from urllib.parse import urlencode
from uuid import UUID, uuid4

import websockets
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from kutana_core.interfaces.stt import STTProvider
from kutana_core.models.transcript import TranscriptSegment

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from websockets.asyncio.client import ClientConnection

logger = logging.getLogger(__name__)

_DEEPGRAM_WS_URL = "wss://api.deepgram.com/v1/listen"

# KeepAlive interval — Deepgram times out after ~12s of silence.
# Sending every 8s provides comfortable headroom.
_KEEPALIVE_INTERVAL_S = 8.0

# Maximum reconnect attempts before giving up.
_MAX_RECONNECT_ATTEMPTS = 3
_RECONNECT_DELAY_S = 1.0


class DeepgramSTT(STTProvider):
    """Deepgram real-time streaming speech-to-text provider.

    Connects via WebSocket to Deepgram's live transcription API
    using the Nova-2 model with punctuation and diarization.

    Phantom word prevention:
        ``endpointing_ms`` (default 400) tells Deepgram to wait for
        400 ms of silence before finalizing an utterance.  Without this
        Deepgram uses its own default (~10-50 ms) which is too aggressive
        for meeting contexts and can commit results from brief background
        noise bursts.

        ``min_confidence`` (default 0.65) drops any final result whose
        confidence score is below the threshold.  Deepgram's confidence
        is well-calibrated: legitimate speech is typically >= 0.8;
        hallucinations from ambient noise tend to fall below 0.65.

    Connection reliability:
        A background keepalive task sends ``{"type": "KeepAlive"}``
        messages every 8 seconds when audio is not actively flowing.
        On connection loss, ``send_audio`` and ``get_transcript`` will
        attempt to reconnect transparently.
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
                from brief pauses; 300-500 ms is typical for meetings.
            min_confidence: Drop final results with confidence below this
                value.  Range [0.0, 1.0]; default 0.65.
        """
        self._api_key = api_key
        self._meeting_id = meeting_id or uuid4()
        self._endpointing_ms = endpointing_ms
        self._min_confidence = min_confidence
        self._ws: ClientConnection | None = None
        self._keepalive_task: asyncio.Task[None] | None = None
        self._last_audio_time: float = 0.0

    def _build_url(self) -> str:
        """Build the Deepgram WebSocket URL with query parameters.

        Returns:
            Full WebSocket URL with encoding and model parameters.
        """
        params = urlencode(
            {
                "model": "nova-2",
                "punctuate": "true",
                "diarize": "true",
                "encoding": "linear16",
                "sample_rate": "16000",
                "channels": "1",
                "endpointing": str(self._endpointing_ms),
                "smart_format": "true",
            }
        )
        return f"{_DEEPGRAM_WS_URL}?{params}"

    def _build_headers(self) -> dict[str, str]:
        """Build the authentication headers for Deepgram.

        Returns:
            Dictionary with Authorization header.
        """
        return {"Authorization": f"Token {self._api_key}"}

    async def _open_ws(self) -> ClientConnection:
        """Open a new WebSocket connection to Deepgram.

        Returns:
            The newly opened WebSocket connection.
        """
        return await websockets.connect(
            self._build_url(),
            additional_headers=self._build_headers(),
        )

    async def start_stream(self) -> None:
        """Open a WebSocket connection to Deepgram's live transcription API.

        Configures the stream with Nova-2 model, punctuation, and
        speaker diarization enabled.  Starts a background keepalive
        task to prevent the connection from timing out during silence.
        """
        self._ws = await self._open_ws()
        self._last_audio_time = time.monotonic()
        self._keepalive_task = asyncio.create_task(self._keepalive_loop())
        logger.info("Deepgram streaming session started.")

    async def _keepalive_loop(self) -> None:
        """Background task that sends KeepAlive messages during silence.

        Sends a ``{"type": "KeepAlive"}`` JSON message every
        ``_KEEPALIVE_INTERVAL_S`` seconds, but only when audio has not
        been sent recently.  This prevents Deepgram from closing the
        connection due to inactivity.
        """
        try:
            while True:
                await asyncio.sleep(_KEEPALIVE_INTERVAL_S)
                if self._ws is None:
                    continue
                # Only send KeepAlive if audio hasn't been sent recently
                elapsed = time.monotonic() - self._last_audio_time
                if elapsed >= _KEEPALIVE_INTERVAL_S:
                    try:
                        await self._ws.send(json.dumps({"type": "KeepAlive"}))
                        logger.debug("Sent KeepAlive to Deepgram (%.1fs since last audio)", elapsed)
                    except (ConnectionClosedError, ConnectionClosedOK):
                        logger.warning(
                            "KeepAlive failed: connection closed, will reconnect on next send"
                        )
                    except Exception:
                        logger.debug("KeepAlive send error", exc_info=True)
        except asyncio.CancelledError:
            return

    async def _reconnect(self) -> None:
        """Close the dead WebSocket and re-open a new connection.

        Retries up to ``_MAX_RECONNECT_ATTEMPTS`` times with a delay
        between attempts.  On success the keepalive task is restarted.

        Raises:
            ConnectionError: If all reconnect attempts fail.
        """
        logger.warning("Attempting Deepgram WebSocket reconnect...")

        # Tear down old connection
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                logger.debug("Error closing dead WebSocket", exc_info=True)
            self._ws = None

        # Cancel old keepalive
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._keepalive_task
            self._keepalive_task = None

        for attempt in range(1, _MAX_RECONNECT_ATTEMPTS + 1):
            try:
                self._ws = await self._open_ws()
                self._last_audio_time = time.monotonic()
                self._keepalive_task = asyncio.create_task(self._keepalive_loop())
                logger.info(
                    "Deepgram reconnected on attempt %d/%d",
                    attempt,
                    _MAX_RECONNECT_ATTEMPTS,
                )
                return
            except Exception:
                logger.warning(
                    "Reconnect attempt %d/%d failed",
                    attempt,
                    _MAX_RECONNECT_ATTEMPTS,
                    exc_info=True,
                )
                if attempt < _MAX_RECONNECT_ATTEMPTS:
                    await asyncio.sleep(_RECONNECT_DELAY_S * attempt)

        msg = f"Failed to reconnect to Deepgram after {_MAX_RECONNECT_ATTEMPTS} attempts"
        raise ConnectionError(msg)

    async def send_audio(self, chunk: bytes) -> None:
        """Send raw audio bytes to Deepgram via WebSocket.

        On ``ConnectionClosedError``, attempts a reconnect and retries
        the send once.  Deepgram accepts raw PCM audio bytes directly,
        no base64 encoding is required.

        Args:
            chunk: Raw PCM16 audio bytes at 16kHz mono.
        """
        if self._ws is None:
            msg = "Stream not started. Call start_stream() first."
            raise RuntimeError(msg)

        try:
            await self._ws.send(chunk)
            self._last_audio_time = time.monotonic()
        except (ConnectionClosedError, ConnectionClosedOK):
            logger.warning("send_audio: connection lost, reconnecting")
            await self._reconnect()
            await self._ws.send(chunk)  # type: ignore[union-attr]
            self._last_audio_time = time.monotonic()

    async def get_transcript(self) -> AsyncIterator[TranscriptSegment]:
        """Yield finalized transcript segments from Deepgram.

        Reads WebSocket JSON messages and yields a TranscriptSegment
        for each result where is_final is true.  On connection loss,
        attempts a reconnect and resumes listening.

        Yields:
            TranscriptSegment with speaker attribution, text,
            timing, and confidence from finalized results.
        """
        if self._ws is None:
            msg = "Stream not started. Call start_stream() first."
            raise RuntimeError(msg)

        reconnect_attempts = 0
        while True:
            try:
                async for raw_message in self._ws:  # type: ignore[union-attr]
                    reconnect_attempts = 0  # reset on successful recv
                    segment = self._parse_message(raw_message)
                    if segment is not None:
                        yield segment
                # WebSocket closed normally (server side) — try reconnect
                logger.warning("Deepgram WebSocket closed normally, reconnecting")
                await self._reconnect()
                reconnect_attempts += 1
            except (ConnectionClosedError, ConnectionClosedOK):
                reconnect_attempts += 1
                if reconnect_attempts > _MAX_RECONNECT_ATTEMPTS:
                    logger.error(
                        "get_transcript: exhausted %d reconnect attempts",
                        _MAX_RECONNECT_ATTEMPTS,
                    )
                    return
                logger.warning(
                    "get_transcript: connection lost (attempt %d/%d), reconnecting",
                    reconnect_attempts,
                    _MAX_RECONNECT_ATTEMPTS,
                )
                try:
                    await self._reconnect()
                except ConnectionError:
                    logger.error("get_transcript: reconnect failed, stopping")
                    return

    def _parse_message(self, raw_message: str | bytes) -> TranscriptSegment | None:
        """Parse a Deepgram JSON message into a TranscriptSegment.

        Args:
            raw_message: Raw JSON string from Deepgram WebSocket.

        Returns:
            A TranscriptSegment if the message is a final result with
            sufficient confidence, otherwise None.
        """
        message = json.loads(raw_message)

        # Deepgram wraps results in a channel->alternatives structure
        channel = message.get("channel", {})
        alternatives = channel.get("alternatives", [])
        if not alternatives:
            return None

        is_final: bool = message.get("is_final", False)
        if not is_final:
            return None

        best = alternatives[0]
        transcript_text: str = best.get("transcript", "").strip()
        if not transcript_text:
            return None

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
            return None

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

        return TranscriptSegment(
            meeting_id=self._meeting_id,
            speaker_id=speaker,
            text=transcript_text,
            start_time=start_time,
            end_time=end_time,
            confidence=confidence,
        )

    async def close(self) -> None:
        """Send a close message, cancel keepalive, and shut down the WebSocket."""
        # Cancel keepalive task first
        if self._keepalive_task is not None:
            self._keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._keepalive_task
            self._keepalive_task = None

        if self._ws is not None:
            try:
                # Deepgram expects a CloseStream message to signal end
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
