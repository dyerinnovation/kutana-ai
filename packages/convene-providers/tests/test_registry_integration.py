"""Integration tests for the provider registry lifecycle."""

from __future__ import annotations

from uuid import uuid4

import pytest

from convene_core.interfaces.llm import LLMProvider
from convene_core.interfaces.stt import STTProvider
from convene_core.interfaces.tts import TTSProvider
from convene_core.models.task import Task, TaskPriority
from convene_core.models.transcript import TranscriptSegment
from convene_providers.registry import ProviderRegistry, ProviderType, default_registry
from convene_providers.testing import MockLLM, MockSTT, MockTTS

# ---- Helpers ----

MEETING_ID = uuid4()


def _make_segments(n: int = 3) -> list[TranscriptSegment]:
    """Create sample transcript segments for testing."""
    return [
        TranscriptSegment(
            meeting_id=MEETING_ID,
            speaker_id=f"spk_{i}",
            text=f"Test utterance number {i}",
            start_time=float(i * 10),
            end_time=float(i * 10 + 5),
            confidence=0.9,
        )
        for i in range(n)
    ]


def _make_tasks(n: int = 2) -> list[Task]:
    """Create sample tasks for testing."""
    return [
        Task(
            meeting_id=MEETING_ID,
            description=f"Follow up on item {i}",
            priority=TaskPriority.MEDIUM,
        )
        for i in range(n)
    ]


# ---- Full Lifecycle Tests ----


class TestSTTLifecycle:
    """Test the full STT provider lifecycle through the registry."""

    @pytest.mark.asyncio
    async def test_register_create_use(self) -> None:
        """Register MockSTT, create it, use full STT lifecycle."""
        registry = ProviderRegistry()
        registry.register(ProviderType.STT, "mock", MockSTT)

        segments = _make_segments(2)
        provider = registry.create(ProviderType.STT, "mock", segments=segments)
        assert isinstance(provider, STTProvider)

        await provider.start_stream()
        await provider.send_audio(b"\x00" * 160)

        result = [seg async for seg in provider.get_transcript()]
        assert len(result) == 2
        assert result[0].text == "Test utterance number 0"

        await provider.close()

    @pytest.mark.asyncio
    async def test_audio_buffer_accumulates(self) -> None:
        """Audio chunks sent via send_audio are accumulated in the buffer."""
        registry = ProviderRegistry()
        registry.register(ProviderType.STT, "mock", MockSTT)

        provider = registry.create(ProviderType.STT, "mock")
        await provider.start_stream()

        chunk_a = b"\x01" * 80
        chunk_b = b"\x02" * 80
        await provider.send_audio(chunk_a)
        await provider.send_audio(chunk_b)

        assert provider._buffer == chunk_a + chunk_b

        await provider.close()

    @pytest.mark.asyncio
    async def test_multiple_segments_ordered(self) -> None:
        """Segments are yielded in the original insertion order."""
        registry = ProviderRegistry()
        registry.register(ProviderType.STT, "mock", MockSTT)

        segments = _make_segments(5)
        provider = registry.create(ProviderType.STT, "mock", segments=segments)
        await provider.start_stream()

        result = [seg async for seg in provider.get_transcript()]
        assert [s.text for s in result] == [f"Test utterance number {i}" for i in range(5)]

        await provider.close()

    @pytest.mark.asyncio
    async def test_close_resets_state(self) -> None:
        """Closing the provider leaves it in a clean, stopped state."""
        registry = ProviderRegistry()
        registry.register(ProviderType.STT, "mock", MockSTT)

        provider = registry.create(ProviderType.STT, "mock")
        await provider.start_stream()
        await provider.send_audio(b"\xff" * 100)
        await provider.close()

        assert not provider._started
        assert provider._buffer == b""


