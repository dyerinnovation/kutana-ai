"""Speech-to-text provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from kutana_core.models.transcript import TranscriptSegment


class STTProvider(ABC):
    """Abstract base class for speech-to-text providers.

    Implementations must support streaming audio input and produce
    transcript segments asynchronously.
    """

    @abstractmethod
    async def start_stream(self) -> None:
        """Initialize a new streaming transcription session."""
        ...

    @abstractmethod
    async def send_audio(self, chunk: bytes) -> None:
        """Send an audio chunk to the STT provider.

        Args:
            chunk: Raw audio bytes (PCM16, 16kHz, mono).
        """
        ...

    @abstractmethod
    def get_transcript(self) -> AsyncIterator[TranscriptSegment]:
        """Yield finalized transcript segments as they become available.

        Yields:
            TranscriptSegment instances with speaker attribution.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the streaming session and release resources."""
        ...
