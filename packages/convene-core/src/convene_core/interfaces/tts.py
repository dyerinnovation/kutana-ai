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

    Implementations must support streaming audio synthesis
    and voice listing.
    """

    @abstractmethod
    def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize text into streaming audio chunks.

        Args:
            text: The text to synthesize into speech.

        Yields:
            Audio bytes in the provider's native format.
        """
        ...

    @abstractmethod
    async def get_voices(self) -> list[Voice]:
        """Retrieve the list of available voices.

        Returns:
            List of Voice objects supported by the provider.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release any resources held by the provider."""
        ...
