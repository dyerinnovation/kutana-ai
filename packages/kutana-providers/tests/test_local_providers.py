"""Tests for local/free-tier providers and mock providers."""

from __future__ import annotations

from uuid import uuid4

import pytest

from kutana_core.interfaces.llm import LLMProvider
from kutana_core.interfaces.stt import STTProvider
from kutana_core.interfaces.tts import TTSProvider, Voice
from kutana_core.models.task import Task, TaskPriority
from kutana_core.models.transcript import TranscriptSegment
from kutana_providers.llm.groq_llm import GroqLLM
from kutana_providers.llm.ollama_llm import OllamaLLM
from kutana_providers.registry import ProviderType, default_registry
from kutana_providers.stt.whisper_stt import WhisperSTT
from kutana_providers.testing import MockLLM, MockSTT, MockTTS
from kutana_providers.tts.piper_tts import PiperTTS

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
            description=f"Task {i}",
            priority=TaskPriority.MEDIUM,
        )
        for i in range(n)
    ]


# ---- WhisperSTT Tests ----


class TestWhisperSTT:
    """Tests for the WhisperSTT provider."""

    def test_is_stt_provider(self) -> None:
        """WhisperSTT implements STTProvider ABC."""
        provider = WhisperSTT(model_size="tiny")
        assert isinstance(provider, STTProvider)

    def test_default_model_size(self) -> None:
        """WhisperSTT defaults to 'small' model."""
        provider = WhisperSTT()
        assert provider._model_size == "small"

    def test_custom_model_size(self) -> None:
        """WhisperSTT accepts custom model size."""
        provider = WhisperSTT(model_size="medium")
        assert provider._model_size == "medium"

    def test_custom_meeting_id(self) -> None:
        """WhisperSTT accepts custom meeting ID."""
        mid = uuid4()
        provider = WhisperSTT(meeting_id=mid)
        assert provider._meeting_id == mid

    @pytest.mark.asyncio
    async def test_send_audio_before_start_raises(self) -> None:
        """Sending audio before start_stream raises RuntimeError."""
        provider = WhisperSTT(model_size="tiny")
        with pytest.raises(RuntimeError, match="Stream not started"):
            await provider.send_audio(b"\x00" * 100)

    @pytest.mark.asyncio
    async def test_close_resets_state(self) -> None:
        """Closing the provider resets running state and buffer."""
        provider = WhisperSTT(model_size="tiny")
        provider._running = True
        provider._buffer = b"\x00" * 100
        await provider.close()
        assert not provider._running
        assert provider._buffer == b""


# ---- PiperTTS Tests ----


class TestPiperTTS:
    """Tests for the PiperTTS provider."""

    def test_is_tts_provider(self) -> None:
        """PiperTTS implements TTSProvider ABC."""
        provider = PiperTTS()
        assert isinstance(provider, TTSProvider)

    def test_default_voice(self) -> None:
        """PiperTTS defaults to 'en_US-lessac-medium' voice."""
        provider = PiperTTS()
        assert provider._voice_name == "en_US-lessac-medium"

    def test_custom_voice(self) -> None:
        """PiperTTS accepts custom voice name."""
        provider = PiperTTS(voice_name="en_GB-alan-medium")
        assert provider._voice_name == "en_GB-alan-medium"

    def test_is_available_without_piper(self) -> None:
        """PiperTTS.is_available reflects whether piper is installed."""
        provider = PiperTTS()
        # Either True or False is valid; key is that the attribute exists
        assert isinstance(provider.is_available, bool)

    def test_zero_cost_per_char(self) -> None:
        """PiperTTS reports zero cost per char (self-hosted)."""
        provider = PiperTTS()
        assert provider.get_cost_per_char() == 0.0

    @pytest.mark.asyncio
    async def test_list_voices_returns_list(self) -> None:
        """list_voices returns a list of Voice objects."""
        provider = PiperTTS()
        voices = await provider.list_voices()
        assert len(voices) >= 1
        assert all(isinstance(v, Voice) for v in voices)

    @pytest.mark.asyncio
    async def test_list_voices_includes_default(self) -> None:
        """list_voices includes the default lessac voice."""
        provider = PiperTTS()
        voices = await provider.list_voices()
        voice_ids = [v.id for v in voices]
        assert "en_US-lessac-medium" in voice_ids


# ---- OllamaLLM Tests ----


