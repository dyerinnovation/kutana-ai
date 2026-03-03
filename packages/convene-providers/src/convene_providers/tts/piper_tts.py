"""Local text-to-speech provider using Piper."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING

from convene_core.interfaces.tts import TTSProvider, Voice

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

# Common Piper voices available for download.
_DEFAULT_VOICES: list[Voice] = [
    Voice(
        id="en_US-lessac-medium",
        name="Lessac (US English)",
        language="en-US",
    ),
    Voice(
        id="en_US-amy-medium",
        name="Amy (US English)",
        language="en-US",
    ),
    Voice(
        id="en_GB-alan-medium",
        name="Alan (British English)",
        language="en-GB",
    ),
]


class PiperTTS(TTSProvider):
    """Local TTS provider using Piper. No API key required.

    Synthesizes speech using the Piper TTS engine, which runs
    entirely on-device with ONNX-based neural voice models.
    """

    def __init__(self, voice_name: str = "en_US-lessac-medium") -> None:
        """Initialize the Piper TTS provider.

        Args:
            voice_name: Name of the Piper voice model to use
                (e.g., ``en_US-lessac-medium``).
        """
        self._voice_name = voice_name
        self._voice: object | None = None

    def _load_voice(self) -> None:
        """Load the Piper voice model synchronously.

        Called inside ``asyncio.to_thread`` to avoid blocking
        the event loop.
        """
        from piper.voice import PiperVoice

        self._voice = PiperVoice.load(self._voice_name)
        logger.info("Loaded Piper voice: %s", self._voice_name)

    async def synthesize(self, text: str) -> AsyncIterator[bytes]:
        """Synthesize text into audio bytes using Piper.

        Lazily loads the voice model on first call, then runs
        synthesis in a background thread and yields the resulting
        audio bytes.

        Args:
            text: The text to synthesize into speech.

        Yields:
            Raw audio bytes (WAV format) from Piper.
        """
        if self._voice is None:
            await asyncio.to_thread(self._load_voice)

        buf = io.BytesIO()

        def _synthesize() -> bytes:
            self._voice.synthesize(  # type: ignore[union-attr]  # _voice is set before use
                text,
                buf,
            )
            return buf.getvalue()

        audio_data = await asyncio.to_thread(_synthesize)
        yield audio_data

    async def get_voices(self) -> list[Voice]:
        """Return available Piper voice models.

        Returns a hardcoded list of common Piper voices. In
        production, this could scan a model directory for
        installed voices.

        Returns:
            List of Voice objects supported by Piper.
        """
        return list(_DEFAULT_VOICES)

    async def close(self) -> None:
        """Release the loaded voice model."""
        self._voice = None
