"""ElevenLabs text-to-speech provider."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import httpx

from kutana_core.interfaces.tts import TTSProvider, Voice

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"
_VOICES_ENDPOINT = f"{_ELEVENLABS_BASE_URL}/voices"
_AUDIO_CHUNK_SIZE = 4096

# ElevenLabs Turbo v2: ~$0.000030/char (based on published pricing)
_COST_PER_CHAR: float = 0.000030


class ElevenLabsTTS(TTSProvider):
    """ElevenLabs text-to-speech provider.

    Synthesizes speech via ElevenLabs' streaming HTTP API and
    retrieves available voices. Output format: MP3.
    """

    def __init__(
        self,
        api_key: str,
        voice_id: str = "default",
        model_id: str = "eleven_monolingual_v1",
    ) -> None:
        """Initialize the ElevenLabs TTS provider.

        Args:
            api_key: ElevenLabs API key for authentication.
            voice_id: Default voice ID for synthesis.
            model_id: ElevenLabs model to use for synthesis.
        """
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._client = httpx.AsyncClient(
            headers={
                "xi-api-key": self._api_key,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
        )

    def _build_payload(self, text: str) -> dict[str, Any]:
        return {
            "text": text,
            "model_id": self._model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

    async def synthesize_stream(
        self, text: str, voice: str | None = None
    ) -> AsyncIterator[bytes]:
        """Synthesize text into streaming MP3 audio bytes via ElevenLabs.

        Args:
            text: The text to synthesize into speech.
            voice: Voice ID; falls back to the constructor default if None.

        Yields:
            MP3 audio bytes from ElevenLabs.
        """
        effective_voice = voice or self._voice_id
        url = f"{_ELEVENLABS_BASE_URL}/text-to-speech/{effective_voice}/stream"
        payload = self._build_payload(text)

        async with self._client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes(chunk_size=_AUDIO_CHUNK_SIZE):
                yield chunk

    async def synthesize_batch(self, text: str, voice: str | None = None) -> bytes:
        """Synthesize text into a single bytes object via ElevenLabs.

        Args:
            text: The text to synthesize into speech.
            voice: Voice ID; falls back to the constructor default if None.

        Returns:
            Complete MP3 audio bytes.
        """
        chunks: list[bytes] = []
        async for chunk in self.synthesize_stream(text, voice):
            chunks.append(chunk)
        return b"".join(chunks)

    async def list_voices(self) -> list[Voice]:
        """Retrieve available voices from ElevenLabs.

        Returns:
            List of Voice objects with id, name, and language.
        """
        response = await self._client.get(_VOICES_ENDPOINT)
        response.raise_for_status()
        data: dict[str, Any] = response.json()

        voices: list[Voice] = []
        for entry in data.get("voices", []):
            voice_id: str = entry.get("voice_id", "")
            name: str = entry.get("name", "")
            # ElevenLabs returns labels with language info
            labels: dict[str, str] = entry.get("labels", {})
            language: str = labels.get("language", "en-US")
            if voice_id and name:
                voices.append(Voice(id=voice_id, name=name, language=language))

        logger.info("Fetched %d voices from ElevenLabs.", len(voices))
        return voices

    def get_cost_per_char(self) -> float:
        """Return ElevenLabs' approximate cost per character in USD."""
        return _COST_PER_CHAR

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()