class TestOllamaLLM:
    """Tests for the OllamaLLM provider."""

    def test_is_llm_provider(self) -> None:
        """OllamaLLM implements LLMProvider ABC."""
        provider = OllamaLLM()
        assert isinstance(provider, LLMProvider)

    def test_default_config(self) -> None:
        """OllamaLLM uses default base_url and model."""
        provider = OllamaLLM()
        assert provider._base_url == "http://localhost:11434"
        assert provider._model == "mistral"

    def test_custom_config(self) -> None:
        """OllamaLLM accepts custom base_url and model."""
        provider = OllamaLLM(
            base_url="http://192.168.1.100:11434",
            model="llama3",
        )
        assert provider._base_url == "http://192.168.1.100:11434"
        assert provider._model == "llama3"

    def test_trailing_slash_stripped(self) -> None:
        """OllamaLLM strips trailing slash from base_url."""
        provider = OllamaLLM(base_url="http://localhost:11434/")
        assert provider._base_url == "http://localhost:11434"

    @pytest.mark.asyncio
    async def test_extract_tasks_empty_segments(self) -> None:
        """extract_tasks returns empty list for empty input."""
        provider = OllamaLLM()
        result = await provider.extract_tasks([], "test context")
        assert result == []

    @pytest.mark.asyncio
    async def test_summarize_empty_segments(self) -> None:
        """summarize returns empty string for empty input."""
        provider = OllamaLLM()
        result = await provider.summarize([])
        assert result == ""

    @pytest.mark.asyncio
    async def test_generate_report_empty_tasks(self) -> None:
        """generate_report returns message for empty task list."""
        provider = OllamaLLM()
        result = await provider.generate_report([])
        assert result == "No tasks to report."

    @pytest.mark.asyncio
    async def test_format_segments(self) -> None:
        """_format_segments produces readable transcript text."""
        provider = OllamaLLM()
        segments = _make_segments(2)
        formatted = provider._format_segments(segments)
        assert "spk_0" in formatted
        assert "spk_1" in formatted
        assert "Test utterance" in formatted

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """close() does not raise."""
        provider = OllamaLLM()
        await provider.close()


# ---- GroqLLM Tests ----


class TestGroqLLM:
    """Tests for the GroqLLM provider."""

    def test_is_llm_provider(self) -> None:
        """GroqLLM implements LLMProvider ABC."""
        provider = GroqLLM(api_key="test-key")
        assert isinstance(provider, LLMProvider)

    def test_default_model(self) -> None:
        """GroqLLM defaults to llama-3.1-8b-instant."""
        provider = GroqLLM(api_key="test-key")
        assert provider._model == "llama-3.1-8b-instant"

    def test_custom_model(self) -> None:
        """GroqLLM accepts custom model name."""
        provider = GroqLLM(api_key="test-key", model="mixtral-8x7b-32768")
        assert provider._model == "mixtral-8x7b-32768"

    @pytest.mark.asyncio
    async def test_extract_tasks_empty_segments(self) -> None:
        """extract_tasks returns empty list for empty input."""
        provider = GroqLLM(api_key="test-key")
        result = await provider.extract_tasks([], "test context")
        assert result == []

    @pytest.mark.asyncio
    async def test_summarize_empty_segments(self) -> None:
        """summarize returns empty string for empty input."""
        provider = GroqLLM(api_key="test-key")
        result = await provider.summarize([])
        assert result == ""

    @pytest.mark.asyncio
    async def test_generate_report_empty_tasks(self) -> None:
        """generate_report returns message for empty task list."""
        provider = GroqLLM(api_key="test-key")
        result = await provider.generate_report([])
        assert result == "No tasks to report."

    @pytest.mark.asyncio
    async def test_format_segments(self) -> None:
        """_format_segments produces readable transcript text."""
        provider = GroqLLM(api_key="test-key")
        segments = _make_segments(2)
        formatted = provider._format_segments(segments)
        assert "spk_0" in formatted
        assert "Test utterance" in formatted


# ---- Mock Provider Tests ----


class TestMockSTT:
    """Tests for the MockSTT provider."""

    def test_is_stt_provider(self) -> None:
        """MockSTT implements STTProvider ABC."""
        mock = MockSTT()
        assert isinstance(mock, STTProvider)

    @pytest.mark.asyncio
    async def test_start_and_send(self) -> None:
        """MockSTT accepts start_stream and send_audio calls."""
        mock = MockSTT()
        await mock.start_stream()
        await mock.send_audio(b"\x00" * 100)
        assert mock._buffer == b"\x00" * 100

    @pytest.mark.asyncio
    async def test_get_transcript_returns_segments(self) -> None:
        """MockSTT yields pre-configured segments."""
        segments = _make_segments(2)
        mock = MockSTT(segments=segments)
        await mock.start_stream()
        result = [seg async for seg in mock.get_transcript()]
        assert len(result) == 2
        assert result[0].text == "Test utterance number 0"

    @pytest.mark.asyncio
    async def test_empty_segments(self) -> None:
        """MockSTT with no segments yields nothing."""
        mock = MockSTT()
        await mock.start_stream()
        result = [seg async for seg in mock.get_transcript()]
        assert result == []

    @pytest.mark.asyncio
    async def test_close(self) -> None:
        """close() marks stream as stopped."""
        mock = MockSTT()
        await mock.start_stream()
        assert mock._started
        await mock.close()
        assert not mock._started


