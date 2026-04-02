"""Mock providers for unit testing."""

from __future__ import annotations

import fnmatch
from typing import TYPE_CHECKING, Any

from kutana_core.interfaces.llm import LLMProvider
from kutana_core.interfaces.stt import STTProvider
from kutana_core.interfaces.tts import TTSProvider, Voice
from kutana_core.messaging.abc import MessageBus
from kutana_core.messaging.types import Message, Subscription

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from kutana_core.messaging.types import MessageHandler
    from kutana_core.models.task import Task
    from kutana_core.models.transcript import TranscriptSegment


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
        cost_per_char: float = 0.0,
    ) -> None:
        """Initialize the mock TTS provider.

        Args:
            audio_data: Fixed audio bytes returned by all synthesis methods.
                Defaults to 1600 zero bytes.
            cost_per_char: Cost per character reported by ``get_cost_per_char``.
        """
        self._audio_data = audio_data
        self._cost_per_char = cost_per_char

    async def synthesize_stream(
        self,
        text: str,
        voice: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Yield the fixed audio bytes regardless of input text or voice.

        Args:
            text: The text to synthesize (ignored in mock).
            voice: Voice ID (ignored in mock).

        Yields:
            The pre-configured audio bytes.
        """
        yield self._audio_data

    async def synthesize_batch(
        self,
        text: str,
        voice: str | None = None,
    ) -> bytes:
        """Return the fixed audio bytes regardless of input text or voice.

        Args:
            text: The text to synthesize (ignored in mock).
            voice: Voice ID (ignored in mock).

        Returns:
            The pre-configured audio bytes.
        """
        return self._audio_data

    async def list_voices(self) -> list[Voice]:
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

    def get_cost_per_char(self) -> float:
        """Return the configured mock cost per character."""
        return self._cost_per_char

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


class MockMessageBus(MessageBus):
    """Mock MessageBus for unit testing.

    Dispatches published messages to matching subscribed handlers immediately
    in-process without any network I/O. Supports fnmatch topic patterns.

    Attributes:
        published: List of all messages published via :meth:`publish`.
    """

    def __init__(self) -> None:
        """Initialize the mock message bus."""
        self.published: list[Message] = []
        self._subscriptions: dict[str, Subscription] = {}

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        metadata: dict[str, str] | None = None,
        source: str = "",
    ) -> str:
        """Record the message and dispatch to matching subscriptions.

        Args:
            topic: The topic to publish to.
            payload: The message payload.
            metadata: Optional routing metadata.
            source: The publishing service name.

        Returns:
            The message ID.
        """
        message = Message(
            topic=topic,
            payload=payload,
            metadata=metadata or {},
            source=source,
        )
        self.published.append(message)
        for sub in list(self._subscriptions.values()):
            if fnmatch.fnmatch(topic, sub.topic) or sub.topic == topic:
                await sub.handler(message)
        return message.id

    async def subscribe(
        self,
        topic: str,
        handler: MessageHandler,
        group: str | None = None,
    ) -> Subscription:
        """Register a subscription.

        Args:
            topic: The topic or fnmatch pattern to subscribe to.
            handler: Async callback invoked for each matching message.
            group: Consumer group name (recorded but not used for load
                balancing in mock).

        Returns:
            A Subscription representing this active subscription.
        """
        sub = Subscription(topic=topic, handler=handler, group=group)
        self._subscriptions[sub.subscription_id] = sub
        return sub

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Remove a subscription.

        Args:
            subscription: The subscription to remove.
        """
        self._subscriptions.pop(subscription.subscription_id, None)

    async def ack(self, subscription: Subscription, message_id: str) -> None:
        """No-op acknowledgment for mock.

        Args:
            subscription: The subscription that received the message.
            message_id: The message ID to acknowledge (ignored in mock).
        """

    async def close(self) -> None:
        """Clear all active subscriptions."""
        self._subscriptions.clear()
