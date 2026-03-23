"""Configuration settings for the agent gateway service."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class AgentGatewaySettings(BaseSettings):
    """Configuration for the agent gateway.

    Attributes:
        redis_url: Redis connection URL for event streams.
        jwt_secret: Secret key for JWT token validation.
        jwt_algorithm: Algorithm used for JWT tokens.
        max_connections: Maximum concurrent agent connections.
        heartbeat_interval_s: Seconds between heartbeat pings.
        heartbeat_timeout_s: Seconds before a missed heartbeat disconnects.
        stt_provider: STT provider name (whisper, whisper-remote, deepgram, assemblyai).
        stt_api_key: API key for cloud STT providers.
        whisper_model_size: Whisper model size for local whisper.
        whisper_api_url: Remote Whisper API URL for whisper-remote.
        speaker_timeout_seconds: Seconds before auto-advancing speaker (default 300 / 5 min).
        tts_provider: TTS provider to use (piper, cartesia, elevenlabs).
        tts_cartesia_api_key: Cartesia API key (required when tts_provider=cartesia).
        tts_elevenlabs_api_key: ElevenLabs API key (required when tts_provider=elevenlabs).
        tts_char_limit: Per-agent character budget per session (default 100 K).
        tts_default_voice: Default voice ID when the pool is exhausted or provider-specific.
    """

    database_url: str = "postgresql+asyncpg://convene:convene@localhost:5432/convene"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    max_connections: int = 100
    heartbeat_interval_s: int = 30
    heartbeat_timeout_s: int = 90
    stt_provider: str = "whisper"
    stt_api_key: str = ""
    whisper_model_size: str = "small"
    whisper_api_url: str = ""
    speaker_timeout_seconds: int = 300
    # TTS settings
    tts_provider: str = "piper"  # piper | cartesia | elevenlabs
    tts_cartesia_api_key: str = ""
    tts_elevenlabs_api_key: str = ""
    tts_char_limit: int = 100_000
    tts_default_voice: str = "en_US-lessac-medium"

    model_config = {
        "env_prefix": "AGENT_GATEWAY_",
        "case_sensitive": False,
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }
