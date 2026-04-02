"""Local text-to-speech provider using Piper."""

from __future__ import annotations

import asyncio
import io
import logging
from typing import TYPE_CHECKING

from kutana_core.interfaces.tts import TTSProvider, Voice

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
    Voice(
        id="en_US-arctic-medium",
        name="Arctic (US English)",
        language="en-US",
    ),
    Voice(
        id="en_US-libritts_r-medium",
        name="LibriTTS-R (US English)",
        language="en-US",
    ),
]

# Piper is self-hosted with no per-character cost.
_COST_PER_CHAR: float = 0.0


class PiperTTS(TTSProvider):
    """Local TTS provider using Piper. No API key required.

    Synthesizes speech using the Piper TTS engine, which runs
    entirely on-device with ONNX-based neural voice models.

    If the ``piper`` package is not installed, synthesis methods raise
    ``RuntimeError`` with a clear installation message rather than an
    ``ImportError`` at module load time.
    """

    def __init__(self, voice_name: str = "en_US-lessac-medium") -> None:
        """Initialize the Piper TTS provider.

        Args:
            voice_name: Name of the Piper voice model to use
                (e.g., ``en_US-lessac-medium``).
        """
        self._voice_name = voice_name
        self._voice: object | None = None
        self._piper_available: bool = self._check_piper()

    @staticmethod
    def _check_piper() -> bool:
        """Return True if the piper package is importable."""
        try:
            import piper  # noqa: F401
            return True
        except ImportError:
            logger.warning(
                "Piper TTS is not installed. "
                "Install it with: pip install piper-tts. "
                "Synthesis will raise RuntimeError until Piper is available."
            )
            return False

    def _load_voice(self) -> None:
        """Load the Piper voice model synchronously.

        Called inside ``asyncio.to_thread`` to avoid blocking
        the event loop.

        Raises:
            RuntimeError: If piper is not installed.
        """
        if not self._piper_available:
            msg = (
                "Piper TTS is not installed. "
                "Install it with: pip install piper-tts"
            )
            raise RuntimeError(msg)

        from piper.voice import PiperVoice

        self._voice = PiperVoice.load(self._voice_name)
        logger.info("Loaded Piper voice: %s", self._voice_name)

    async def synthesize_stream(
        self, text: str, voice: str | None = None
    ) -> AsyncIterator[bytes]:
        """Synthesize text into audio bytes using Piper.

        Lazily loads the voice model on first call, then runs
        synthesis in a background thread and yields the resulting
        audio bytes as a single chunk (Piper is not a streaming API).

        Note: The ``voice`` parameter is ignored — Piper loads a single
        model at construction time. Pass a different ``voice_name`` to
        ``__init__`` to change voices.

        Args:
            text: The text to synthesize into speech.
            voice: Ignored; Piper voices are set at construction time.

        Yields:
            Raw audio bytes (WAV format) from Piper.

        Raises:
            RuntimeError: If piper is not installed.
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

    async def synthesize_batch(self, text: str, voice: str | None = None) -> bytes:
        """Synthesize text into a single bytes object using Piper.

        Args:
            text: The text to synthesize into speech.
            voice: Ignored; Piper voices are set at construction time.

        Returns:
            Raw audio bytes (WAV format) from Piper.

        Raises:
            RuntimeError: If piper is not installed.
        """
        chunks: list[bytes] = []
        async for chunk in self.synthesize_stream(text, voice):
            chunks.append(chunk)
        return b"".join(chunks)

    async def list_voices(self) -> list[Voice]:
        """Return available Piper voice models.

        Returns a hardcoded list of common Piper voices. In
        production, this could scan a model directory for
        installed voices.

        Returns:
            List of Voice objects supported by Piper.
        """
        return list(_DEFAULT_VOICES)

    def get_cost_per_char(self) -> float:
        """Return Piper's cost per character (zero — self-hosted)."""
        return _COST_PER_CHAR

    @property
    def is_available(self) -> bool:
        """Return True if Piper is installed and ready to synthesize."""
        return self._piper_available

    async def close(self) -> None:
        """Release the loaded voice model."""
        self._voice = None
