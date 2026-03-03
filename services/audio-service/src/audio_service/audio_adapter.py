"""Abstract base class for audio transport adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from audio_service.audio_pipeline import AudioPipeline


class AudioAdapter(ABC):
    """Base class for audio transport adapters.

    An adapter receives audio from a specific transport (WebSocket,
    LiveKit track, etc.) and forwards PCM16 16 kHz mono bytes to
    an AudioPipeline for STT processing.
    """

    def __init__(self, pipeline: AudioPipeline) -> None:
        """Initialise the adapter with an audio pipeline.

        Args:
            pipeline: The AudioPipeline to forward audio to.
        """
        self._pipeline = pipeline

    @abstractmethod
    async def start(self) -> None:
        """Start receiving audio from the transport."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop receiving audio and clean up resources."""
