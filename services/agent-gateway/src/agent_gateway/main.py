"""FastAPI application entry point for the Convene AI Agent Gateway."""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

# Enable application-level logging so session events are visible in docker logs
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s [%(name)s] %(message)s",
    stream=sys.stdout,
)
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import redis.asyncio as redis_async

from agent_gateway.agent_session import AgentSessionHandler
from agent_gateway.audio_bridge import AudioBridge
from agent_gateway.audio_session import AudioSessionHandler
from agent_gateway.auth import AuthError, validate_token
from agent_gateway.chat_bridge import ChatBridge
from agent_gateway.connection_manager import ConnectionManager
from agent_gateway.event_relay import EventRelay
from agent_gateway.human_session import HumanSessionHandler
from agent_gateway.settings import AgentGatewaySettings
from agent_gateway.turn_bridge import TurnBridge

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_settings: AgentGatewaySettings | None = None
_connection_manager: ConnectionManager | None = None
_event_relay: EventRelay | None = None
_audio_bridge: AudioBridge | None = None
_turn_bridge: TurnBridge | None = None
_chat_bridge: ChatBridge | None = None
_tts_bridge: Any | None = None  # TTSBridge; imported lazily to avoid circular deps
_db_session_factory: async_sessionmaker[AsyncSession] | None = None
_redis_client: redis_async.Redis | None = None  # type: ignore[type-arg]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown lifecycle.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to the ASGI server while the app is running.
    """
    global _settings, _connection_manager, _event_relay, _audio_bridge, _turn_bridge, _chat_bridge, _tts_bridge, _db_session_factory, _redis_client

    _settings = AgentGatewaySettings()
    logger.info(
        "Gateway settings: stt_provider=%s, whisper_api_url=%s, redis_url=%s",
        _settings.stt_provider, _settings.whisper_api_url, _settings.redis_url,
    )

    # Database session factory for agent session persistence
    engine = create_async_engine(
        _settings.database_url,
        pool_pre_ping=True,
    )
    _db_session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    _connection_manager = ConnectionManager(
        max_connections=_settings.max_connections,
        audio_vad_timeout_s=_settings.audio_vad_timeout_s,
    )
    _redis_client = redis_async.from_url(_settings.redis_url, decode_responses=True)
    _connection_manager.redis = _redis_client
    _event_relay = EventRelay(
        redis_url=_settings.redis_url,
        connection_manager=_connection_manager,
    )
    _audio_bridge = AudioBridge(
        redis_url=_settings.redis_url,
        stt_provider=_settings.stt_provider,
        stt_api_key=_settings.stt_api_key,
        whisper_model_size=_settings.whisper_model_size,
        whisper_api_url=_settings.whisper_api_url,
    )

    # Initialise TurnBridge (Redis-backed turn management)
    from convene_providers.turn_management.redis_turn_manager import RedisTurnManager

    _turn_manager = RedisTurnManager(
        redis_url=_settings.redis_url,
        speaker_timeout_seconds=_settings.speaker_timeout_seconds,
    )
    _turn_bridge = TurnBridge(
        turn_manager=_turn_manager,
        manager=_connection_manager,
        speaker_timeout_seconds=_settings.speaker_timeout_seconds,
    )
    _connection_manager.turn_bridge = _turn_bridge
    _turn_bridge.start()

    # Initialise ChatBridge (Redis Streams storage + Pub/Sub broadcast)
    from convene_providers.chat.redis_chat_store import RedisChatStore

    _chat_store = RedisChatStore(redis_url=_settings.redis_url)
    _chat_bridge = ChatBridge(
        chat_store=_chat_store,
        manager=_connection_manager,
        redis_url=_settings.redis_url,
    )
    _connection_manager.chat_bridge = _chat_bridge
    _chat_bridge.start()

    # Initialise TTSBridge (provider selection based on config)
    from agent_gateway.tts_bridge import TTSBridge

    _tts_provider_name = _settings.tts_provider.lower()
    if _tts_provider_name == "cartesia" and _settings.tts_cartesia_api_key:
        from convene_providers.tts.cartesia_tts import CartesiaTTS

        _raw_tts_provider = CartesiaTTS(api_key=_settings.tts_cartesia_api_key)
        logger.info("TTS provider: Cartesia")
    elif _tts_provider_name == "elevenlabs" and _settings.tts_elevenlabs_api_key:
        from convene_providers.tts.elevenlabs_tts import ElevenLabsTTS

        _raw_tts_provider = ElevenLabsTTS(api_key=_settings.tts_elevenlabs_api_key)
        logger.info("TTS provider: ElevenLabs")
    else:
        from convene_providers.tts.piper_tts import PiperTTS

        _raw_tts_provider = PiperTTS(voice_name=_settings.tts_default_voice)
        logger.info(
            "TTS provider: Piper (available=%s)", getattr(_raw_tts_provider, "is_available", False)
        )

    _tts_bridge = TTSBridge(
        tts_provider=_raw_tts_provider,
        manager=_connection_manager,
        char_limit=_settings.tts_char_limit,
    )
    _connection_manager.tts_bridge = _tts_bridge

    await _event_relay.start()
    logger.info("agent-gateway starting up (max_connections=%d)", _settings.max_connections)

    yield

    logger.info("agent-gateway shutting down")
    if _chat_bridge is not None:
        await _chat_bridge.stop()
        _chat_bridge = None
    if _turn_bridge is not None:
        await _turn_bridge.stop()
        _turn_bridge = None
    if _tts_bridge is not None:
        await _tts_bridge.close()
        _tts_bridge = None
    if _audio_bridge is not None:
        await _audio_bridge.close()
        _audio_bridge = None
    if _event_relay is not None:
        await _event_relay.stop()
        _event_relay = None
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
    _connection_manager = None
    _db_session_factory = None
    await engine.dispose()
    _settings = None


app = FastAPI(
    title="Convene AI Agent Gateway",
    description="WebSocket gateway for AI agent connections to Convene meetings",
    version="0.1.0",
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
        active_connections: Number of active agent connections.
    """

    status: str
    service: str
    active_connections: int


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return the health status of the agent gateway.

    Returns:
        HealthResponse with status, service name, and connection count.
    """
    count = _connection_manager.active_count if _connection_manager else 0
    return HealthResponse(
        status="healthy",
        service="agent-gateway",
        active_connections=count,
    )


# ---------------------------------------------------------------------------
# Agent WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/agent/connect")
async def agent_connect(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token"),
) -> None:
    """WebSocket endpoint for AI agent connections.

    Validates the JWT token, creates a session, and enters the
    message handling loop.

    Args:
        websocket: The incoming WebSocket connection.
        token: JWT token for authentication.
    """
    if _settings is None or _connection_manager is None:
        await websocket.accept()
        await websocket.close(code=1011, reason="Service not initialized")
        return

    # Validate token before accepting the connection
    try:
        identity = validate_token(
            token,
            _settings.jwt_secret,
            _settings.jwt_algorithm,
        )
    except AuthError as e:
        await websocket.accept()
        await websocket.close(code=4001, reason=f"{e.code}: {e.message}")
        return

    # Check connection limit
    if _connection_manager.is_full():
        await websocket.accept()
        await websocket.close(code=4029, reason="Connection limit reached")
        return

    await websocket.accept()

    # Create and register session
    session = AgentSessionHandler(
        websocket=websocket,
        identity=identity,
        connection_manager=_connection_manager,
        audio_bridge=_audio_bridge,
        db_session_factory=_db_session_factory,
        tts_bridge=_tts_bridge,
        jwt_secret=_settings.jwt_secret,
        gateway_url=_settings.gateway_url,
    )
    _connection_manager.register(session)

    logger.info(
        "Agent connected: %s (config=%s)",
        identity.name,
        identity.agent_config_id,
    )

    try:
        await session.handle()
    except WebSocketDisconnect:
        logger.info("Agent %s disconnected normally", identity.name)
    except Exception:
        logger.exception("Error in agent session %s", session.session_id)
    finally:
        _connection_manager.unregister(session.session_id)


# ---------------------------------------------------------------------------
# Human WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/human/connect")
async def human_connect(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token"),
    meeting_id: str = Query(..., description="UUID of the meeting to join"),
) -> None:
    """WebSocket endpoint for human browser connections.

    Unlike /agent/connect, this endpoint:
    - Auto-joins the meeting on connect (no join_meeting message required).
    - Always grants speak + listen + transcribe capabilities.
    - Accepts meeting_id as a URL query parameter.

    Args:
        websocket: The incoming WebSocket connection.
        token: JWT token for authentication (obtained from /token/meeting).
        meeting_id: UUID of the meeting to join.
    """
    if _settings is None or _connection_manager is None:
        await websocket.accept()
        await websocket.close(code=1011, reason="Service not initialized")
        return

    # Validate token
    try:
        identity = validate_token(
            token,
            _settings.jwt_secret,
            _settings.jwt_algorithm,
        )
    except AuthError as e:
        await websocket.accept()
        await websocket.close(code=4001, reason=f"{e.code}: {e.message}")
        return

    # Parse meeting_id
    from uuid import UUID as _UUID

    try:
        parsed_meeting_id = _UUID(meeting_id)
    except ValueError:
        await websocket.accept()
        await websocket.close(code=4003, reason="invalid_meeting_id: must be a valid UUID")
        return

    # Check connection limit
    if _connection_manager.is_full():
        await websocket.accept()
        await websocket.close(code=4029, reason="Connection limit reached")
        return

    await websocket.accept()

    session = HumanSessionHandler(
        websocket=websocket,
        identity=identity,
        meeting_id=parsed_meeting_id,
        connection_manager=_connection_manager,
        audio_bridge=_audio_bridge,
    )
    _connection_manager.register(session)

    logger.info(
        "Human connected: %s (meeting=%s)",
        identity.name,
        parsed_meeting_id,
    )

    try:
        await session.handle()
    except WebSocketDisconnect:
        logger.info("Human %s disconnected normally", identity.name)
    except Exception:
        logger.exception("Error in human session %s", session.session_id)
    finally:
        _connection_manager.unregister(session.session_id)


# ---------------------------------------------------------------------------
# Audio sidecar WebSocket endpoint
# ---------------------------------------------------------------------------


@app.websocket("/audio/connect")
async def audio_connect(
    websocket: WebSocket,
    token: str = Query(..., description="Audio JWT token (from join_meeting response)"),
    meeting_id: str = Query(..., description="UUID of the meeting to connect audio for"),
    audio_format: str = Query("pcm16", description="Audio format: pcm16 (default) or opus"),
) -> None:
    """WebSocket endpoint for bidirectional agent audio streaming (voice sidecar).

    This endpoint is the audio plane for voice-capable agents. The control plane
    (MCP tools, turn management, chat) remains on /agent/connect.

    Protocol:
        Client → Server:
            { type: "start_speaking" }
            { type: "stop_speaking" }
            { type: "audio_data", data: "<base64 PCM16>", timestamp: <ms> }
            { type: "ping" }

        Server → Client:
            { type: "audio_session_joined", session_id, meeting_id, format }
            { type: "mixed_audio", data: "<base64 PCM16>", speakers: [participant_id] }
            { type: "speaker_changed", participant_id, action: "started"|"stopped" }
            { type: "pong" }
            { type: "error", code, message }

    Args:
        websocket: The incoming WebSocket connection.
        token: Short-lived audio JWT obtained from the join_meeting Joined response.
        meeting_id: UUID of the meeting (must match the meeting in the audio token).
        audio_format: Negotiated audio format (pcm16 or opus; pcm16 is always supported).
    """
    if _settings is None or _connection_manager is None:
        await websocket.accept()
        await websocket.close(code=1011, reason="Service not initialized")
        return

    # Validate audio token
    try:
        identity = validate_token(
            token,
            _settings.jwt_secret,
            _settings.jwt_algorithm,
        )
    except AuthError as e:
        await websocket.accept()
        await websocket.close(code=4001, reason=f"{e.code}: {e.message}")
        return

    # Parse and validate meeting_id
    from uuid import UUID as _UUID

    try:
        parsed_meeting_id = _UUID(meeting_id)
    except ValueError:
        await websocket.accept()
        await websocket.close(code=4003, reason="invalid_meeting_id: must be a valid UUID")
        return

    # Validate audio_format
    if audio_format not in ("pcm16", "opus"):
        await websocket.accept()
        await websocket.close(code=4003, reason="invalid_format: supported formats are pcm16, opus")
        return

    await websocket.accept()

    # Get or create the per-meeting AudioRouter
    audio_router = _connection_manager.get_or_create_audio_router(parsed_meeting_id)

    audio_session = AudioSessionHandler(
        websocket=websocket,
        identity=identity,
        meeting_id=parsed_meeting_id,
        audio_router=audio_router,
        audio_format=audio_format,
    )

    logger.info(
        "Audio session connecting: agent=%s, meeting=%s, format=%s",
        identity.name,
        parsed_meeting_id,
        audio_format,
    )

    try:
        await audio_session.handle()
    except WebSocketDisconnect:
        logger.info("Audio session %s disconnected normally", audio_session.session_id)
    except Exception:
        logger.exception("Error in audio session %s", audio_session.session_id)
    finally:
        # Clean up the router if it has no remaining sessions
        await _connection_manager.cleanup_audio_router(parsed_meeting_id)
