"""Active agent session registry for the gateway."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

    from agent_gateway.agent_session import AgentSessionHandler

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Registry of active agent WebSocket sessions.

    Thread-safe within a single asyncio event loop (no concurrent
    mutations from multiple threads).

    Attributes:
        _sessions: Map of session_id -> AgentSessionHandler.
        _meeting_sessions: Map of meeting_id -> set of session_ids.
        _max_connections: Maximum allowed concurrent connections.
    """

    def __init__(self, max_connections: int = 100) -> None:
        """Initialise the connection manager.

        Args:
            max_connections: Maximum concurrent agent connections.
        """
        self._sessions: dict[UUID, AgentSessionHandler] = {}
        self._meeting_sessions: dict[UUID, set[UUID]] = {}
        self._max_connections = max_connections

    @property
    def active_count(self) -> int:
        """Return the number of active sessions."""
        return len(self._sessions)

    def is_full(self) -> bool:
        """Check if the maximum connection limit has been reached."""
        return self.active_count >= self._max_connections

    def register(self, session: AgentSessionHandler) -> None:
        """Register a new agent session.

        Args:
            session: The session handler to register.

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

    def get_session(self, session_id: UUID) -> AgentSessionHandler | None:
        """Get a session by ID.

        Args:
            session_id: The session ID to look up.

        Returns:
            The session handler, or None if not found.
        """
        return self._sessions.get(session_id)

    def get_meeting_sessions(self, meeting_id: UUID) -> list[AgentSessionHandler]:
        """Get all sessions in a meeting.

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

    def get_all_sessions(self) -> list[AgentSessionHandler]:
        """Return all active sessions."""
        return list(self._sessions.values())
