"""Mock providers for unit testing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from convene_core.interfaces.llm import LLMProvider
from convene_core.interfaces.stt import STTProvider
from convene_core.interfaces.tts import TTSProvider, Voice

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from convene_core.models.task import Task
    from convene_core.models.transcript import TranscriptSegment


class MockSTT(STTProvider):
    """Mock STT that returns pre-configured segments.

    Useful for unit tests that need deterministic transcript
    output without requiring an actual STT backend.
    """

    def __init__(
        self,
        segments: list[TranscriptSegment] | None = None,
    ) -> None:
        """Initialize the mock STT provider.

        Args:
            segments: Pre-configured transcript segments to
                return from ``get_transcript``. Defaults to
                an empty list.
        """
        self._segments = segments or []
        self._buffer = b""
        self._started = False

    async def start_stream(self) -> None:
        """Mark the stream as started and reset the buffer."""
        self._started = True
        self._buffer = b""

    async def send_audio(self, chunk: bytes) -> None:
        """Append audio bytes to the internal buffer.

        Args:
            chunk: Raw audio bytes (ignored in mock but
                stored for assertion purposes).
        """
        self._buffer += chunk

    async def get_transcript(
        self,
    ) -> AsyncIterator[TranscriptSegment]:
        """Yield the pre-configured transcript segments.

        Yields:
            TranscriptSegment instances provided at init.
        """
        for segment in self._segments:
            yield segment

    async def close(self) -> None:
        """Mark the stream as stopped."""
        self._started = False


class MockTTS(TTSProvider):
    """Mock TTS that returns fixed audio bytes.

    Useful for unit tests that need deterministic audio output
    without requiring an actual TTS backend.
    """

    def __init__(
        self,
        audio_data: bytes = b"\x00" * 1600,
    ) -> None:
        """Initialize the mock TTS provider.

        Args:
            audio_data: Fixed audio bytes to return from
                ``synthesize``. Defaults to 1600 zero bytes.
        """
        self._audio_data = audio_data

    async def synthesize(
        self,
        text: str,
    ) -> AsyncIterator[bytes]:
        """Yield the fixed audio bytes regardless of input text.

        Args:
            text: The text to synthesize (ignored in mock).

        Yields:
            The pre-configured audio bytes.
        """
        yield self._audio_data

    async def get_voices(self) -> list[Voice]:
        """Return a single mock voice.

        Returns:
            List containing one mock Voice object.
        """
        return [
            Voice(
                id="mock",
                name="Mock Voice",
                language="en-US",
            ),
        ]

    async def close(self) -> None:
        """No resources to release in mock provider."""


class MockLLM(LLMProvider):
    """Mock LLM that returns pre-configured responses.

    Useful for unit tests that need deterministic LLM output
    without requiring an actual LLM backend or API key.
    """

    def __init__(
        self,
        tasks: list[Task] | None = None,
        summary: str = "Mock summary",
        report: str = "Mock report",
    ) -> None:
        """Initialize the mock LLM provider.

        Args:
            tasks: Pre-configured tasks to return from
                ``extract_tasks``. Defaults to an empty list.
            summary: Fixed summary string to return from
                ``summarize``.
            report: Fixed report string to return from
                ``generate_report``.
        """
        self._tasks = tasks or []
        self._summary = summary
        self._report = report

    async def extract_tasks(
        self,
        segments: list[TranscriptSegment],
        context: str,
    ) -> list[Task]:
        """Return the pre-configured list of tasks.

        Args:
            segments: List of transcript segments (ignored).
            context: Additional context string (ignored).

        Returns:
            The pre-configured list of Task objects.
        """
        return list(self._tasks)

    async def summarize(
        self,
        segments: list[TranscriptSegment],
    ) -> str:
        """Return the pre-configured summary string.

        Args:
            segments: List of transcript segments (ignored).

        Returns:
            The fixed summary string.
        """
        return self._summary

    async def generate_report(
        self,
        tasks: list[Task],
    ) -> str:
        """Return the pre-configured report string.

        Args:
            tasks: List of tasks (ignored).

        Returns:
            The fixed report string.
        """
        return self._report
