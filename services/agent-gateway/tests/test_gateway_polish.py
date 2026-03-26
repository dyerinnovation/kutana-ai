"""Tests for Agent Gateway Polish: multi-agent support, audio routing, data channel.

Covers:
 - ConnectionManager.get_audio_router (non-creating lookup)
 - AgentSessionHandler participant notifications on join and leave
 - AgentSessionHandler participants snapshot in Joined response
 - AgentSessionHandler._leave_and_notify idempotency
 - AgentSessionHandler._handle_audio routes to existing AudioRouter
 - HumanSessionHandler._handle_audio routes to existing AudioRouter
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session(
    session_id: UUID | None = None,
    agent_name: str = "agent",
    meeting_id: UUID | None = None,
    source: str = "agent",
    capabilities: list[str] | None = None,
) -> MagicMock:
    """Return a mock session satisfying the SessionHandler protocol."""
    s = MagicMock()
    s.session_id = session_id or uuid4()
    s.agent_name = agent_name
    s.meeting_id = meeting_id
    s.source = source
    s.capabilities = capabilities or ["listen", "transcribe"]
    s.send_participant_update = AsyncMock()
    return s


def _make_connection_manager(
    sessions: list[MagicMock] | None = None,
    meeting_sessions: list[MagicMock] | None = None,
) -> MagicMock:
    """Return a mock ConnectionManager."""
    mgr = MagicMock()
    mgr.redis = None
    mgr.turn_bridge = None
    mgr.tts_bridge = None
    mgr.get_meeting_sessions = MagicMock(return_value=meeting_sessions or [])
    mgr.join_meeting = MagicMock()
    mgr.leave_meeting = MagicMock()
    mgr.unregister = MagicMock()
    mgr.get_audio_router = MagicMock(return_value=None)
    return mgr


def _make_identity(
    agent_config_id: UUID | None = None,
    name: str = "test-agent",
    source: str = "agent",
    capabilities: list[str] | None = None,
) -> MagicMock:
    """Return a mock AgentIdentity."""
    identity = MagicMock()
    identity.agent_config_id = agent_config_id or uuid4()
    identity.name = name
    identity.source = source
    identity.capabilities = capabilities or ["listen", "speak", "transcribe"]
    return identity


def _make_websocket(send_json: AsyncMock | None = None) -> MagicMock:
    """Return a mock FastAPI WebSocket."""
    ws = MagicMock()
    ws.send_json = send_json or AsyncMock()
    return ws


# ---------------------------------------------------------------------------
# ConnectionManager.get_audio_router
# ---------------------------------------------------------------------------


class TestConnectionManagerGetAudioRouter:
    """Tests for the non-creating get_audio_router method."""

    def test_returns_none_when_no_router_exists(self) -> None:
        """get_audio_router returns None when no sidecar sessions have connected."""
        from agent_gateway.connection_manager import ConnectionManager

        mgr = ConnectionManager()
        meeting_id = uuid4()
        assert mgr.get_audio_router(meeting_id) is None

    def test_returns_router_after_creation(self) -> None:
        """get_audio_router returns the router created by get_or_create."""
        from agent_gateway.connection_manager import ConnectionManager

        mgr = ConnectionManager()
        meeting_id = uuid4()
        # Create via get_or_create, then fetch via get
        router = mgr.get_or_create_audio_router(meeting_id)
        assert mgr.get_audio_router(meeting_id) is router

    def test_returns_none_for_different_meeting(self) -> None:
        """get_audio_router returns None for a meeting that has no router."""
        from agent_gateway.connection_manager import ConnectionManager

        mgr = ConnectionManager()
        meeting_a = uuid4()
        meeting_b = uuid4()
        mgr.get_or_create_audio_router(meeting_a)
        assert mgr.get_audio_router(meeting_b) is None

    def test_does_not_create_router(self) -> None:
        """get_audio_router must not create a new AudioRouter."""
        from agent_gateway.connection_manager import ConnectionManager

        mgr = ConnectionManager()
        meeting_id = uuid4()
        mgr.get_audio_router(meeting_id)  # should not create
        # _audio_routers must still be empty
        assert meeting_id not in mgr._audio_routers  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AgentSessionHandler — snapshot_participants
# ---------------------------------------------------------------------------


class TestSnapshotParticipants:
    """Tests for AgentSessionHandler._snapshot_participants."""

    def _make_agent_session_handler(
        self,
        identity: MagicMock | None = None,
        connection_manager: MagicMock | None = None,
        ws: MagicMock | None = None,
    ) -> object:
        from agent_gateway.agent_session import AgentSessionHandler

        return AgentSessionHandler(
            websocket=ws or _make_websocket(),
            identity=identity or _make_identity(),
            connection_manager=connection_manager or _make_connection_manager(),
        )

    def test_returns_empty_list_for_empty_meeting(self) -> None:
        """Snapshot is empty when no other participants are in the meeting."""
        mgr = _make_connection_manager(meeting_sessions=[])
        handler = self._make_agent_session_handler(connection_manager=mgr)
        result = handler._snapshot_participants(uuid4())  # type: ignore[attr-defined]
        assert result == []

    def test_excludes_self(self) -> None:
        """Snapshot excludes the current session."""
        mgr = _make_connection_manager()
        handler = self._make_agent_session_handler(connection_manager=mgr)
        # Only session in meeting is self
        mgr.get_meeting_sessions.return_value = [handler]
        result = handler._snapshot_participants(uuid4())  # type: ignore[attr-defined]
        assert result == []

    def test_includes_other_participants(self) -> None:
        """Snapshot includes all other sessions in the meeting."""
        mgr = _make_connection_manager()
        handler = self._make_agent_session_handler(connection_manager=mgr)
        other = _make_mock_session(agent_name="other-agent", source="claude-code")
        mgr.get_meeting_sessions.return_value = [other]

        result = handler._snapshot_participants(uuid4())  # type: ignore[attr-defined]
        assert len(result) == 1
        assert result[0]["name"] == "other-agent"
        assert result[0]["role"] == "claude-code"

    def test_snapshot_contains_expected_keys(self) -> None:
        """Each snapshot entry has the required participant dict keys."""
        mgr = _make_connection_manager()
        handler = self._make_agent_session_handler(connection_manager=mgr)
        other = _make_mock_session()
        mgr.get_meeting_sessions.return_value = [other]

        result = handler._snapshot_participants(uuid4())  # type: ignore[attr-defined]
        assert "participant_id" in result[0]
        assert "name" in result[0]
        assert "role" in result[0]
        assert "connection_type" in result[0]
        assert "capabilities" in result[0]


# ---------------------------------------------------------------------------
# AgentSessionHandler — _broadcast_participant_update
# ---------------------------------------------------------------------------


class TestBroadcastParticipantUpdate:
    """Tests for AgentSessionHandler._broadcast_participant_update."""

    def _make_handler(
        self, connection_manager: MagicMock | None = None
    ) -> object:
        from agent_gateway.agent_session import AgentSessionHandler

        handler = AgentSessionHandler(
            websocket=_make_websocket(),
            identity=_make_identity(),
            connection_manager=connection_manager or _make_connection_manager(),
        )
        handler.meeting_id = uuid4()
        return handler

    @pytest.mark.asyncio
    async def test_noop_when_no_meeting(self) -> None:
        """Does nothing if the agent hasn't joined a meeting."""
        from agent_gateway.agent_session import AgentSessionHandler

        mgr = _make_connection_manager()
        handler = AgentSessionHandler(
            websocket=_make_websocket(),
            identity=_make_identity(),
            connection_manager=mgr,
        )
        # meeting_id is None (not joined)
        await handler._broadcast_participant_update("joined")  # type: ignore[attr-defined]
        mgr.get_meeting_sessions.assert_not_called()

    @pytest.mark.asyncio
    async def test_skips_self(self) -> None:
        """Does not send participant_update to itself."""
        mgr = _make_connection_manager()
        handler = self._make_handler(connection_manager=mgr)
        # Only session in meeting is itself
        mgr.get_meeting_sessions.return_value = [handler]

        await handler._broadcast_participant_update("joined")  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_sends_to_other_sessions(self) -> None:
        """Sends participant_update to all other sessions in the meeting."""
        mgr = _make_connection_manager()
        handler = self._make_handler(connection_manager=mgr)
        other_a = _make_mock_session()
        other_b = _make_mock_session()
        mgr.get_meeting_sessions.return_value = [handler, other_a, other_b]

        await handler._broadcast_participant_update("joined")  # type: ignore[attr-defined]

        other_a.send_participant_update.assert_awaited_once()
        other_b.send_participant_update.assert_awaited_once()
        call_kwargs = other_a.send_participant_update.call_args.kwargs
        assert call_kwargs["action"] == "joined"
        assert call_kwargs["role"] == "agent"

    @pytest.mark.asyncio
    async def test_broadcasts_left_action(self) -> None:
        """Sends 'left' action when broadcasting a leave."""
        mgr = _make_connection_manager()
        handler = self._make_handler(connection_manager=mgr)
        other = _make_mock_session()
        mgr.get_meeting_sessions.return_value = [handler, other]

        await handler._broadcast_participant_update("left")  # type: ignore[attr-defined]

        call_kwargs = other.send_participant_update.call_args.kwargs
        assert call_kwargs["action"] == "left"

    @pytest.mark.asyncio
    async def test_swallows_send_errors(self) -> None:
        """Errors in individual send_participant_update do not propagate."""
        mgr = _make_connection_manager()
        handler = self._make_handler(connection_manager=mgr)
        bad_session = _make_mock_session()
        bad_session.send_participant_update = AsyncMock(
            side_effect=RuntimeError("ws closed")
        )
        mgr.get_meeting_sessions.return_value = [handler, bad_session]

        # Must not raise
        await handler._broadcast_participant_update("joined")  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AgentSessionHandler — _leave_and_notify idempotency
