"""Remote speech-to-text provider using a vLLM-served Whisper model."""

from __future__ import annotations

import asyncio
import logging
import math
import re
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

# ---------------------------------------------------------------------------
# Known Whisper hallucination phrases
# ---------------------------------------------------------------------------
# Whisper-large-v3 reliably hallucinates these exact phrases when given audio
# that consists mostly of silence, background noise, or HVAC/fan hiss.
# Comparison is case-insensitive and strips trailing punctuation.

_HALLUCINATION_PHRASES: frozenset[str] = frozenset(
    {
        "i'm sorry",
        "i am sorry",
        "thank you",
        "thanks for watching",
        "please subscribe",
        "please like and subscribe",
        "you",
        "okay",
        "ok",
        "bye",
        "bye bye",
        "see you",
        # Dash-prefixed variants emitted by Whisper on some audio
        "- i'm sorry",
        "- thank you",
    }
)

# Compiled pattern: detects repetition of a short phrase within a single
# segment (e.g. "I'm sorry. I'm sorry." or "- I'm sorry. - I'm sorry.").
# Matches when the same run of ≥ 4 non-whitespace chars appears 2+ times.
_REPETITION_RE = re.compile(r"(\S{4,}.{0,10}?)\s*[-–—.!?]?\s*\1", re.IGNORECASE)