class TestTTSLifecycle:
    """Test the full TTS provider lifecycle through the registry."""

    @pytest.mark.asyncio
    async def test_register_create_use(self) -> None:
        """Register MockTTS, create it, use synthesize and get_voices."""
        registry = ProviderRegistry()
        registry.register(ProviderType.TTS, "mock", MockTTS)

        audio = b"\xff" * 800
        provider = registry.create(ProviderType.TTS, "mock", audio_data=audio)
        assert isinstance(provider, TTSProvider)

        chunks = [chunk async for chunk in provider.synthesize("hello")]
        assert len(chunks) == 1
        assert chunks[0] == audio

        voices = await provider.get_voices()
        assert len(voices) >= 1
        assert voices[0].id == "mock"

    @pytest.mark.asyncio
    async def test_synthesize_different_texts_return_same_audio(self) -> None:
        """MockTTS ignores input text and returns the same fixed audio."""
        registry = ProviderRegistry()
        registry.register(ProviderType.TTS, "mock", MockTTS)

        audio = b"\xab" * 400
        provider = registry.create(ProviderType.TTS, "mock", audio_data=audio)

        chunks_a = [c async for c in provider.synthesize("hello world")]
        chunks_b = [c async for c in provider.synthesize("goodbye")]

        assert chunks_a == chunks_b

    @pytest.mark.asyncio
    async def test_get_voices_returns_voice_objects(self) -> None:
        """get_voices returns Voice objects with id, name, and language."""
        registry = ProviderRegistry()
        registry.register(ProviderType.TTS, "mock", MockTTS)

        provider = registry.create(ProviderType.TTS, "mock")
        voices = await provider.get_voices()

        assert len(voices) == 1
        assert voices[0].id == "mock"
        assert voices[0].name == "Mock Voice"
        assert voices[0].language == "en-US"


class TestLLMLifecycle:
    """Test the full LLM provider lifecycle through the registry."""

    @pytest.mark.asyncio
    async def test_register_create_use(self) -> None:
        """Register MockLLM with kwargs, create it, use all methods."""
        registry = ProviderRegistry()
        registry.register(ProviderType.LLM, "mock", MockLLM)

        provider = registry.create(
            ProviderType.LLM,
            "mock",
            summary="Custom summary",
            report="Custom report",
        )
        assert isinstance(provider, LLMProvider)

        segments = _make_segments(2)
        tasks = await provider.extract_tasks(segments, "context")
        assert tasks == []

        summary = await provider.summarize(segments)
        assert summary == "Custom summary"

        report = await provider.generate_report([])
        assert report == "Custom report"

    @pytest.mark.asyncio
    async def test_extract_tasks_returns_configured_tasks(self) -> None:
        """MockLLM returns the pre-configured task list from extract_tasks."""
        registry = ProviderRegistry()
        registry.register(ProviderType.LLM, "mock", MockLLM)

        tasks = _make_tasks(3)
        provider = registry.create(ProviderType.LLM, "mock", tasks=tasks)

        segments = _make_segments(2)
        result = await provider.extract_tasks(segments, "meeting context")

        assert len(result) == 3
        assert all(isinstance(t, Task) for t in result)
        assert result[0].description == "Follow up on item 0"

    @pytest.mark.asyncio
    async def test_generate_report_with_tasks(self) -> None:
        """generate_report returns configured report regardless of task input."""
        registry = ProviderRegistry()
        registry.register(ProviderType.LLM, "mock", MockLLM)

        provider = registry.create(ProviderType.LLM, "mock", report="Sprint summary")
        tasks = _make_tasks(4)
        result = await provider.generate_report(tasks)

        assert result == "Sprint summary"

    @pytest.mark.asyncio
    async def test_defaults_when_no_kwargs(self) -> None:
        """MockLLM has sensible defaults when created with no extra kwargs."""
        registry = ProviderRegistry()
        registry.register(ProviderType.LLM, "mock", MockLLM)

        provider = registry.create(ProviderType.LLM, "mock")
        assert await provider.extract_tasks([], "") == []
        assert await provider.summarize([]) == "Mock summary"
        assert await provider.generate_report([]) == "Mock report"