# ---------------------------------------------------------------------------


class TestLeaveAndNotify:
    """Tests for AgentSessionHandler._leave_and_notify."""

    def _make_handler(self) -> object:
        from agent_gateway.agent_session import AgentSessionHandler

        mgr = _make_connection_manager()
        handler = AgentSessionHandler(
            websocket=_make_websocket(),
            identity=_make_identity(),
            connection_manager=mgr,
        )
        handler.meeting_id = uuid4()
        return handler

    @pytest.mark.asyncio
    async def test_noop_without_meeting(self) -> None:
        """Does nothing when meeting_id is None."""
        from agent_gateway.agent_session import AgentSessionHandler

        mgr = _make_connection_manager()
        handler = AgentSessionHandler(
            websocket=_make_websocket(),
            identity=_make_identity(),
            connection_manager=mgr,
        )
        # meeting_id is None
        await handler._leave_and_notify()  # type: ignore[attr-defined]
        mgr.leave_meeting.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_leave_meeting_once(self) -> None:
        """leave_meeting is called exactly once even on repeated calls."""
        handler = self._make_handler()
        mgr = handler._manager  # type: ignore[attr-defined]
        mgr.get_meeting_sessions.return_value = []

        await handler._leave_and_notify("voluntary")  # type: ignore[attr-defined]
        await handler._leave_and_notify("voluntary")  # second call should be no-op

        mgr.leave_meeting.assert_called_once()

    @pytest.mark.asyncio
    async def test_sets_left_announced_flag(self) -> None:
        """_left_announced is set to True after first call."""
        handler = self._make_handler()
        handler._manager.get_meeting_sessions.return_value = []  # type: ignore[attr-defined]

        assert not handler._left_announced  # type: ignore[attr-defined]
        await handler._leave_and_notify()  # type: ignore[attr-defined]
        assert handler._left_announced  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AgentSessionHandler._handle_audio — AudioRouter routing
