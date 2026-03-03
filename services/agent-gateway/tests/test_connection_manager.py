"""Tests for the agent gateway connection manager."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from agent_gateway.connection_manager import ConnectionManager


def _make_session(
    session_id=None,
    agent_name="test-agent",
    meeting_id=None,
):
    """Create a mock AgentSessionHandler."""
    session = MagicMock()
    session.session_id = session_id or uuid4()
    session.agent_name = agent_name
    session.meeting_id = meeting_id
    return session


class TestConnectionManager:
    """Tests for ConnectionManager."""

    def test_initial_state(self) -> None:
        """Manager starts with no connections."""
        manager = ConnectionManager(max_connections=10)
        assert manager.active_count == 0
        assert not manager.is_full()

    def test_register_session(self) -> None:
        """Sessions can be registered."""
        manager = ConnectionManager()
        session = _make_session()
        manager.register(session)
        assert manager.active_count == 1

    def test_unregister_session(self) -> None:
        """Sessions can be unregistered."""
        manager = ConnectionManager()
        session = _make_session()
        manager.register(session)
        manager.unregister(session.session_id)
        assert manager.active_count == 0

    def test_unregister_nonexistent_session(self) -> None:
        """Unregistering a nonexistent session is a no-op."""
        manager = ConnectionManager()
        manager.unregister(uuid4())  # Should not raise
        assert manager.active_count == 0

    def test_connection_limit(self) -> None:
        """Registering beyond max_connections raises RuntimeError."""
        manager = ConnectionManager(max_connections=2)
        manager.register(_make_session())
        manager.register(_make_session())
        assert manager.is_full()

        with pytest.raises(RuntimeError, match="Connection limit reached"):
            manager.register(_make_session())

    def test_get_session(self) -> None:
        """Sessions can be retrieved by ID."""
        manager = ConnectionManager()
        session = _make_session()
        manager.register(session)

        found = manager.get_session(session.session_id)
        assert found is session

    def test_get_session_not_found(self) -> None:
        """Returns None for unknown session ID."""
        manager = ConnectionManager()
        assert manager.get_session(uuid4()) is None

    def test_join_meeting(self) -> None:
        """Sessions can join meetings."""
        manager = ConnectionManager()
        session = _make_session()
        meeting_id = uuid4()
        manager.register(session)
        manager.join_meeting(session.session_id, meeting_id)

        sessions = manager.get_meeting_sessions(meeting_id)
        assert len(sessions) == 1
        assert sessions[0] is session

    def test_multiple_sessions_in_meeting(self) -> None:
        """Multiple sessions can join the same meeting."""
        manager = ConnectionManager()
        s1 = _make_session()
        s2 = _make_session()
        meeting_id = uuid4()

        manager.register(s1)
        manager.register(s2)
        manager.join_meeting(s1.session_id, meeting_id)
        manager.join_meeting(s2.session_id, meeting_id)

        sessions = manager.get_meeting_sessions(meeting_id)
        assert len(sessions) == 2

    def test_leave_meeting(self) -> None:
        """Sessions can leave meetings."""
        manager = ConnectionManager()
        session = _make_session()
        meeting_id = uuid4()

        manager.register(session)
        manager.join_meeting(session.session_id, meeting_id)
        manager.leave_meeting(session.session_id, meeting_id)

        sessions = manager.get_meeting_sessions(meeting_id)
        assert len(sessions) == 0

    def test_get_meeting_sessions_empty(self) -> None:
        """Returns empty list for unknown meeting."""
        manager = ConnectionManager()
        assert manager.get_meeting_sessions(uuid4()) == []

    def test_unregister_cleans_meeting_association(self) -> None:
        """Unregistering a session removes its meeting association."""
        manager = ConnectionManager()
        session = _make_session()
        meeting_id = uuid4()
        session.meeting_id = meeting_id

        manager.register(session)
        manager.join_meeting(session.session_id, meeting_id)
        manager.unregister(session.session_id)

        sessions = manager.get_meeting_sessions(meeting_id)
        assert len(sessions) == 0

    def test_get_all_sessions(self) -> None:
        """get_all_sessions returns all registered sessions."""
        manager = ConnectionManager()
        s1 = _make_session()
        s2 = _make_session()
        manager.register(s1)
        manager.register(s2)

        all_sessions = manager.get_all_sessions()
        assert len(all_sessions) == 2
