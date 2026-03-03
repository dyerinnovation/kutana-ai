"""Tests for STT provider wiring in the audio service."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from audio_service.main import (
    AudioServiceSettings,
    _create_stt_provider,
    app,
    lifespan,
)
from convene_providers.stt.whisper_remote_stt import WhisperRemoteSTT
from convene_providers.stt.whisper_stt import WhisperSTT

# ---- Settings Tests ----


class TestAudioServiceSettings:
    """Tests for AudioServiceSettings defaults and env var overrides."""

    def test_default_stt_provider(self) -> None:
        """Default STT provider is whisper."""
        settings = AudioServiceSettings()
        assert settings.stt_provider == "whisper"

    def test_default_whisper_model_size(self) -> None:
        """Default whisper model size is small."""
        settings = AudioServiceSettings()
        assert settings.whisper_model_size == "small"

    def test_default_api_key_empty(self) -> None:
        """Default STT API key is empty."""
        settings = AudioServiceSettings()
        assert settings.stt_api_key == ""

    def test_default_whisper_api_url_empty(self) -> None:
        """Default whisper API URL is empty."""
        settings = AudioServiceSettings()
        assert settings.whisper_api_url == ""

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings can be overridden via environment variables."""
        monkeypatch.setenv("STT_PROVIDER", "deepgram")
        monkeypatch.setenv("STT_API_KEY", "test-key-123")
        monkeypatch.setenv("WHISPER_MODEL_SIZE", "large-v2")
        monkeypatch.setenv("WHISPER_API_URL", "http://example.com/v1")

        settings = AudioServiceSettings()
        assert settings.stt_provider == "deepgram"
        assert settings.stt_api_key == "test-key-123"
        assert settings.whisper_model_size == "large-v2"
        assert settings.whisper_api_url == "http://example.com/v1"


# ---- Factory Tests ----


class TestCreateSTTProvider:
    """Tests for _create_stt_provider factory function."""

    def test_whisper_default(self) -> None:
        """Creates WhisperSTT with default settings."""
        settings = AudioServiceSettings()
        mid = uuid4()
        provider = _create_stt_provider(settings, mid)
        assert isinstance(provider, WhisperSTT)
        assert provider._meeting_id == mid
        assert provider._model_size == "small"

    def test_whisper_custom_model(self) -> None:
        """Creates WhisperSTT with custom model size."""
        settings = AudioServiceSettings(whisper_model_size="large-v2")
        mid = uuid4()
        provider = _create_stt_provider(settings, mid)
        assert isinstance(provider, WhisperSTT)
        assert provider._model_size == "large-v2"

    def test_whisper_remote_with_url(self) -> None:
        """Creates WhisperRemoteSTT with API URL."""
        settings = AudioServiceSettings(
            stt_provider="whisper-remote",
            whisper_api_url="http://spark-b0f2.local/convene-stt/v1",
        )
        mid = uuid4()
        provider = _create_stt_provider(settings, mid)
        assert isinstance(provider, WhisperRemoteSTT)
        assert provider._meeting_id == mid
        assert provider._api_url == "http://spark-b0f2.local/convene-stt/v1"

    def test_whisper_remote_missing_url_raises(self) -> None:
        """whisper-remote without URL raises ValueError."""
        settings = AudioServiceSettings(
            stt_provider="whisper-remote",
            whisper_api_url="",
        )
        with pytest.raises(ValueError, match="WHISPER_API_URL"):
            _create_stt_provider(settings, uuid4())

    def test_deepgram_with_key(self) -> None:
        """Creates deepgram provider with API key."""
        settings = AudioServiceSettings(
            stt_provider="deepgram",
            stt_api_key="dg-key-123",
        )
        mid = uuid4()
        provider = _create_stt_provider(settings, mid)
        # Just verify it was created without error
        assert provider is not None

    def test_assemblyai_with_key(self) -> None:
        """Creates assemblyai provider with API key."""
        settings = AudioServiceSettings(
            stt_provider="assemblyai",
            stt_api_key="aai-key-123",
        )
        mid = uuid4()
        provider = _create_stt_provider(settings, mid)
        assert provider is not None

    def test_deepgram_missing_key_raises(self) -> None:
        """deepgram without API key raises ValueError."""
        settings = AudioServiceSettings(
            stt_provider="deepgram",
            stt_api_key="",
        )
        with pytest.raises(ValueError, match="STT_API_KEY"):
            _create_stt_provider(settings, uuid4())

    def test_assemblyai_missing_key_raises(self) -> None:
        """assemblyai without API key raises ValueError."""
        settings = AudioServiceSettings(
            stt_provider="assemblyai",
            stt_api_key="",
        )
        with pytest.raises(ValueError, match="STT_API_KEY"):
            _create_stt_provider(settings, uuid4())

    def test_unknown_provider_raises_key_error(self) -> None:
        """Unknown provider name raises KeyError."""
        settings = AudioServiceSettings(stt_provider="nonexistent")
        with pytest.raises(KeyError, match="nonexistent"):
            _create_stt_provider(settings, uuid4())

    def test_case_insensitive_name(self) -> None:
        """Provider name is case-insensitive."""
        settings = AudioServiceSettings(stt_provider="Whisper")
        provider = _create_stt_provider(settings, uuid4())
        assert isinstance(provider, WhisperSTT)

    def test_each_call_returns_new_instance(self) -> None:
        """Each call returns a distinct instance (no sharing)."""
        settings = AudioServiceSettings()
        p1 = _create_stt_provider(settings, uuid4())
        p2 = _create_stt_provider(settings, uuid4())
        assert p1 is not p2

    def test_meeting_id_forwarded(self) -> None:
        """Meeting ID is passed through to the provider."""
        settings = AudioServiceSettings()
        mid = uuid4()
        provider = _create_stt_provider(settings, mid)
        assert provider._meeting_id == mid


