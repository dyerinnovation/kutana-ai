"""Integration tests for agent capability declaration.

Tests the full flow: JoinMeeting with capabilities → Joined response
with granted_capabilities → ParticipantUpdate with capabilities →
ParticipantJoined event with audio_capability field.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from agent_gateway.agent_session import AgentSessionHandler
from agent_gateway.protocol import JoinMeeting

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MEETING_ID = uuid4()
_AGENT_CONFIG_ID = uuid4()


def _make_identity(
    capabilities: list[str] | None = None,
) -> MagicMock:
    """Create a mock AgentIdentity with given capabilities."""
    identity = MagicMock()
    identity.agent_config_id = _AGENT_CONFIG_ID
    identity.name = "TestAgent"
    identity.source = "agent"
    identity.capabilities = capabilities or [
        "listen",
        "transcribe",
        "speak",
        "voice",
    ]
    return identity


def _make_websocket() -> AsyncMock:
    """Create a mock WebSocket that captures sent messages."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    return ws


def _make_connection_manager() -> MagicMock:
    """Create a mock ConnectionManager."""
    cm = MagicMock()
    cm.join_meeting = MagicMock()
    cm.leave_meeting = MagicMock()
    cm.get_meeting_sessions = MagicMock(return_value=[])
    cm.redis = None
    cm.turn_bridge = None
    return cm


def _make_handler(
    identity: MagicMock | None = None,
    capabilities: list[str] | None = None,
) -> tuple[AgentSessionHandler, AsyncMock]:
    """Create an AgentSessionHandler with mocked dependencies.

    Returns:
        Tuple of (handler, mock_websocket).
    """
    ws = _make_websocket()
    ident = identity or _make_identity(capabilities)
    cm = _make_connection_manager()
    handler = AgentSessionHandler(
        websocket=ws,
        identity=ident,
        connection_manager=cm,
        jwt_secret="test-secret",
        gateway_url="ws://localhost:8003",
    )
    return handler, ws


# ---------------------------------------------------------------------------
# Tests: Capability grant and Joined response
# ---------------------------------------------------------------------------


class TestCapabilityGrant:
    """Tests that JoinMeeting capabilities are granted correctly."""

    @pytest.mark.asyncio
    async def test_text_only_grants_listen_transcribe(self) -> None:
        """Agent requesting listen+transcribe gets exactly those capabilities."""
        handler, ws = _make_handler()
        msg = JoinMeeting(
            meeting_id=_MEETING_ID,
            capabilities=["listen", "transcribe"],
        )
        await handler._handle_join(msg)

        sent = ws.send_json.call_args[0][0]
        assert sent["type"] == "joined"
        assert set(sent["granted_capabilities"]) == {"listen", "transcribe"}

    @pytest.mark.asyncio
    async def test_voice_grants_voice_capability(self) -> None:
        """Agent requesting voice gets voice in granted capabilities."""
        handler, ws = _make_handler()
        msg = JoinMeeting(
            meeting_id=_MEETING_ID,
            capabilities=["listen", "transcribe", "voice"],
        )
        await handler._handle_join(msg)

        sent = ws.send_json.call_args[0][0]
        assert "voice" in sent["granted_capabilities"]

    @pytest.mark.asyncio
    async def test_voice_returns_audio_sidecar_url(self) -> None:
        """Voice-capable agents receive audio_ws_url and audio_token in Joined."""
        handler, ws = _make_handler()
        msg = JoinMeeting(
            meeting_id=_MEETING_ID,
            capabilities=["listen", "transcribe", "voice"],
        )
        await handler._handle_join(msg)

        sent = ws.send_json.call_args[0][0]
        assert sent["audio_ws_url"] is not None
        assert "audio/connect" in sent["audio_ws_url"]
        assert sent["audio_token"] is not None

    @pytest.mark.asyncio
    async def test_text_only_no_audio_sidecar(self) -> None:
        """Text-only agents do not receive audio_ws_url."""
        handler, ws = _make_handler()
        msg = JoinMeeting(
            meeting_id=_MEETING_ID,
            capabilities=["listen", "transcribe"],
        )
        await handler._handle_join(msg)

        sent = ws.send_json.call_args[0][0]
        assert sent["audio_ws_url"] is None
        assert sent["audio_token"] is None

    @pytest.mark.asyncio
    async def test_capability_intersection(self) -> None:
        """Granted capabilities are intersection of requested and allowed."""
        identity = _make_identity(capabilities=["listen", "transcribe"])
        handler, ws = _make_handler(identity=identity)
        msg = JoinMeeting(
            meeting_id=_MEETING_ID,
            capabilities=["listen", "transcribe", "speak", "voice"],
        )
        await handler._handle_join(msg)

        sent = ws.send_json.call_args[0][0]
        granted = set(sent["granted_capabilities"])
        assert granted == {"listen", "transcribe"}
        assert "speak" not in granted
        assert "voice" not in granted


