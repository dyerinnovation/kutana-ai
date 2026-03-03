"""FastAPI application entry point for the Convene AI audio service."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from fastapi import FastAPI
from pydantic import BaseModel
from pydantic_settings import BaseSettings

from audio_service.audio_pipeline import AudioPipeline
from audio_service.event_publisher import EventPublisher
from convene_providers.registry import ProviderType, default_registry

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class AudioServiceSettings(BaseSettings):
    """Configuration for the audio service.

    Attributes:
        redis_url: Redis connection URL for event publishing.
        stt_provider: STT provider name (whisper, whisper-remote,
            deepgram, assemblyai).
        stt_api_key: API key for deepgram/assemblyai providers.
        whisper_model_size: Whisper model size for local whisper.
        whisper_api_url: Remote Whisper API URL for whisper-remote.
    """

    redis_url: str = "redis://localhost:6379/0"
    stt_provider: str = "whisper"
    stt_api_key: str = ""
    whisper_model_size: str = "small"
    whisper_api_url: str = ""
    audio_service_public_url: str = ""

    model_config = {"env_prefix": "", "case_sensitive": False}


# ---------------------------------------------------------------------------
# STT factory
# ---------------------------------------------------------------------------


def _create_stt_provider(
    settings: AudioServiceSettings,
    meeting_id: UUID,
) -> object:
    """Create an STT provider instance from settings.

    Args:
        settings: Audio service settings with STT configuration.
        meeting_id: Meeting ID to pass to the provider.

    Returns:
        An STT provider instance.

    Raises:
        KeyError: If the provider name is not registered.
        ValueError: If required config is missing for the provider.
    """
    name = settings.stt_provider.lower()
    kwargs: dict[str, object] = {"meeting_id": meeting_id}

    if name == "whisper":
        kwargs["model_size"] = settings.whisper_model_size
    elif name == "whisper-remote":
        if not settings.whisper_api_url:
            msg = "WHISPER_API_URL is required for whisper-remote provider"
            raise ValueError(msg)
        kwargs["api_url"] = settings.whisper_api_url
    elif name in ("deepgram", "assemblyai"):
        if not settings.stt_api_key:
            msg = f"STT_API_KEY is required for {name} provider"
            raise ValueError(msg)
        kwargs["api_key"] = settings.stt_api_key
    else:
        # Unknown provider — pass api_key if provided
        if settings.stt_api_key:
            kwargs["api_key"] = settings.stt_api_key

    return default_registry.create(ProviderType.STT, name, **kwargs)


# ---------------------------------------------------------------------------
# Public factory for creating pipelines
# ---------------------------------------------------------------------------


def create_pipeline(
    settings: AudioServiceSettings,
    meeting_id: UUID,
    event_publisher: EventPublisher | None = None,
) -> AudioPipeline:
    """Create an AudioPipeline with the configured STT provider.

    Args:
        settings: Audio service settings.
        meeting_id: Meeting ID for event attribution.
        event_publisher: Optional event publisher.

    Returns:
        A configured AudioPipeline instance.
    """
    stt_provider = _create_stt_provider(settings, meeting_id)
    return AudioPipeline(
        stt_provider=stt_provider,
        event_publisher=event_publisher,
        meeting_id=meeting_id,
    )


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_settings: AudioServiceSettings | None = None
_event_publisher: EventPublisher | None = None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Validates STT configuration on startup by creating and immediately
    closing a test provider instance. Creates the EventPublisher on
    startup and closes it on shutdown.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to the ASGI server while the app is running.
    """
    global _settings, _event_publisher

    _settings = AudioServiceSettings()
    _event_publisher = EventPublisher(redis_url=_settings.redis_url)

    # Validate STT config at startup — fail fast if misconfigured
    test_provider = _create_stt_provider(_settings, uuid4())
    await test_provider.close()
    logger.info(
        "audio-service starting up (stt_provider=%s)", _settings.stt_provider
    )

    yield

    logger.info("audio-service shutting down")
    if _event_publisher is not None:
        await _event_publisher.close()
        _event_publisher = None
    _settings = None


app = FastAPI(
    title="Convene AI Audio Service",
    description="Audio pipeline and transport adapters for Convene AI",
    version="0.2.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response model for the health check endpoint.

    Attributes:
        status: Current health status of the service.
        service: Name of the service reporting health.
    """

    status: str
    service: str


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return the health status of the audio service.

    Returns:
        HealthResponse with status and service name.
    """
    return HealthResponse(status="healthy", service="audio-service")
