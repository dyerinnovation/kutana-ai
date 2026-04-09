"""Tests for channel subscription and source-tracking in the agent gateway."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from agent_gateway.auth import AgentIdentity, create_agent_token, validate_token
from agent_gateway.event_relay import EventRelay
from agent_gateway.protocol import (
    JoinMeeting,
    ParticipantUpdate,
    SubscribeChannel,
    parse_client_message,
)

# ---------------------------------------------------------------------------
# Protocol tests
# ---------------------------------------------------------------------------


class TestSubscribeChannelMessage:
    """Tests for the new SubscribeChannel protocol message."""

    def test_subscribe_channel_defaults(self) -> None:
        """SubscribeChannel holds a list of channel names."""
        msg = SubscribeChannel(channels=["tasks", "decisions"])
        assert msg.type == "subscribe_channel"
        assert msg.channels == ["tasks", "decisions"]

    def test_subscribe_channel_single(self) -> None:
        """SubscribeChannel works with a single channel."""
        msg = SubscribeChannel(channels=["chat"])
        assert len(msg.channels) == 1

    def test_parse_subscribe_channel(self) -> None:
        """parse_client_message correctly parses subscribe_channel."""
        msg = parse_client_message(
            {
                "type": "subscribe_channel",
                "channels": ["tasks", "summaries"],
            }
        )
        assert isinstance(msg, SubscribeChannel)
        assert "tasks" in msg.channels

    def test_join_meeting_has_source_field(self) -> None:
        """JoinMeeting includes the source field with default 'agent'."""
        msg = JoinMeeting(meeting_id=uuid4())
        assert msg.source == "agent"

    def test_join_meeting_custom_source(self) -> None:
        """JoinMeeting accepts custom source values like 'claude-code'."""
        msg = JoinMeeting(meeting_id=uuid4(), source="claude-code")
        assert msg.source == "claude-code"

    def test_participant_update_has_source_field(self) -> None:
        """ParticipantUpdate includes the optional source field."""
        msg = ParticipantUpdate(
            action="joined",
            participant_id=uuid4(),
            name="Claude",
            role="observer",
            source="claude-code",
        )
        assert msg.source == "claude-code"

    def test_participant_update_source_optional(self) -> None:
        """ParticipantUpdate source is None by default."""
        msg = ParticipantUpdate(
            action="joined",
            participant_id=uuid4(),
            name="Alice",
            role="host",
        )
        assert msg.source is None


# ---------------------------------------------------------------------------
# Auth tests
# ---------------------------------------------------------------------------


class TestSourceInAuth:
    """Tests for source claim in AgentIdentity and JWT."""

    def test_agent_identity_default_source(self) -> None:
        """AgentIdentity has 'agent' as default source."""
        identity = AgentIdentity(
            agent_config_id=uuid4(),
            name="test-agent",
            capabilities=["listen"],
        )
        assert identity.source == "agent"

    def test_agent_identity_claude_code_source(self) -> None:
        """AgentIdentity accepts 'claude-code' source."""
        identity = AgentIdentity(
            agent_config_id=uuid4(),
            name="claude-code",
            capabilities=["listen"],
            source="claude-code",
        )
        assert identity.source == "claude-code"

    def test_create_token_includes_source(self) -> None:
        """create_agent_token includes the source claim in the JWT."""
        import jwt

        agent_id = uuid4()
        secret = "test-secret"
        token = create_agent_token(
            agent_config_id=agent_id,
            name="claude",
            capabilities=["listen"],
            secret=secret,
            source="claude-code",
        )
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        assert payload["source"] == "claude-code"

    def test_validate_token_extracts_source(self) -> None:
        """validate_token extracts the source claim from the JWT."""
        agent_id = uuid4()
        secret = "test-secret"
        token = create_agent_token(
            agent_config_id=agent_id,
            name="claude",
            capabilities=["listen"],
            secret=secret,
            source="claude-code",
        )
        identity = validate_token(token, secret)
        assert identity.source == "claude-code"

    def test_validate_token_defaults_source_to_agent(self) -> None:
        """validate_token defaults source to 'agent' when claim is absent."""
        import time

        import jwt

        secret = "test-secret"
        # Token without source claim
        payload = {
            "sub": str(uuid4()),
            "name": "old-agent",
            "capabilities": ["listen"],
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, secret, algorithm="HS256")
        identity = validate_token(token, secret)
        assert identity.source == "agent"


# ---------------------------------------------------------------------------
# AgentSessionHandler subscribe tests
# ---------------------------------------------------------------------------


class TestAgentSessionSubscribeChannel:
    """Tests for AgentSessionHandler._handle_subscribe_channel."""

    def _make_session(self, capabilities: list[str] | None = None) -> tuple:
        """Create a mock session and its handler for testing."""
        from agent_gateway.agent_session import AgentSessionHandler

        mock_ws = AsyncMock()
        identity = AgentIdentity(
            agent_config_id=uuid4(),
            name="test-agent",
            capabilities=capabilities or ["listen", "transcribe"],
            source="agent",
        )
        manager = MagicMock()
        manager.redis = None
        manager.turn_bridge = None
        handler = AgentSessionHandler(
            websocket=mock_ws,
            identity=identity,
            connection_manager=manager,
        )
        return handler, mock_ws

    async def test_subscribe_channel_adds_to_set(self) -> None:
        """_handle_subscribe_channel adds channels to subscribed_channels."""
        handler, _ = self._make_session()
        msg = SubscribeChannel(channels=["tasks", "decisions"])
        await handler._handle_subscribe_channel(msg)
        assert "tasks" in handler.subscribed_channels
        assert "decisions" in handler.subscribed_channels

    async def test_subscribe_channel_accumulates(self) -> None:
        """Multiple subscribe calls accumulate channels."""
        handler, _ = self._make_session()
        await handler._handle_subscribe_channel(SubscribeChannel(channels=["tasks"]))
        await handler._handle_subscribe_channel(SubscribeChannel(channels=["chat"]))
        assert "tasks" in handler.subscribed_channels
        assert "chat" in handler.subscribed_channels

    async def test_join_meeting_sets_source_from_message(self) -> None:
        """_handle_join updates source when message source is not 'agent'."""
        handler, ws = self._make_session()
        handler._manager.join_meeting = MagicMock()
        handler._db_factory = None
        ws.send_json = AsyncMock()

        msg = JoinMeeting(
            meeting_id=uuid4(),
            capabilities=["listen", "transcribe"],
            source="claude-code",
        )
        # Patch _persist_join to avoid DB call
        handler._persist_join = AsyncMock()
        await handler._handle_join(msg)

        assert handler.source == "claude-code"

    async def test_join_meeting_keeps_jwt_source_when_message_says_agent(self) -> None:
        """_handle_join does not override source when message says 'agent'."""
        from agent_gateway.agent_session import AgentSessionHandler

        mock_ws = AsyncMock()
        identity = AgentIdentity(
            agent_config_id=uuid4(),
            name="test-agent",
            capabilities=["listen", "transcribe"],
            source="claude-code",  # JWT says claude-code
        )
        manager = MagicMock()
        manager.redis = None
        manager.turn_bridge = None
        handler = AgentSessionHandler(
            websocket=mock_ws,
            identity=identity,
            connection_manager=manager,
        )
        handler._manager.join_meeting = MagicMock()
        handler._persist_join = AsyncMock()
        mock_ws.send_json = AsyncMock()

        # Message says "agent" — should not override the JWT source
        msg = JoinMeeting(meeting_id=uuid4(), source="agent")
        await handler._handle_join(msg)

        assert handler.source == "claude-code"


# ---------------------------------------------------------------------------
# EventRelay channel routing tests
# ---------------------------------------------------------------------------


@pytest.fixture
def connection_manager() -> MagicMock:
    """Create a mock ConnectionManager."""
    return MagicMock()


@pytest.fixture
def relay(connection_manager: MagicMock) -> EventRelay:
    """Create an EventRelay with mocked Redis."""
    with patch("agent_gateway.event_relay.redis") as mock_redis_module:
        mock_redis = AsyncMock()
        mock_redis_module.from_url.return_value = mock_redis
        r = EventRelay(
            redis_url="redis://localhost:6379/0",
            connection_manager=connection_manager,
        )
        r._redis = mock_redis
        return r


def _make_mock_session(
    capabilities: list[str] | None = None,
    subscribed_channels: set[str] | None = None,
) -> AsyncMock:
    """Create a mock session."""
    session = AsyncMock()
    session.session_id = uuid4()
    session.capabilities = capabilities or ["listen", "transcribe"]
    session.subscribed_channels = subscribed_channels or set()
    session.send_transcript = AsyncMock()
    session.send_event = AsyncMock()
    return session


class TestEventRelayChannelRouting:
    """Tests for EventRelay data-channel routing with subscribed_channels."""

    async def test_channel_event_routes_to_subscribed_session(
        self, relay: EventRelay, connection_manager: MagicMock
    ) -> None:
        """A data.channel.tasks event goes to a session subscribed to 'tasks'."""
        meeting_id = uuid4()
        session = _make_mock_session(subscribed_channels={"tasks"})
        connection_manager.get_meeting_sessions.return_value = [session]

        payload = json.dumps({"meeting_id": str(meeting_id), "channel": "tasks", "msg": "hi"})
        await relay._handle_event("msg-1", {"event_type": "data.channel.tasks", "payload": payload})

        session.send_event.assert_awaited_once()

    async def test_channel_event_not_routed_when_not_subscribed(
        self, relay: EventRelay, connection_manager: MagicMock
    ) -> None:
        """A data.channel.tasks event does NOT go to a session not subscribed."""
        meeting_id = uuid4()
        session = _make_mock_session(subscribed_channels={"decisions"})
        connection_manager.get_meeting_sessions.return_value = [session]

        payload = json.dumps({"meeting_id": str(meeting_id), "channel": "tasks", "msg": "hi"})
        await relay._handle_event("msg-1", {"event_type": "data.channel.tasks", "payload": payload})

        session.send_event.assert_not_awaited()

    async def test_wildcard_subscription_receives_all_channels(
        self, relay: EventRelay, connection_manager: MagicMock
    ) -> None:
        """A session subscribed to '*' receives all channel events."""
        meeting_id = uuid4()
        session = _make_mock_session(subscribed_channels={"*"})
        connection_manager.get_meeting_sessions.return_value = [session]

        payload = json.dumps({"meeting_id": str(meeting_id), "channel": "anything", "msg": "hi"})
        await relay._handle_event(
            "msg-1", {"event_type": "data.channel.anything", "payload": payload}
        )

        session.send_event.assert_awaited_once()

    async def test_no_subscriptions_routes_to_all(
        self, relay: EventRelay, connection_manager: MagicMock
    ) -> None:
        """A session with empty subscribed_channels receives all channel events."""
        meeting_id = uuid4()
        session = _make_mock_session(subscribed_channels=set())
        connection_manager.get_meeting_sessions.return_value = [session]

        payload = json.dumps({"meeting_id": str(meeting_id), "channel": "tasks", "msg": "hi"})
        await relay._handle_event("msg-1", {"event_type": "data.channel.tasks", "payload": payload})

        # Empty set means no filter — all events should pass through
        session.send_event.assert_awaited_once()

    def test_should_relay_channel_with_subscription(self, relay: EventRelay) -> None:
        """_should_relay returns True for subscribed channel."""
        assert (
            relay._should_relay(
                "data.channel.tasks",
                ["listen"],
                subscribed_channels={"tasks"},
            )
            is True
        )

    def test_should_relay_channel_not_subscribed(self, relay: EventRelay) -> None:
        """_should_relay returns False for unsubscribed channel."""
        assert (
            relay._should_relay(
                "data.channel.tasks",
                ["listen"],
                subscribed_channels={"decisions"},
            )
            is False
        )

    def test_should_relay_channel_wildcard(self, relay: EventRelay) -> None:
        """_should_relay returns True for wildcard subscription."""
        assert (
            relay._should_relay(
                "data.channel.anything",
                ["listen"],
                subscribed_channels={"*"},
            )
            is True
        )

    def test_should_relay_channel_no_filter(self, relay: EventRelay) -> None:
        """_should_relay returns True when subscribed_channels is None (no filter)."""
        assert (
            relay._should_relay(
                "data.channel.tasks",
                ["listen"],
                subscribed_channels=None,
            )
            is True
        )