class TestMockTTS:
    """Tests for the MockTTS provider."""

    def test_is_tts_provider(self) -> None:
        """MockTTS implements TTSProvider ABC."""
        mock = MockTTS()
        assert isinstance(mock, TTSProvider)

    @pytest.mark.asyncio
    async def test_synthesize_stream_returns_audio(self) -> None:
        """MockTTS yields pre-configured audio bytes from synthesize_stream."""
        audio = b"\xff" * 800
        mock = MockTTS(audio_data=audio)
        chunks = [chunk async for chunk in mock.synthesize_stream("hello")]
        assert len(chunks) == 1
        assert chunks[0] == audio

    @pytest.mark.asyncio
    async def test_synthesize_batch_returns_audio(self) -> None:
        """MockTTS returns pre-configured audio bytes from synthesize_batch."""
        audio = b"\xff" * 800
        mock = MockTTS(audio_data=audio)
        result = await mock.synthesize_batch("hello")
        assert result == audio

    @pytest.mark.asyncio
    async def test_list_voices_returns_mock(self) -> None:
        """MockTTS returns a single mock voice from list_voices."""
        mock = MockTTS()
        voices = await mock.list_voices()
        assert len(voices) == 1
        assert voices[0].id == "mock"

    def test_get_cost_per_char_default_zero(self) -> None:
        """MockTTS default cost per char is zero."""
        mock = MockTTS()
        assert mock.get_cost_per_char() == 0.0

    def test_get_cost_per_char_custom(self) -> None:
        """MockTTS respects custom cost_per_char."""
        mock = MockTTS(cost_per_char=0.00001)
        assert mock.get_cost_per_char() == 0.00001


class TestMockLLM:
    """Tests for the MockLLM provider."""

    def test_is_llm_provider(self) -> None:
        """MockLLM implements LLMProvider ABC."""
        mock = MockLLM()
        assert isinstance(mock, LLMProvider)

    @pytest.mark.asyncio
    async def test_extract_tasks_returns_configured(self) -> None:
        """MockLLM returns pre-configured tasks."""
        tasks = _make_tasks(3)
        mock = MockLLM(tasks=tasks)
        result = await mock.extract_tasks(_make_segments(), "ctx")
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_summarize_returns_configured(self) -> None:
        """MockLLM returns pre-configured summary."""
        mock = MockLLM(summary="Custom summary")
        result = await mock.summarize(_make_segments())
        assert result == "Custom summary"

    @pytest.mark.asyncio
    async def test_generate_report_returns_configured(self) -> None:
        """MockLLM returns pre-configured report."""
        mock = MockLLM(report="Custom report")
        result = await mock.generate_report(_make_tasks())
        assert result == "Custom report"

    @pytest.mark.asyncio
    async def test_defaults(self) -> None:
        """MockLLM has sensible defaults."""
        mock = MockLLM()
        tasks = await mock.extract_tasks(_make_segments(), "")
        assert tasks == []
        summary = await mock.summarize(_make_segments())
        assert summary == "Mock summary"
        report = await mock.generate_report(_make_tasks())
        assert report == "Mock report"


# ---- Registry Tests ----


class TestRegistryNewProviders:
    """Tests that new providers are registered in the default registry."""

    def test_whisper_registered(self) -> None:
        """WhisperSTT is registered as 'whisper' STT provider."""
        assert default_registry.is_registered(ProviderType.STT, "whisper")

    def test_piper_registered(self) -> None:
        """PiperTTS is registered as 'piper' TTS provider."""
        assert default_registry.is_registered(ProviderType.TTS, "piper")

    def test_ollama_registered(self) -> None:
        """OllamaLLM is registered as 'ollama' LLM provider."""
        assert default_registry.is_registered(ProviderType.LLM, "ollama")

    def test_groq_registered(self) -> None:
        """GroqLLM is registered as 'groq' LLM provider."""
        assert default_registry.is_registered(ProviderType.LLM, "groq")

    def test_stt_list_includes_whisper(self) -> None:
        """Registry STT list includes 'whisper'."""
        providers = default_registry.list_providers(ProviderType.STT)
        assert "whisper" in providers

    def test_tts_list_includes_piper(self) -> None:
        """Registry TTS list includes 'piper'."""
        providers = default_registry.list_providers(ProviderType.TTS)
        assert "piper" in providers

    def test_llm_list_includes_ollama_and_groq(self) -> None:
        """Registry LLM list includes 'ollama' and 'groq'."""
        providers = default_registry.list_providers(ProviderType.LLM)
        assert "ollama" in providers
        assert "groq" in providers

    def test_total_provider_counts(self) -> None:
        """Registry has correct total providers per type."""
        assert len(default_registry.list_providers(ProviderType.STT)) == 4
        assert len(default_registry.list_providers(ProviderType.TTS)) == 3
        assert len(default_registry.list_providers(ProviderType.LLM)) == 3