# ---------------------------------------------------------------------------
# Tests: audio_capability inference
# ---------------------------------------------------------------------------


class TestAudioCapabilityInference:
    """Tests for _infer_audio_capability."""

    def test_text_only(self) -> None:
        handler, _ = _make_handler()
        handler.capabilities = ["listen", "transcribe"]
        result = handler._infer_audio_capability(tts_enabled=False)
        assert result == "text_only"

    def test_voice(self) -> None:
        handler, _ = _make_handler()
        handler.capabilities = ["listen", "transcribe", "voice"]
        result = handler._infer_audio_capability(tts_enabled=False)
        assert result == "voice"

    def test_tts_enabled(self) -> None:
        handler, _ = _make_handler()
        handler.capabilities = ["listen", "transcribe"]
        result = handler._infer_audio_capability(tts_enabled=True)
        assert result == "tts_enabled"

    def test_voice_overrides_tts(self) -> None:
        """voice takes precedence over tts_enabled."""
        handler, _ = _make_handler()
        handler.capabilities = ["listen", "transcribe", "voice"]
        result = handler._infer_audio_capability(tts_enabled=True)
        assert result == "voice"


# ---------------------------------------------------------------------------
# Tests: ParticipantJoined event includes capabilities
# ---------------------------------------------------------------------------


class TestParticipantEvent:
    """Tests that participant events include capabilities and audio_capability."""

    @pytest.mark.asyncio
    async def test_participant_joined_event_includes_capabilities(self) -> None:
        """ParticipantJoined event published to Redis includes capabilities."""
        handler, _ws = _make_handler()
        handler._manager.redis = AsyncMock()
        handler._manager.redis.xadd = AsyncMock()

        msg = JoinMeeting(
            meeting_id=_MEETING_ID,
            capabilities=["listen", "transcribe", "voice"],
        )
        await handler._handle_join(msg)

        # Find the xadd call for participant.joined
        calls = handler._manager.redis.xadd.call_args_list
        participant_call = None
        for call in calls:
            args = call[0] if call[0] else []
            kwargs = call[1] if call[1] else {}
            event_data = args[1] if len(args) > 1 else kwargs.get("fields", {})
            if (
                isinstance(event_data, dict)
                and event_data.get("event_type") == "participant.joined"
            ):
                participant_call = event_data
                break

        assert participant_call is not None, "participant.joined event not published"
        payload = json.loads(participant_call["payload"])
        assert "capabilities" in payload
        assert "voice" in payload["capabilities"]
        assert payload["audio_capability"] == "voice"

    @pytest.mark.asyncio
    async def test_participant_joined_event_text_only(self) -> None:
        """Text-only agent has audio_capability=text_only in participant event."""
        handler, _ws = _make_handler()
        handler._manager.redis = AsyncMock()
        handler._manager.redis.xadd = AsyncMock()

        msg = JoinMeeting(
            meeting_id=_MEETING_ID,
            capabilities=["listen", "transcribe"],
        )
        await handler._handle_join(msg)

        calls = handler._manager.redis.xadd.call_args_list
        for call in calls:
            args = call[0] if call[0] else []
            event_data = args[1] if len(args) > 1 else {}
            if (
                isinstance(event_data, dict)
                and event_data.get("event_type") == "participant.joined"
            ):
                payload = json.loads(event_data["payload"])
                assert payload["audio_capability"] == "text_only"
                return

        pytest.fail("participant.joined event not published")


# ---------------------------------------------------------------------------
# Tests: ParticipantUpdate broadcast includes capabilities
# ---------------------------------------------------------------------------


class TestParticipantUpdateBroadcast:
    """Tests that participant_update WebSocket messages include capabilities."""

    @pytest.mark.asyncio
    async def test_broadcast_includes_capabilities(self) -> None:
        """participant_update sent to other sessions includes capabilities."""
        handler, _ws = _make_handler()

        other_session = AsyncMock()
        other_session.session_id = uuid4()
        other_session.send_participant_update = AsyncMock()

        handler._manager.get_meeting_sessions = MagicMock(return_value=[other_session])

        msg = JoinMeeting(
            meeting_id=_MEETING_ID,
            capabilities=["listen", "transcribe", "voice"],
        )
        await handler._handle_join(msg)

        other_session.send_participant_update.assert_called_once()
        call_kwargs = other_session.send_participant_update.call_args[1]
        assert call_kwargs["action"] == "joined"
        assert "voice" in call_kwargs["capabilities"]
