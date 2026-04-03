"""AudioBridge -- manages per-meeting AudioPipeline instances."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from audio_service.audio_pipeline import AudioPipeline
from audio_service.event_publisher import EventPublisher
from audio_service.main import AudioServiceSettings, _create_stt_provider

if TYPE_CHECKING:
    from uuid import UUID

logger = logging.getLogger(__name__)


class AudioBridge:
    """Manages AudioPipeline instances per meeting.

    Creates an STT pipeline when an agent joins a meeting,
    forwards agent audio to the pipeline, and runs a background
    task consuming transcript segments (which flow through Redis
    back to the EventRelay).

    Attributes:
        _pipelines: Active AudioPipeline per meeting.
        _segment_tasks: Background tasks consuming transcript segments.
        _event_publisher: Shared EventPublisher for all pipelines.
        _stt_settings: STT configuration from AudioServiceSettings.
    """

    def __init__(
        self,
        redis_url: str,
        stt_provider: str,
        stt_api_key: str,
        whisper_model_size: str,
        whisper_api_url: str,
        transcription_interval_s: float = 5.0,
    ) -> None:
        """Initialise the audio bridge.

        Args:
            redis_url: Redis connection URL for event publishing.
            stt_provider: STT provider name.
            stt_api_key: API key for cloud STT providers.
            whisper_model_size: Whisper model size for local whisper.
            whisper_api_url: Remote Whisper API URL.
            transcription_interval_s: Seconds between transcription passes.
        """
        self._event_publisher = EventPublisher(redis_url=redis_url)
        self._stt_settings = AudioServiceSettings(
            redis_url=redis_url,
            stt_provider=stt_provider,
            stt_api_key=stt_api_key,
            whisper_model_size=whisper_model_size,
            whisper_api_url=whisper_api_url,
        )
        self._transcription_interval_s = transcription_interval_s
        self._pipelines: dict[UUID, AudioPipeline] = {}
        self._segment_tasks: dict[UUID, asyncio.Task[None]] = {}
        logger.info(
            "AudioBridge initialized (stt_provider=%s, whisper_api_url=%s)",
            stt_provider,
            whisper_api_url,
        )
        if stt_provider == "whisper-remote" and not whisper_api_url:
            logger.warning("whisper-remote selected but whisper_api_url is empty!")

    def _recreate_stt_provider(self, meeting_id: UUID) -> object:
        """Create a fresh STT provider instance from settings.

        Args:
            meeting_id: The meeting ID for the new provider.

        Returns:
            A new STT provider instance.
        """
        return _create_stt_provider(self._stt_settings, meeting_id)

    async def ensure_pipeline(
        self, meeting_id: UUID, speaker_name: str | None = None
    ) -> None:
        """Create an STT pipeline for a meeting if one doesn't exist.

        Args:
            meeting_id: The meeting to create a pipeline for.
            speaker_name: Display name of the speaker for this pipeline.
        """
        if meeting_id in self._pipelines:
            return

        stt_provider = _create_stt_provider(self._stt_settings, meeting_id)
        pipeline = AudioPipeline(
            stt_provider=stt_provider,
            event_publisher=self._event_publisher,
            meeting_id=meeting_id,
            speaker_name=speaker_name,
        )
        self._pipelines[meeting_id] = pipeline

        # Eagerly connect to STT provider to avoid cold start latency
        await pipeline.start()

        # Start background task to consume transcript segments
        task = asyncio.create_task(self._consume_segments(meeting_id, pipeline))
        self._segment_tasks[meeting_id] = task

        logger.info("Created audio pipeline for meeting %s", meeting_id)

    async def process_audio(self, meeting_id: UUID, audio_bytes: bytes) -> None:
        """Forward PCM16 audio to the meeting's pipeline.

        Args:
            meeting_id: The meeting the audio belongs to.
            audio_bytes: Raw PCM16 16kHz mono audio bytes.
        """
        pipeline = self._pipelines.get(meeting_id)
        if pipeline is None:
            logger.warning(
                "No pipeline for meeting %s, dropping audio",
                meeting_id,
            )
            return
        await pipeline.process_audio(audio_bytes)

    async def close_pipeline(self, meeting_id: UUID) -> None:
        """Close the pipeline for a meeting and cancel its segment consumer.

        Args:
            meeting_id: The meeting whose pipeline to close.
        """
        # Cancel segment consumer task
        task = self._segment_tasks.pop(meeting_id, None)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # Close the pipeline
        pipeline = self._pipelines.pop(meeting_id, None)
        if pipeline is not None:
            await pipeline.close()
            logger.info("Closed audio pipeline for meeting %s", meeting_id)

    async def close(self) -> None:
        """Close all pipelines and the shared EventPublisher."""
        meeting_ids = list(self._pipelines.keys())
        for meeting_id in meeting_ids:
            await self.close_pipeline(meeting_id)
        await self._event_publisher.close()
        logger.info("AudioBridge closed")

    async def _consume_segments(
        self,
        meeting_id: UUID,
        pipeline: AudioPipeline,
    ) -> None:
        """Background task: periodically trigger transcription of buffered audio.

        Whisper-based STT providers buffer audio and transcribe on each
        ``get_transcript()`` call rather than streaming continuously.
        This task loops every ``_transcription_interval_s`` seconds,
        triggering transcription of whatever audio has accumulated.
        On cancellation, one final pass captures any remaining audio.
        Retries up to 5 times with exponential backoff on unexpected errors.

        On WebSocket connection errors (ConnectionClosedError), creates
        a fresh STT provider, resets the pipeline, and resumes the loop
        without counting toward the retry budget.

        Args:
            meeting_id: The meeting this pipeline belongs to.
            pipeline: The AudioPipeline to consume segments from.
        """
        max_retries = 5
        retry = 0
        delay = 2.0
        while retry < max_retries:
            try:
                while True:
                    logger.debug("Triggering transcription pass for meeting %s", meeting_id)
                    segment_count = 0
                    async for segment in pipeline.get_segments():
                        logger.info(
                            "Segment from meeting %s: %s",
                            meeting_id,
                            segment.text[:80] if segment.text else "",
                        )
                        segment_count += 1
                    if segment_count:
                        logger.info(
                            "Transcription pass yielded %d segments for meeting %s",
                            segment_count,
                            meeting_id,
                        )
                        # Reset retry counter on successful transcription
                        retry = 0
                        delay = 2.0
                    await asyncio.sleep(self._transcription_interval_s)
            except asyncio.CancelledError:
                # Final pass to capture any remaining buffered audio
                with contextlib.suppress(Exception):
                    async for segment in pipeline.get_segments():
                        logger.info(
                            "Final segment from meeting %s: %s",
                            meeting_id,
                            segment.text[:80] if segment.text else "",
                        )
                logger.info(
                    "Segment consumer cancelled for meeting %s",
                    meeting_id,
                )
                return
            except (ConnectionClosedError, ConnectionClosedOK, ConnectionError):
                # STT WebSocket died — create a fresh provider and reset
                logger.warning(
                    "STT connection lost for meeting %s, creating fresh provider",
                    meeting_id,
                )
                try:
                    new_provider = self._recreate_stt_provider(meeting_id)
                    pipeline.reset_provider(new_provider)
                    logger.info(
                        "STT provider reset for meeting %s, resuming segment consumer",
                        meeting_id,
                    )
                    # Don't count connection errors toward retry budget
                    continue
                except Exception:
                    logger.exception(
                        "Failed to recreate STT provider for meeting %s",
                        meeting_id,
                    )
                    retry += 1
                    if retry >= max_retries:
                        logger.error(
                            "Segment consumer exhausted %d retries for meeting %s",
                            max_retries,
                            meeting_id,
                        )
                        return
                    await asyncio.sleep(delay)
                    delay *= 2
            except Exception:
                retry += 1
                logger.exception(
                    "Error consuming segments for meeting %s (retry %d/%d, next delay %.1fs)",
                    meeting_id,
                    retry,
                    max_retries,
                    delay,
                )
                if retry >= max_retries:
                    logger.error(
                        "Segment consumer exhausted %d retries for meeting %s",
                        max_retries,
                        meeting_id,
                    )
                    return
                await asyncio.sleep(delay)
                delay *= 2