class WhisperRemoteSTT(STTProvider):
    """Remote STT provider that calls an OpenAI-compatible Whisper API.

    Buffers raw PCM16 16kHz mono audio and transcribes it by POSTing
    a WAV file to a remote ``/audio/transcriptions`` endpoint (e.g.
    vLLM serving ``openai/whisper-large-v3`` on DGX Spark).

    Uses ``aiohttp`` instead of ``httpx`` because httpx hangs on
    IPv6 link-local addresses (no Happy Eyeballs support).

    Hallucination filtering — five independent gates applied in order:

    1. **Segment duration gate** — Drops segments shorter than
       ``min_segment_duration_s`` (default 0.15 s).  When Whisper enters
       its fallback temperature-sampling mode on ambient noise it floods
       the output with dozens of tiny segments (observed: 53 × "I'm sorry."
       from 4.6 s of audio ≈ 0.087 s each).  This single gate eliminates
       the entire flood without touching real-speech segments.

    2. **``no_speech_prob`` gate** — Whisper's ``verbose_json`` response
       includes ``no_speech_prob`` per segment.  Segments at or above
       ``no_speech_threshold`` (default 0.35) are dropped.

    3. **Compression ratio gate** — Repetitive hallucinated text compresses
       extremely well.  Segments with ``compression_ratio`` above
       ``compression_ratio_threshold`` (default 2.4, Whisper's own default)
       are dropped.

    4. **Known phrase blocklist** — Exact-match (case-insensitive, stripped
       of punctuation) against ``_HALLUCINATION_PHRASES``.

    5. **Intra-segment repetition detector** — Regex-based check for phrases
       that repeat within a single segment text (e.g. "I'm sorry. I'm sorry.").

    Additionally, cross-call deduplication prevents the same text from
    appearing twice in a row across consecutive 5-second transcription windows.
    """

    def __init__(
        self,
        api_url: str,
        meeting_id: UUID | None = None,
        request_timeout_s: float = 60.0,
        no_speech_threshold: float = 0.35,
        min_confidence: float = 0.0,
        compression_ratio_threshold: float = 2.4,
        min_segment_duration_s: float = 0.15,
    ) -> None:
        """Initialize the remote Whisper STT provider.

        Args:
            api_url: Base URL of the OpenAI-compatible API
                (e.g. ``http://spark-b0f2.local/convene-stt/v1``).
            meeting_id: Optional meeting ID to tag transcript segments.
            request_timeout_s: Per-request timeout in seconds for the
                Whisper HTTP POST call.
            no_speech_threshold: Drop segments where Whisper's own
                ``no_speech_prob`` is at or above this value.  Range
                [0.0, 1.0]; default 0.35 (lowered from 0.5 — the
                "I'm sorry" hallucinations were observed at 0.35–0.50).
            min_confidence: Drop segments with confidence (derived from
                ``avg_logprob``) below this value.  Default 0.0 disables
                the filter; raise to ~0.3 for stricter filtering.
            compression_ratio_threshold: Drop segments whose
                ``compression_ratio`` exceeds this value.  Whisper uses
                2.4 internally; repetitive hallucinations score well above
                this.  Default 2.4.
            min_segment_duration_s: Drop segments shorter than this many
                seconds.  Real speech is never this short; the "I'm sorry"
                hallucination flood produces segments of ~0.09 s.
                Default 0.15 s.
        """
        self._api_url = api_url.rstrip("/")
        self._meeting_id = meeting_id or uuid4()
        self._request_timeout_s = request_timeout_s
        self._no_speech_threshold = no_speech_threshold
        self._min_confidence = min_confidence
        self._compression_ratio_threshold = compression_ratio_threshold
        self._min_segment_duration_s = min_segment_duration_s
        self._buffer = b""
        self._running = False
        self._session: aiohttp.ClientSession | None = None
        self._last_text: str = ""  # Cross-call deduplication

    async def start_stream(self) -> None:
        """Initialize a new streaming transcription session."""
        self._buffer = b""
        self._running = True
        self._last_text = ""
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

    def _is_hallucination(self, text: str) -> str | None:
        """Check text against known hallucination patterns.

        Args:
            text: Stripped segment text to check.

        Returns:
            A string describing why the text was flagged, or ``None`` if
            the text appears to be real speech.
        """
        normalized = text.strip().rstrip(".,!?").lower()

        if normalized in _HALLUCINATION_PHRASES:
            return f"known phrase: {normalized!r}"

        if _REPETITION_RE.search(text):
            return f"repeated phrase: {text[:60]!r}"

        return None

    async def get_transcript(self) -> AsyncIterator[TranscriptSegment]:
        """Transcribe buffered audio via the remote Whisper API.

        Writes the PCM16 buffer to a temporary WAV file, POSTs it
        to the remote endpoint, and yields a ``TranscriptSegment``
        for each detected segment after applying all hallucination
        filters.

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
                # Fallback: API returned plain text without segments.
                # Apply hallucination filtering before yielding.
                text = result.get("text", "").strip()
                if text:
                    hallucination_reason = self._is_hallucination(text)
                    if hallucination_reason:
                        logger.info(
                            "Whisper fallback text dropped (%s): %r",
                            hallucination_reason,
                            text[:80],
                        )
                    elif text == self._last_text:
                        logger.debug(
                            "Whisper fallback text deduplicated: %r",
                            text[:60],
                        )
                    else:
                        logger.info(
                            "Whisper returned plain text (no segments), len=%d",
                            len(text),
                        )
                        self._last_text = text
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
            dropped_count = 0
            drop_reasons: dict[str, int] = {}

            for seg in segments:
                end_time = seg.get("end", 0.0)
                start_time = seg.get("start", 0.0)
                if end_time <= start_time:
                    end_time = start_time + 0.01

                # ------------------------------------------------------------------
                # Gate 1: Segment duration
                # When Whisper's fallback temperature-sampling activates on ambient
                # noise, it floods the output with many tiny segments (observed:
                # 53 × "I'm sorry." in 4.6 s = ~0.087 s each).  Real speech
                # segments are always ≥ ~0.15 s for the shortest syllable.
                # ------------------------------------------------------------------
                duration = end_time - start_time
                if duration < self._min_segment_duration_s:
                    key = "too_short"
                    drop_reasons[key] = drop_reasons.get(key, 0) + 1
                    dropped_count += 1
                    continue

                # ------------------------------------------------------------------
                # Gate 2: no_speech_prob
                # ------------------------------------------------------------------
                no_speech_prob: float = seg.get("no_speech_prob", 0.0)
                if no_speech_prob >= self._no_speech_threshold:
                    key = "no_speech_prob"
                    drop_reasons[key] = drop_reasons.get(key, 0) + 1
                    dropped_count += 1
                    continue

                # ------------------------------------------------------------------
                # Gate 3: Compression ratio
                # High compression = repetitive text = hallucination.
                # ------------------------------------------------------------------
                compression_ratio: float = seg.get("compression_ratio", 0.0)
                if (
                    compression_ratio > 0.0
                    and compression_ratio > self._compression_ratio_threshold
                ):
                    key = "compression_ratio"
                    drop_reasons[key] = drop_reasons.get(key, 0) + 1
                    dropped_count += 1
                    continue

                # ------------------------------------------------------------------
                # Gate 4: avg_logprob confidence floor
                # ------------------------------------------------------------------
                raw_logprob = seg.get("avg_logprob")
                if raw_logprob is not None:
                    confidence = max(0.0, min(1.0, math.exp(raw_logprob)))
                else:
                    confidence = 1.0

                if confidence < self._min_confidence:
                    key = "confidence"
                    drop_reasons[key] = drop_reasons.get(key, 0) + 1
                    dropped_count += 1
                    continue

                text = seg.get("text", "").strip()
                if not text:
                    continue

                # ------------------------------------------------------------------
                # Gate 5: Known-phrase blocklist + intra-segment repetition
                # ------------------------------------------------------------------
                hallucination_reason = self._is_hallucination(text)
                if hallucination_reason:
                    key = "hallucination"
                    drop_reasons[key] = drop_reasons.get(key, 0) + 1
                    dropped_count += 1
                    logger.debug(
                        "Dropping segment (%s): %r",
                        hallucination_reason,
                        text[:60],
                    )
                    continue

                # ------------------------------------------------------------------
                # Cross-call deduplication
                # ------------------------------------------------------------------
                if text == self._last_text:
                    key = "duplicate"
                    drop_reasons[key] = drop_reasons.get(key, 0) + 1
                    dropped_count += 1
                    continue

                self._last_text = text
                yield TranscriptSegment(
                    meeting_id=self._meeting_id,
                    speaker_id=None,
                    text=text,
                    start_time=start_time,
                    end_time=end_time,
                    confidence=confidence,
                )
                seg_count += 1

            if dropped_count:
                logger.info(
                    "Whisper yielded %d segments, dropped %d — reasons: %s",
                    seg_count,
                    dropped_count,
                    drop_reasons,
                )
            else:
                logger.info("Whisper yielded %d segments", seg_count)

        finally:
            import os

            os.unlink(tmp.name)

    async def close(self) -> None:
        """Clear the audio buffer and close the HTTP session."""
        self._buffer = b""
        self._running = False
        self._last_text = ""
        if self._session is not None:
            await self._session.close()
            self._session = None
        logger.info("Remote Whisper streaming session closed.")