# ---------------------------------------------------------------------------


class TestAgentHandleAudioRouting:
    """Tests for audio routing to existing AudioRouter in _handle_audio."""

    def _make_handler_with_audio_bridge(
        self,
        meeting_id: UUID | None = None,
        router: MagicMock | None = None,
    ) -> tuple[object, MagicMock]:
        """Create a handler with an audio bridge and optional mock router."""
        from agent_gateway.agent_session import AgentSessionHandler

        mgr = _make_connection_manager()
        mgr.get_audio_router.return_value = router
        identity = _make_identity(capabilities=["listen", "speak", "transcribe"])
        handler = AgentSessionHandler(
            websocket=_make_websocket(),
            identity=identity,
            connection_manager=mgr,
        )
        handler.meeting_id = meeting_id or uuid4()
        handler.capabilities = ["speak", "listen"]
        return handler, mgr

    @pytest.mark.asyncio
    async def test_no_router_no_error(self) -> None:
        """Audio is forwarded to STT when no AudioRouter exists."""
        import base64

        handler, mgr = self._make_handler_with_audio_bridge(router=None)
        audio_bridge = AsyncMock()
        handler._audio_bridge = audio_bridge  # type: ignore[attr-defined]
        pcm = base64.b64encode(b"\x00" * 640).decode()

        from agent_gateway.protocol import AudioData

        await handler._handle_audio(AudioData(data=pcm))  # type: ignore[attr-defined]

        audio_bridge.process_audio.assert_awaited_once()
        mgr.get_audio_router.assert_called_once_with(handler.meeting_id)  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_routes_to_existing_audio_router(self) -> None:
        """When an AudioRouter exists, audio is distributed to sidecar sessions."""
        import base64

        router = MagicMock()
        router.route_audio = AsyncMock()
        handler, _mgr = self._make_handler_with_audio_bridge(router=router)
        handler._audio_bridge = None  # type: ignore[attr-defined]
        pcm = base64.b64encode(b"\x00" * 640).decode()

        from agent_gateway.protocol import AudioData

        await handler._handle_audio(AudioData(data=pcm))  # type: ignore[attr-defined]

        router.route_audio.assert_awaited_once()
        call_args = router.route_audio.call_args
        # First positional arg is the session_id
        assert call_args.args[0] == handler.session_id  # type: ignore[attr-defined]

    @pytest.mark.asyncio
    async def test_route_audio_error_swallowed(self) -> None:
        """Errors from route_audio do not propagate to the caller."""
        import base64

        router = MagicMock()
        router.route_audio = AsyncMock(side_effect=RuntimeError("router error"))
        handler, _mgr = self._make_handler_with_audio_bridge(router=router)
        handler._audio_bridge = None  # type: ignore[attr-defined]
        pcm = base64.b64encode(b"\x00" * 640).decode()

        from agent_gateway.protocol import AudioData

        # Must not raise
        await handler._handle_audio(AudioData(data=pcm))  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# HumanSessionHandler._handle_audio — AudioRouter routing
