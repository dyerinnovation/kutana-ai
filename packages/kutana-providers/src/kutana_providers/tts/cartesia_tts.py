"""Cartesia text-to-speech provider."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from kutana_core.interfaces.tts import TTSProvider, Voice

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_CARTESIA_BASE_URL = "https://api.cartesia.ai"
_TTS_BYTES_ENDPOINT = f"{_CARTESIA_BASE_URL}/tts/bytes"
_VOICES_ENDPOINT = f"{_CARTESIA_BASE_URL}/voices"
_AUDIO_CHUNK_SIZE = 4096

# Cartesia sonic-english: ~$0.000015/char (based on published pricing)
_COST_PER_CHAR: float = 0.000015


class CartesiaTTS(TTSProvider):
    """Cartesia text-to-speech provider.

    Synthesizes speech via Cartesia's HTTP streaming API and
    retrieves available voices. Output format: raw PCM16 @ 24 kHz.
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str = "default",
        model_id: str = "sonic-3",
    ) -> None:
        """Initialize the Cartesia TTS provider.

        Args:
            api_key: Cartesia API key for authentication.
            voice_id: Default voice identifier for synthesis.
            model_id: Cartesia model to use for synthesis.
        """
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._client = httpx.AsyncClient(
            headers={
                "X-API-Key": self._api_key,
                "Cartesia-Version": "2024-06-10",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    def _build_payload(self, text: str, voice: str | None) -> dict[str, Any]:
        return {
            "model_id": self._model_id,
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": voice or self._voice_id,
            },
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 24000,
            },
        }

    async def synthesize_stream(
        self, text: str, voice: str | None = None
    ) -> AsyncIterator[bytes]:
        """Synthesize text into streaming PCM16 audio bytes via Cartesia.

        Args:
            text: The text to synthesize into speech.
            voice: Voice ID; falls back to the constructor default if None.

        Yields:
            Raw PCM16 audio bytes at 24 kHz.
        """
        payload = self._build_payload(text, voice)
        async with self._client.stream("POST", _TTS_BYTES_ENDPOINT, json=payload) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=_AUDIO_CHUNK_SIZE):
                yield chunk

    async def synthesize_batch(self, text: str, voice: str | None = None) -> bytes:
        """Synthesize text into a single bytes object via Cartesia.

        Args:
            text: The text to synthesize into speech.
            voice: Voice ID; falls back to the constructor default if None.

        Returns:
            Complete PCM16 audio bytes at 24 kHz.
        """
        chunks: list[bytes] = []
        async for chunk in self.synthesize_stream(text, voice):
            chunks.append(chunk)
        return b"".join(chunks)

    async def list_voices(self) -> list[Voice]:
        """Retrieve available voices from Cartesia.

        Returns:
            List of Voice objects with id, name, and language.
        """
        response = await self._client.get(_VOICES_ENDPOINT)
        response.raise_for_status()
        data: list[dict[str, Any]] = response.json()

        voices: list[Voice] = []
        for entry in data:
            voice_id: str = entry.get("id", "")
            name: str = entry.get("name", "")
            language: str = entry.get("language", "en-US")
            if voice_id and name:
                voices.append(Voice(id=voice_id, name=name, language=language))

        logger.info("Fetched %d voices from Cartesia.", len(voices))
        return voices

    def get_cost_per_char(self) -> float:
        """Return Cartesia's approximate cost per character in USD."""
        return _COST_PER_CHAR

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
