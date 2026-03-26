"""Active agent and human session registry for the gateway."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable
from uuid import UUID

if TYPE_CHECKING:
    from agent_gateway.agent_session import AgentSessionHandler
    from agent_gateway.audio_router import AudioRouter
    from agent_gateway.chat_bridge import ChatBridge
    from agent_gateway.human_session import HumanSessionHandler
    from agent_gateway.tts_bridge import TTSBridge
    from agent_gateway.turn_bridge import TurnBridge

logger = logging.getLogger(__name__)


@runtime_checkable
class SessionHandler(Protocol):
    """Protocol satisfied by both AgentSessionHandler and HumanSessionHandler.

    The EventRelay and ConnectionManager use this protocol so they can hold
    and route to both agent and human sessions without a concrete base class.
    """

    session_id: UUID
    agent_name: str
    meeting_id: UUID | None
    capabilities: list[str]

    async def send_transcript(
        self,
        meeting_id: UUID,
        speaker_id: str | None,
        text: str,
        start_time: float,
        end_time: float,
        confidence: float,
        speaker_name: str | None = None,
    ) -> None: ...

    async def send_event(self, event_type: str, payload: dict[str, Any]) -> None: ...


# Union type used in type annotations only.
AnySession = "AgentSessionHandler | HumanSessionHandler"


class ConnectionManager:
    """Registry of active WebSocket sessions (agents and human browsers).

    Thread-safe within a single asyncio event loop (no concurrent
    mutations from multiple threads).

    Attributes:
        _sessions: Map of session_id -> session handler.
        _meeting_sessions: Map of meeting_id -> set of session_ids.
        _audio_routers: Map of meeting_id -> AudioRouter for the audio sidecar.
        _max_connections: Maximum allowed concurrent connections.
        redis: Optional Redis client for channel publishing.
        _audio_vad_timeout_s: VAD silence timeout forwarded to new AudioRouters.
    """

    def __init__(
        self,
        max_connections: int = 100,
        audio_vad_timeout_s: int = 10,
    ) -> None:
        """Initialise the connection manager.

        Args:
            max_connections: Maximum concurrent connections.
            audio_vad_timeout_s: Silence seconds before VAD auto-stops a speaker.
        """
        self._sessions: dict[UUID, Any] = {}  # AgentSessionHandler | HumanSessionHandler
        self._meeting_sessions: dict[UUID, set[UUID]] = {}
        self._audio_routers: dict[UUID, AudioRouter] = {}
        self._max_connections = max_connections
        self._audio_vad_timeout_s = audio_vad_timeout_s
        self.redis: Any | None = None
        self.turn_bridge: TurnBridge | None = None
        self.chat_bridge: ChatBridge | None = None
        self.tts_bridge: TTSBridge | None = None

    @property
    def active_count(self) -> int:
        """Return the number of active sessions."""
        return len(self._sessions)

    def is_full(self) -> bool:
        """Check if the maximum connection limit has been reached."""
        return self.active_count >= self._max_connections

    def register(self, session: Any) -> None:
        """Register a new session (agent or human).

        Args:
            session: The session handler to register (AgentSessionHandler or HumanSessionHandler).

        Raises:
            RuntimeError: If the connection limit is reached.
        """
        if self.is_full():
            msg = f"Connection limit reached ({self._max_connections})"
            raise RuntimeError(msg)

        self._sessions[session.session_id] = session
        logger.info(
            "Agent session registered: %s (agent=%s, total=%d)",
            session.session_id,
            session.agent_name,
            self.active_count,
        )

    def unregister(self, session_id: UUID) -> None:
        """Remove an agent session from the registry.

        Args:
            session_id: The session ID to remove.
        """
        session = self._sessions.pop(session_id, None)
        if session is None:
            return

        # Clean up meeting associations
        if session.meeting_id is not None:
            meeting_set = self._meeting_sessions.get(session.meeting_id)
            if meeting_set:
                meeting_set.discard(session_id)
                if not meeting_set:
                    del self._meeting_sessions[session.meeting_id]

        logger.info(
            "Agent session unregistered: %s (total=%d)",
            session_id,
            self.active_count,
        )

    def join_meeting(self, session_id: UUID, meeting_id: UUID) -> None:
        """Associate a session with a meeting.

        Args:
            session_id: The session joining the meeting.
            meeting_id: The meeting being joined.
        """
        if meeting_id not in self._meeting_sessions:
            self._meeting_sessions[meeting_id] = set()
        self._meeting_sessions[meeting_id].add(session_id)

    def leave_meeting(self, session_id: UUID, meeting_id: UUID) -> None:
        """Remove a session from a meeting association.

        Args:
            session_id: The session leaving.
            meeting_id: The meeting being left.
        """
        meeting_set = self._meeting_sessions.get(meeting_id)
        if meeting_set:
            meeting_set.discard(session_id)
            if not meeting_set:
                del self._meeting_sessions[meeting_id]

    def get_session(self, session_id: UUID) -> Any | None:
        """Get a session by ID.

        Args:
            session_id: The session ID to look up.

        Returns:
            The session handler, or None if not found.
        """
        return self._sessions.get(session_id)

    def get_meeting_sessions(self, meeting_id: UUID) -> list[Any]:
        """Get all sessions (agents + humans) in a meeting.

        Args:
            meeting_id: The meeting to look up.

        Returns:
            List of session handlers in the meeting.
        """
        session_ids = self._meeting_sessions.get(meeting_id, set())
        return [
            self._sessions[sid]
            for sid in session_ids
            if sid in self._sessions
        ]

    def get_all_sessions(self) -> list[Any]:
        """Return all active sessions."""
        return list(self._sessions.values())

    # ------------------------------------------------------------------
    # Audio router management
    # ------------------------------------------------------------------

    def get_or_create_audio_router(self, meeting_id: UUID) -> AudioRouter:
        """Return the AudioRouter for a meeting, creating one if needed.

        The router is started on first creation so its VAD monitor is running
        before the first audio session connects.

        Args:
            meeting_id: The meeting to get or create a router for.

        Returns:
            The active AudioRouter for the meeting.
        """
        from agent_gateway.audio_router import AudioRouter

        if meeting_id not in self._audio_routers:
            router = AudioRouter(
                meeting_id=meeting_id,
                vad_timeout_s=self._audio_vad_timeout_s,
            )
            router.start()
            self._audio_routers[meeting_id] = router
            logger.info(
                "AudioRouter created for meeting %s (vad_timeout=%ds)",
                meeting_id,
                self._audio_vad_timeout_s,
            )
        return self._audio_routers[meeting_id]

    async def cleanup_audio_router(self, meeting_id: UUID) -> None:
        """Stop and remove the AudioRouter for a meeting if it is empty.

        Should be called after an audio session disconnects so idle routers
        don't accumulate.

        Args:
            meeting_id: The meeting whose router to clean up.
        """
        router = self._audio_routers.get(meeting_id)
        if router is not None and router.is_empty:
            await router.stop()
            del self._audio_routers[meeting_id]
            logger.info("AudioRouter cleaned up for meeting %s", meeting_id)