# ---------------------------------------------------------------------------


class TestHumanHandleAudioRouting:
    """Tests for audio routing to existing AudioRouter in HumanSessionHandler._handle_audio."""

    def _make_human_handler(
        self,
        meeting_id: UUID | None = None,
        router: MagicMock | None = None,
    ) -> object:
        from agent_gateway.human_session import HumanSessionHandler

        mgr = _make_connection_manager()
        mgr.get_audio_router.return_value = router
        identity = _make_identity()
        return HumanSessionHandler(
            websocket=_make_websocket(),
            identity=identity,
            meeting_id=meeting_id or uuid4(),
            connection_manager=mgr,
        )

    @pytest.mark.asyncio
    async def test_no_router_no_error(self) -> None:
        """Audio is forwarded to STT when no AudioRouter exists."""
        import base64

        handler = self._make_human_handler(router=None)
        audio_bridge = AsyncMock()
        handler._audio_bridge = audio_bridge  # type: ignore[attr-defined]
        pcm = base64.b64encode(b"\x00" * 640).decode()

        from agent_gateway.protocol import AudioData

        await handler._handle_audio(AudioData(data=pcm))  # type: ignore[attr-defined]

        audio_bridge.process_audio.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_routes_to_existing_audio_router(self) -> None:
        """Human audio is distributed to sidecar sessions via AudioRouter."""
        import base64

        router = MagicMock()
        router.route_audio = AsyncMock()
        handler = self._make_human_handler(router=router)
        handler._audio_bridge = None  # type: ignore[attr-defined]
        pcm = base64.b64encode(b"\x00" * 640).decode()

        from agent_gateway.protocol import AudioData

        await handler._handle_audio(AudioData(data=pcm))  # type: ignore[attr-defined]

        router.route_audio.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_route_audio_error_swallowed(self) -> None:
        """Errors from AudioRouter do not crash the human session."""
        import base64

        router = MagicMock()
        router.route_audio = AsyncMock(side_effect=RuntimeError("router error"))
        handler = self._make_human_handler(router=router)
        handler._audio_bridge = None  # type: ignore[attr-defined]
        pcm = base64.b64encode(b"\x00" * 640).decode()

        from agent_gateway.protocol import AudioData

        # Must not raise
        await handler._handle_audio(AudioData(data=pcm))  # type: ignore[attr-defined]