# ---- Registry Behaviour Tests ----


class TestRegistryBehaviour:
    """Tests for registry isolation, error handling, and kwargs pass-through."""

    def test_isolation_between_instances(self) -> None:
        """Two ProviderRegistry instances do not share state."""
        reg_a = ProviderRegistry()
        reg_b = ProviderRegistry()

        reg_a.register(ProviderType.STT, "mock", MockSTT)

        assert reg_a.is_registered(ProviderType.STT, "mock")
        assert not reg_b.is_registered(ProviderType.STT, "mock")

    def test_kwargs_pass_through(self) -> None:
        """Constructor kwargs are forwarded to the provider class."""
        registry = ProviderRegistry()
        registry.register(ProviderType.STT, "mock", MockSTT)

        segments = _make_segments(5)
        provider = registry.create(ProviderType.STT, "mock", segments=segments)
        assert len(provider._segments) == 5

    def test_duplicate_registration_raises(self) -> None:
        """Registering the same type/name twice raises ValueError."""
        registry = ProviderRegistry()
        registry.register(ProviderType.STT, "mock", MockSTT)

        with pytest.raises(ValueError, match="already registered"):
            registry.register(ProviderType.STT, "mock", MockSTT)

    def test_unregistered_create_raises(self) -> None:
        """Creating an unregistered provider raises KeyError."""
        registry = ProviderRegistry()

        with pytest.raises(KeyError, match="No provider registered"):
            registry.create(ProviderType.STT, "nonexistent")

    def test_same_name_different_type_allowed(self) -> None:
        """Registering the same name under different types is permitted."""
        registry = ProviderRegistry()
        registry.register(ProviderType.STT, "mock", MockSTT)
        registry.register(ProviderType.TTS, "mock", MockTTS)
        registry.register(ProviderType.LLM, "mock", MockLLM)

        assert registry.is_registered(ProviderType.STT, "mock")
        assert registry.is_registered(ProviderType.TTS, "mock")
        assert registry.is_registered(ProviderType.LLM, "mock")

    def test_unregistered_is_registered_returns_false(self) -> None:
        """is_registered returns False for names that were never registered."""
        registry = ProviderRegistry()
        assert not registry.is_registered(ProviderType.STT, "phantom")
        assert not registry.is_registered(ProviderType.TTS, "phantom")
        assert not registry.is_registered(ProviderType.LLM, "phantom")

    def test_error_does_not_corrupt_registry(self) -> None:
        """A failed create leaves the registry intact for subsequent calls."""
        registry = ProviderRegistry()
        registry.register(ProviderType.STT, "mock", MockSTT)

        with pytest.raises(KeyError):
            registry.create(ProviderType.STT, "missing")

        # Registry still works after the error
        provider = registry.create(ProviderType.STT, "mock")
        assert isinstance(provider, STTProvider)

    def test_list_providers_empty_registry(self) -> None:
        """list_providers returns an empty list for a new registry."""
        registry = ProviderRegistry()
        assert registry.list_providers(ProviderType.STT) == []
        assert registry.list_providers(ProviderType.TTS) == []
        assert registry.list_providers(ProviderType.LLM) == []

    def test_list_providers_sorted(self) -> None:
        """list_providers returns provider names in alphabetical order."""
        registry = ProviderRegistry()
        registry.register(ProviderType.LLM, "zebra", MockLLM)
        registry.register(ProviderType.LLM, "alpha", MockLLM)
        registry.register(ProviderType.LLM, "middle", MockLLM)

        result = registry.list_providers(ProviderType.LLM)
        assert result == ["alpha", "middle", "zebra"]

    def test_list_providers_type_isolation(self) -> None:
        """list_providers for one type does not include providers of other types."""
        registry = ProviderRegistry()
        registry.register(ProviderType.STT, "stt-only", MockSTT)
        registry.register(ProviderType.TTS, "tts-only", MockTTS)

        assert registry.list_providers(ProviderType.STT) == ["stt-only"]
        assert registry.list_providers(ProviderType.TTS) == ["tts-only"]
        assert registry.list_providers(ProviderType.LLM) == []


