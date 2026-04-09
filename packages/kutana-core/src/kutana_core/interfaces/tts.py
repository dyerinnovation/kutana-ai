"""Text-to-speech provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


class Voice(BaseModel):
    """Represents an available TTS voice.

    Attributes:
        id: Unique voice identifier from the TTS provider.
        name: Human-readable voice name.
        language: Language code (e.g., "en-US").
    """

    id: str
    name: str
    language: str


class TTSProvider(ABC):
    """Abstract base class for text-to-speech providers.

    Implementations must support streaming and batch audio synthesis,
    voice listing, and per-character cost reporting.
    """

    @abstractmethod
    def synthesize_stream(self, text: str, voice: str | None = None) -> AsyncIterator[bytes]:
        """Synthesize text into streaming audio chunks.

        Args:
            text: The text to synthesize into speech.
            voice: Voice ID to use; falls back to the provider's default if None.

        Yields:
            Audio bytes in the provider's native format.
        """
        ...

    @abstractmethod
    async def synthesize_batch(self, text: str, voice: str | None = None) -> bytes:
        """Synthesize text into a single audio bytes object.

        Accumulates all chunks from the streaming synthesis into one
        contiguous buffer. Suitable for short phrases and cache fills.

        Args:
            text: The text to synthesize into speech.
            voice: Voice ID to use; falls back to the provider's default if None.

        Returns:
            Complete audio bytes in the provider's native format.
        """
        ...

    @abstractmethod
    async def list_voices(self) -> list[Voice]:
        """Retrieve the list of available voices.

        Returns:
            List of Voice objects supported by the provider.
        """
        ...

    @abstractmethod
    def get_cost_per_char(self) -> float:
        """Return the approximate cost per character in USD.

        Used by the TTS pipeline for tier-based provider selection
        and usage cost estimation.

        Returns:
            Cost per character as a float (e.g., 0.000024 for $0.024/1K chars).
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by the provider."""
        ...
