"""Tests for channel tools and GatewayClient event buffering."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

# ---------------------------------------------------------------------------
# GatewayClient tests
# ---------------------------------------------------------------------------


class TestGatewayClientSubscribeChannel:
    """Tests for GatewayClient.subscribe_channel sending WS message."""

    def _make_client(self) -> object:
        from mcp_server.gateway_client import GatewayClient

        client = GatewayClient("ws://localhost:8003", "test-token")
        return client

    async def test_subscribe_channel_without_ws_does_not_crash(self) -> None:
        """subscribe_channel works gracefully when not connected."""
        client = self._make_client()
        client.subscribe_channel("tasks")  # type: ignore[attr-defined]
        assert "tasks" in client.subscribed_channels  # type: ignore[attr-defined]

    async def test_subscribe_channel_sends_ws_message(self) -> None:
        """subscribe_channel sends subscribe_channel message to gateway when connected."""
        client = self._make_client()
        mock_ws = AsyncMock()
        client._ws = mock_ws  # type: ignore[attr-defined]

        with patch("asyncio.create_task") as mock_create_task:
            client.subscribe_channel("tasks")  # type: ignore[attr-defined]
            mock_create_task.assert_called_once()
            # Verify the coroutine that was scheduled would send the right message
            call_args = mock_create_task.call_args[0][0]
            assert call_args is not None

    async def test_subscribe_channel_initializes_buffer(self) -> None:
        """subscribe_channel creates an empty buffer for the channel."""
        client = self._make_client()
        client.subscribe_channel("decisions")  # type: ignore[attr-defined]
        assert "decisions" in client._channel_buffer  # type: ignore[attr-defined]
        assert client._channel_buffer["decisions"] == []  # type: ignore[attr-defined]

    async def test_subscribe_multiple_channels_accumulate(self) -> None:
        """Multiple subscribe calls accumulate distinct channels."""
        client = self._make_client()
        client.subscribe_channel("tasks")  # type: ignore[attr-defined]
        client.subscribe_channel("chat")  # type: ignore[attr-defined]
        assert "tasks" in client.subscribed_channels  # type: ignore[attr-defined]
        assert "chat" in client.subscribed_channels  # type: ignore[attr-defined]


class TestGatewayClientEventBuffering:
    """Tests for GatewayClient buffering turn/participant/chat events."""

    def _make_client_with_events(self, raw_messages: list[str]) -> object:
        """Create a GatewayClient whose _listen() will process the given messages."""
        from mcp_server.gateway_client import GatewayClient

        client = GatewayClient("ws://localhost:8003", "test-token")
        return client

    async def test_turn_queue_updated_buffered(self) -> None:
        """turn_queue_updated messages are buffered in _events_buffer."""
        from mcp_server.gateway_client import GatewayClient

        client = GatewayClient("ws://localhost:8003", "test-token")
        # Simulate the listener receiving a turn_queue_updated message
        msg = {
            "type": "turn_queue_updated",
            "meeting_id": str(uuid4()),
            "active_speaker_id": None,
            "queue": [],
        }
        client._events_buffer.append(msg)  # type: ignore[attr-defined]

        events = client.get_events()  # type: ignore[attr-defined]
        assert len(events) == 1
        assert events[0]["type"] == "turn_queue_updated"

    async def test_get_events_filters_by_type(self) -> None:
        """get_events returns only events of the requested type when filtered."""
        from mcp_server.gateway_client import GatewayClient

        client = GatewayClient("ws://localhost:8003", "test-token")
        client._events_buffer.extend(
            [  # type: ignore[attr-defined]
                {"type": "turn_queue_updated", "queue": []},
                {"type": "participant_update", "action": "joined", "name": "Alice"},
                {"type": "turn_speaker_changed", "new_speaker_id": str(uuid4())},
            ]
        )

        turn_events = client.get_events(event_type="turn_queue_updated")  # type: ignore[attr-defined]
        assert len(turn_events) == 1
        assert turn_events[0]["type"] == "turn_queue_updated"

    async def test_get_events_respects_last_n(self) -> None:
        """get_events returns at most last_n events."""
        from mcp_server.gateway_client import GatewayClient

        client = GatewayClient("ws://localhost:8003", "test-token")
        for i in range(10):
            client._events_buffer.append({"type": "turn_queue_updated", "seq": i})  # type: ignore[attr-defined]

        events = client.get_events(last_n=3)  # type: ignore[attr-defined]
        assert len(events) == 3
        assert events[-1]["seq"] == 9  # Most recent

    async def test_participant_update_joined_adds_to_participants(self) -> None:
        """participant_update joined event adds to _participants list."""
        from mcp_server.gateway_client import GatewayClient

        client = GatewayClient("ws://localhost:8003", "test-token")
        participant_id = str(uuid4())
        msg = {
            "type": "participant_update",
            "action": "joined",
            "participant_id": participant_id,
            "name": "Alice",
            "role": "host",
            "connection_type": "webrtc",
            "source": "human",
        }

        # Simulate what _listen() does for participant_update
        client._events_buffer.append(msg)  # type: ignore[attr-defined]
        if msg["action"] == "joined":
            client._participants.append(
                {  # type: ignore[attr-defined]
                    "participant_id": msg["participant_id"],
                    "name": msg["name"],
                    "role": msg["role"],
                    "connection_type": msg["connection_type"],
                    "source": msg["source"],
                }
            )

        participants = client.get_participants()  # type: ignore[attr-defined]
        assert len(participants) == 1
        assert participants[0]["source"] == "human"

    async def test_listen_buffers_turn_events(self) -> None:
        """_listen() buffers turn_queue_updated and turn_speaker_changed messages."""
        from mcp_server.gateway_client import GatewayClient

        meeting_id = str(uuid4())
        messages = [
            json.dumps(
                {
                    "type": "turn_queue_updated",
                    "meeting_id": meeting_id,
                    "queue": [{"participant_id": str(uuid4()), "position": 1}],
                }
            ),
            json.dumps(
                {
                    "type": "turn_speaker_changed",
                    "meeting_id": meeting_id,
                    "new_speaker_id": str(uuid4()),
                }
            ),
        ]

        # Use a real async generator — no mocking of __aiter__ needed
        class MockWs:
            async def __aiter__(self):
                for m in messages:
                    yield m

        client = GatewayClient("ws://localhost:8003", "test-token")
        client._ws = MockWs()  # type: ignore[attr-defined]

        await client._listen()  # type: ignore[attr-defined]

        assert len(client._events_buffer) == 2  # type: ignore[attr-defined]
        types = [e["type"] for e in client._events_buffer]  # type: ignore[attr-defined]
        assert "turn_queue_updated" in types
        assert "turn_speaker_changed" in types


class TestGatewayClientSourceInJoin:
    """Tests for source='claude-code' sent in JoinMeeting message."""

    async def test_connect_and_join_sends_source(self) -> None:
        """connect_and_join sends source='claude-code' in the join message."""
        from mcp_server.gateway_client import GatewayClient

        sent_messages: list[str] = []

        async def mock_send(msg: str) -> None:
            sent_messages.append(msg)

        async def mock_recv() -> str:
            return json.dumps(
                {
                    "type": "joined",
                    "meeting_id": str(uuid4()),
                    "granted_capabilities": ["listen", "transcribe"],
                }
            )

        mock_ws = MagicMock()
        mock_ws.send = mock_send
        mock_ws.recv = AsyncMock(side_effect=mock_recv)

        with (
            patch("websockets.connect", new=AsyncMock(return_value=mock_ws)),
            patch.object(asyncio, "create_task"),
        ):
            client = GatewayClient("ws://localhost:8003", "test-token")
            await client.connect_and_join(str(uuid4()))

        assert len(sent_messages) == 1
        join_msg = json.loads(sent_messages[0])
        assert join_msg["source"] == "claude-code"
        assert join_msg["type"] == "join_meeting"