# ---- Default Registry Tests ----


class TestDefaultRegistry:
    """Tests for the pre-built default_registry singleton."""

    def test_default_registry_smoke_stt(self) -> None:
        """Default registry can create a WhisperSTT provider."""
        from convene_providers.stt.whisper_stt import WhisperSTT

        provider = default_registry.create(
            ProviderType.STT, "whisper", model_size="tiny"
        )
        assert isinstance(provider, WhisperSTT)
        assert isinstance(provider, STTProvider)

    def test_default_registry_smoke_tts(self) -> None:
        """Default registry can create a PiperTTS provider."""
        from convene_providers.tts.piper_tts import PiperTTS

        provider = default_registry.create(ProviderType.TTS, "piper")
        assert isinstance(provider, PiperTTS)
        assert isinstance(provider, TTSProvider)

    def test_default_registry_smoke_llm_ollama(self) -> None:
        """Default registry can create an OllamaLLM provider."""
        from convene_providers.llm.ollama_llm import OllamaLLM

        provider = default_registry.create(ProviderType.LLM, "ollama")
        assert isinstance(provider, OllamaLLM)
        assert isinstance(provider, LLMProvider)

    def test_default_registry_smoke_llm_groq(self) -> None:
        """Default registry can create a GroqLLM provider."""
        from convene_providers.llm.groq_llm import GroqLLM

        provider = default_registry.create(
            ProviderType.LLM, "groq", api_key="test-key"
        )
        assert isinstance(provider, GroqLLM)
        assert isinstance(provider, LLMProvider)

    def test_all_stt_providers_registered(self) -> None:
        """Default registry has all expected STT providers."""
        stt_providers = default_registry.list_providers(ProviderType.STT)
        assert "assemblyai" in stt_providers
        assert "deepgram" in stt_providers
        assert "whisper" in stt_providers

    def test_all_tts_providers_registered(self) -> None:
        """Default registry has all expected TTS providers."""
        tts_providers = default_registry.list_providers(ProviderType.TTS)
        assert "cartesia" in tts_providers
        assert "elevenlabs" in tts_providers
        assert "piper" in tts_providers

    def test_all_llm_providers_registered(self) -> None:
        """Default registry has all expected LLM providers."""
        llm_providers = default_registry.list_providers(ProviderType.LLM)
        assert "anthropic" in llm_providers
        assert "ollama" in llm_providers
        assert "groq" in llm_providers

    def test_total_provider_counts(self) -> None:
        """Default registry has exactly 3 providers per category."""
        assert len(default_registry.list_providers(ProviderType.STT)) == 3
        assert len(default_registry.list_providers(ProviderType.TTS)) == 3
        assert len(default_registry.list_providers(ProviderType.LLM)) == 3

    def test_default_registry_providers_are_sorted(self) -> None:
        """Default registry list_providers output is alphabetically sorted."""
        stt = default_registry.list_providers(ProviderType.STT)
        tts = default_registry.list_providers(ProviderType.TTS)
        llm = default_registry.list_providers(ProviderType.LLM)

        assert stt == sorted(stt)
        assert tts == sorted(tts)
        assert llm == sorted(llm)

    def test_default_registry_is_not_corrupted_by_creation(self) -> None:
        """Creating providers from the default registry does not modify it."""
        count_before = len(default_registry.list_providers(ProviderType.STT))
        default_registry.create(ProviderType.STT, "whisper", model_size="tiny")
        count_after = len(default_registry.list_providers(ProviderType.STT))
        assert count_before == count_after
