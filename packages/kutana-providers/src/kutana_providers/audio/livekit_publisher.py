"""LiveKit audio publisher — pushes TTS PCM16 output into a LiveKit room."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from livekit import rtc

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# 20 ms frames — standard for real-time audio; AudioSource has internal pacing.
_FRAME_DURATION_MS: int = 20
# PCM16 = 2 bytes per sample per channel.
_BYTES_PER_SAMPLE: int = 2


class LiveKitAudioPublisher:
    """Publish TTS audio into a LiveKit room as a local audio track.

    Receives raw PCM16 bytes from a TTS provider (e.g. Cartesia @ 24 kHz)
    and publishes them into a LiveKit room as a ``LocalAudioTrack``.  Frames
    are split into 20 ms chunks (480 samples @ 24 kHz) before being handed
    to the ``AudioSource``.  Partial frames are buffered across calls.

    Args:
        room: A connected ``livekit.rtc.Room`` instance.
        sample_rate: PCM sample rate in Hz. Defaults to 24 000 (Cartesia native).
        num_channels: Number of audio channels. Defaults to 1 (mono).
        track_name: Name of the published audio track. Defaults to ``"agent-tts"``.
    """

    def __init__(
        self,
        room: rtc.Room,
        *,
        sample_rate: int = 24_000,
        num_channels: int = 1,
        track_name: str = "agent-tts",
    ) -> None:
        self._room = room
        self._sample_rate = sample_rate
        self._num_channels = num_channels
        self._track_name = track_name

        # 20 ms frame in samples and bytes.
        self._samples_per_frame: int = sample_rate * _FRAME_DURATION_MS // 1000
        self._bytes_per_frame: int = self._samples_per_frame * _BYTES_PER_SAMPLE * num_channels

        self._source: rtc.AudioSource | None = None
        self._track: rtc.LocalAudioTrack | None = None
        self._publication: rtc.LocalTrackPublication | None = None
        self._remainder: bytes = b""
        self._stopped: bool = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Create an AudioSource, LocalAudioTrack, and publish to the room.

        Must be called before any ``push_audio`` or ``push_audio_stream``
        calls.  Idempotent if called more than once (re-uses existing track).
        """
        self._stopped = False
        self._source = rtc.AudioSource(
            sample_rate=self._sample_rate,
            num_channels=self._num_channels,
        )
        self._track = rtc.LocalAudioTrack.create_audio_track(self._track_name, self._source)
        options = rtc.TrackPublishOptions()
        options.source = rtc.TrackSource.SOURCE_MICROPHONE

        self._publication = await self._room.local_participant.publish_track(self._track, options)
        logger.info(
            "LiveKitAudioPublisher: published track sid=%s "
            "(sample_rate=%d Hz, channels=%d, frame=%d ms)",
            self._publication.sid,
            self._sample_rate,
            self._num_channels,
            _FRAME_DURATION_MS,
        )

    async def stop(self) -> None:
        """Unpublish the audio track and release resources.

        Flushes any buffered partial frame (zero-padded to a full frame)
        before unpublishing, so the tail of a TTS utterance is not clipped.
        Safe to call if :meth:`start` was never called.
        """
        self._stopped = True

        # Flush any buffered partial frame with zero-padding.
        if self._remainder and self._source is not None:
            padding = b"\x00" * (self._bytes_per_frame - len(self._remainder))
            await self._push_frame(self._remainder + padding)
        self._remainder = b""

        if self._publication is not None:
            try:
                await self._room.local_participant.unpublish_track(self._publication.sid)
            except Exception:
                logger.exception(
                    "LiveKitAudioPublisher: error unpublishing track sid=%s",
                    self._publication.sid,
                )
            self._publication = None

        self._track = None
        self._source = None
        logger.info("LiveKitAudioPublisher: stopped")

    # ------------------------------------------------------------------
    # Audio push
    # ------------------------------------------------------------------

    async def push_audio(self, pcm_bytes: bytes) -> None:
        """Push PCM16 audio bytes into the room, chunked into 20 ms frames.

        Bytes not consumed in this call (a partial frame) are held in an
        internal buffer and prepended to the next call's data.

        Args:
            pcm_bytes: Raw PCM16 audio bytes at the configured sample rate.
        """
        if self._stopped or self._source is None:
            return

        data = self._remainder + pcm_bytes
        offset = 0

        while offset + self._bytes_per_frame <= len(data):
            await self._push_frame(data[offset : offset + self._bytes_per_frame])
            offset += self._bytes_per_frame

        self._remainder = data[offset:]

    async def push_audio_stream(self, chunks: AsyncIterator[bytes]) -> None:
        """Stream TTS audio chunks from an async iterator into the room.

        Iterates over ``chunks`` and calls :meth:`push_audio` for each.
        Exits early if :meth:`stop` is called mid-stream.

        Args:
            chunks: Async iterator yielding PCM16 audio byte chunks.
        """
        async for chunk in chunks:
            if self._stopped:
                break
            await self.push_audio(chunk)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _push_frame(self, frame_bytes: bytes) -> None:
        """Create an AudioFrame from raw bytes and capture it on the source.

        Args:
            frame_bytes: Exactly ``_bytes_per_frame`` bytes of PCM16 audio.
        """
        if self._source is None:
            return
        frame = rtc.AudioFrame.create(
            self._sample_rate, self._num_channels, self._samples_per_frame
        )
        frame.data[:] = frame_bytes
        await self._source.capture_frame(frame)
