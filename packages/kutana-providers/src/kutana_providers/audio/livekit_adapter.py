"""LiveKit audio adapter — subscribes to room tracks, pipes PCM16 to AudioPipeline."""

from __future__ import annotations

import array
import asyncio
import logging
from typing import Any

from livekit import rtc

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional import of AudioAdapter base class from audio-service.
# In the full deployment both packages are installed together; in isolated
# testing the stub below allows the module to load standalone.
# ---------------------------------------------------------------------------
try:
    from audio_service.audio_adapter import AudioAdapter
    from audio_service.audio_pipeline import AudioPipeline
except ImportError:  # pragma: no cover — only missing in isolated unit tests

    class AudioAdapter:  # type: ignore[no-redef]
        """Minimal stub used when audio-service is not installed."""

        def __init__(self, pipeline: Any) -> None:
            self._pipeline = pipeline

        async def start(self) -> None:
            raise NotImplementedError

        async def stop(self) -> None:
            raise NotImplementedError

    AudioPipeline = Any  # type: ignore[misc, assignment]


class LiveKitAudioAdapter(AudioAdapter):
    """Subscribe to LiveKit room audio tracks and pipe PCM16 16 kHz mono to AudioPipeline.

    Each remote participant that publishes an audio track gets its own
    async consumer task.  The consumer reads ``AudioFrame`` objects from
    an ``rtc.AudioStream``, resamples/downmixes as needed, and forwards
    the resulting PCM16 bytes to :meth:`AudioPipeline.process_audio`.

    Args:
        pipeline: The AudioPipeline that receives PCM16 16 kHz mono audio.
        room: A connected (or pre-connected) ``livekit.rtc.Room``.
        target_sample_rate: Desired output sample rate in Hz (default 16 000).
    """

    def __init__(
        self,
        pipeline: AudioPipeline,
        room: rtc.Room,
        *,
        target_sample_rate: int = 16_000,
    ) -> None:
        super().__init__(pipeline)
        self._room = room
        self._target_sample_rate = target_sample_rate
        # Maps participant identity → active consumer asyncio.Task
        self._consumers: dict[str, asyncio.Task[None]] = {}

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Register event callbacks and attach to any already-connected tracks.

        Registers ``track_subscribed`` and ``participant_disconnected`` event
        handlers, then iterates ``room.remote_participants`` to pick up tracks
        that were published before :meth:`start` was called.
        """
        self._room.on("track_subscribed", self._on_track_subscribed_sync)
        self._room.on("participant_disconnected", self._on_participant_disconnected_sync)

        # Handle participants/tracks already present when start() is called.
        for _identity, participant in self._room.remote_participants.items():
            for _tid, publication in participant.track_publications.items():
                if (
                    publication.track is not None
                    and publication.track.kind == rtc.TrackKind.KIND_AUDIO
                ):
                    await self._on_track_subscribed(
                        publication.track,
                        publication,
                        participant,
                    )

        logger.info(
            "LiveKitAudioAdapter started — monitoring %d existing participant(s)",
            len(self._consumers),
        )

    async def stop(self) -> None:
        """Cancel all active consumer tasks and clean up event handlers.

        Attempts graceful cancellation; waits for each task to finish.
        """
        self._room.off("track_subscribed", self._on_track_subscribed_sync)
        self._room.off("participant_disconnected", self._on_participant_disconnected_sync)

        tasks = list(self._consumers.values())
        self._consumers.clear()

        for task in tasks:
            task.cancel()

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        logger.info("LiveKitAudioAdapter stopped — %d consumer(s) cancelled", len(tasks))

    # ------------------------------------------------------------------
    # Event callbacks (sync wrappers required by livekit-rtc .on() API)
    # ------------------------------------------------------------------

    def _on_track_subscribed_sync(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """Sync wrapper that schedules the async handler on the running loop."""
        asyncio.ensure_future(  # noqa: RUF006 — fire-and-forget; task tracked in _consumers
            self._on_track_subscribed(track, publication, participant)
        )

    def _on_participant_disconnected_sync(self, participant: rtc.RemoteParticipant) -> None:
        """Sync wrapper that cancels the departing participant's consumer task."""
        identity = participant.identity
        task = self._consumers.pop(identity, None)
        if task is not None:
            task.cancel()
            logger.debug("Cancelled audio consumer for disconnected participant: %s", identity)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _on_track_subscribed(
        self,
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant,
    ) -> None:
        """Spawn a consumer task for each incoming audio track.

        Args:
            track: The newly subscribed track.
            publication: The track publication (unused but required by callback signature).
            participant: The remote participant publishing the track.
        """
        if track.kind != rtc.TrackKind.KIND_AUDIO:
            return

        identity = participant.identity

        # Cancel any stale consumer for this identity before replacing it.
        existing = self._consumers.pop(identity, None)
        if existing is not None:
            existing.cancel()

        task = asyncio.ensure_future(self._consume_track(track, identity))
        self._consumers[identity] = task
        logger.debug("Started audio consumer for participant: %s", identity)

    async def _consume_track(self, track: rtc.Track, participant_identity: str) -> None:
        """Read AudioFrames from a track and forward PCM16 16 kHz mono to the pipeline.

        Runs until the track ends or the task is cancelled.

        Args:
            track: The audio track to consume.
            participant_identity: Identity string used for logging.
        """
        audio_stream = rtc.AudioStream(track)
        try:
            async for event in audio_stream:
                frame: rtc.AudioFrame = event.frame
                pcm = self._to_pcm16_16khz(frame)
                if pcm:
                    await self._pipeline.process_audio(pcm)
        except asyncio.CancelledError:
            logger.debug("Audio consumer cancelled for participant: %s", participant_identity)
        except Exception:
            logger.exception("Error in audio consumer for participant: %s", participant_identity)
        finally:
            await audio_stream.aclose()
            self._consumers.pop(participant_identity, None)

    def _to_pcm16_16khz(self, frame: rtc.AudioFrame) -> bytes:
        """Convert an AudioFrame to PCM16 16 kHz mono bytes.

        Handles:
        - Stereo → mono by averaging channels.
        - 48 kHz → 16 kHz by 3:1 decimation (every 3rd sample).
        - Already 16 kHz mono frames are returned unchanged.

        Unsupported sample rates (neither 16 kHz nor 48 kHz) are passed
        through without rate conversion after channel downmix; a warning
        is emitted once per occurrence.

        Args:
            frame: An ``rtc.AudioFrame`` whose ``data`` is a memoryview of
                int16 samples in interleaved channel order.

        Returns:
            PCM16 mono bytes at :attr:`_target_sample_rate`.
        """
        num_channels: int = frame.num_channels
        sample_rate: int = frame.sample_rate

        # --- Decode int16 samples from the memoryview ---
        samples: array.array[int] = array.array("h")
        samples.frombytes(bytes(frame.data))

        # --- Stereo (or multi-channel) → mono ---
        if num_channels > 1:
            mono: array.array[int] = array.array("h")
            for i in range(0, len(samples), num_channels):
                channel_sum = sum(samples[i : i + num_channels])
                mono.append(channel_sum // num_channels)
            samples = mono

        # --- Sample rate conversion ---
        if sample_rate == self._target_sample_rate:
            pass  # Already at target rate.
        elif sample_rate == 48_000 and self._target_sample_rate == 16_000:
            # 3:1 decimation — take every third sample.
            samples = samples[::3]
        else:
            logger.warning(
                "Unsupported sample rate %d Hz; expected 16000 or 48000. "
                "Forwarding without rate conversion.",
                sample_rate,
            )

        return samples.tobytes()