# ---- Lifespan Tests ----


class TestLifespan:
    """Tests for lifespan startup/shutdown with STT validation."""

    @pytest.mark.asyncio
    async def test_validates_config_on_startup(self) -> None:
        """Lifespan creates and closes a test provider on startup."""
        import audio_service.main as main_module

        with patch.object(
            main_module,
            "_create_stt_provider",
            return_value=AsyncMock(),
        ) as mock_factory:
            async with lifespan(app):
                mock_factory.assert_called_once()
                created_provider = mock_factory.return_value
                created_provider.close.assert_called_once()
                assert main_module._settings is not None

            # Settings cleaned up on shutdown
            assert main_module._settings is None

    @pytest.mark.asyncio
    async def test_rejects_bad_provider_name(self) -> None:
        """Lifespan raises when STT provider is invalid."""
        import audio_service.main as main_module

        original_settings = main_module.AudioServiceSettings

        class BadSettings(original_settings):  # type: ignore[misc]
            stt_provider: str = "nonexistent-provider"

        with (
            patch.object(main_module, "AudioServiceSettings", BadSettings),
            pytest.raises(KeyError),
        ):
            async with lifespan(app):
                pass  # pragma: no cover

    @pytest.mark.asyncio
    async def test_cleans_up_on_shutdown(self) -> None:
        """Settings and publisher are cleaned up on shutdown."""
        import audio_service.main as main_module

        with patch.object(
            main_module,
            "_create_stt_provider",
            return_value=AsyncMock(),
        ):
            async with lifespan(app):
                assert main_module._settings is not None
                assert main_module._event_publisher is not None

            assert main_module._settings is None
            assert main_module._event_publisher is None


# ---- Pipeline Factory Tests ----


class TestCreatePipeline:
    """Tests for the create_pipeline factory function."""

    def test_create_pipeline_returns_pipeline(self) -> None:
        """create_pipeline returns an AudioPipeline instance."""
        from audio_service.main import create_pipeline

        settings = AudioServiceSettings()
        mid = uuid4()
        pipeline = create_pipeline(settings, mid)
        assert pipeline is not None
        assert pipeline._meeting_id == mid

    def test_create_pipeline_with_publisher(self) -> None:
        """create_pipeline wires up event publisher."""
        from audio_service.main import create_pipeline

        settings = AudioServiceSettings()
        mock_publisher = AsyncMock()
        pipeline = create_pipeline(settings, uuid4(), event_publisher=mock_publisher)
        assert pipeline._event_publisher is mock_publisher
