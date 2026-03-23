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
from typing import TYPE_CHECKING

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
from agent_gateway.auth import AuthError, validate_token
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
    global _settings, _connection_manager, _event_relay, _audio_bridge, _turn_bridge, _db_session_factory, _redis_client

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

    _connection_manager = ConnectionManager(max_connections=_settings.max_connections)
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

    await _event_relay.start()
    logger.info("agent-gateway starting up (max_connections=%d)", _settings.max_connections)

    yield

    logger.info("agent-gateway shutting down")
    if _turn_bridge is not None:
        await _turn_bridge.stop()
        _turn_bridge = None
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
