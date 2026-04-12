"""Unit tests for LiveKitAgentWorker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from agent_gateway.livekit_worker import LiveKitAgentWorker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LK_URL = "ws://localhost:7880"
_LK_ROOM = "test-room"
_LK_KEY = "test-api-key"
_LK_SECRET = "test-api-secret"


def _make_mock_audio_bridge(pipeline: object | None = None) -> MagicMock:
    """Return a mock AudioBridge with a controllable pipeline."""
    bridge = MagicMock()
    bridge.ensure_pipeline = AsyncMock()
    bridge.get_pipeline = MagicMock(return_value=pipeline if pipeline is not None else MagicMock())
    return bridge


def _make_token_builder() -> MagicMock:
    """Return a fluent AccessToken builder mock."""
    builder = MagicMock()
    builder.with_identity.return_value = builder
    builder.with_name.return_value = builder
    builder.with_grants.return_value = builder
    builder.to_jwt.return_value = "signed-jwt"
    return builder


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def meeting_id():
    return uuid4()


@pytest.fixture
def mock_bridge():
    return _make_mock_audio_bridge()


@pytest.fixture
def worker(meeting_id, mock_bridge):
    return LiveKitAgentWorker(
        meeting_id=meeting_id,
        livekit_room_name=_LK_ROOM,
        livekit_url=_LK_URL,
        livekit_api_key=_LK_KEY,
        livekit_api_secret=_LK_SECRET,
        audio_bridge=mock_bridge,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestConnect:
    """Tests for LiveKitAgentWorker.connect()."""

    async def test_connect_creates_room_and_wires_adapter_publisher(
        self, worker, mock_bridge
    ) -> None:
        """connect() creates Room, connects it, starts adapter and publisher."""
        mock_room = AsyncMock()
        mock_adapter = AsyncMock()
        mock_publisher = AsyncMock()
        mock_pipeline = MagicMock()
        mock_bridge.get_pipeline.return_value = mock_pipeline

        with (
            patch("agent_gateway.livekit_worker.rtc") as mock_rtc,
            patch("agent_gateway.livekit_worker.api") as mock_api,
            patch(
                "agent_gateway.livekit_worker.LiveKitAudioAdapter",
                return_value=mock_adapter,
            ) as mock_adapter_cls,
            patch(
                "agent_gateway.livekit_worker.LiveKitAudioPublisher",
                return_value=mock_publisher,
            ) as mock_publisher_cls,
        ):
            mock_rtc.Room.return_value = mock_room
            mock_api.AccessToken.return_value = _make_token_builder()

            await worker.connect()

        mock_rtc.Room.assert_called_once()
        mock_room.connect.assert_awaited_once_with(_LK_URL, "signed-jwt")
        mock_bridge.ensure_pipeline.assert_awaited_once()
        mock_adapter_cls.assert_called_once_with(pipeline=mock_pipeline, room=mock_room)
        mock_adapter.start.assert_awaited_once()
        mock_publisher_cls.assert_called_once_with(room=mock_room)
        mock_publisher.start.assert_awaited_once()

    async def test_connect_generates_correct_token(self, worker, meeting_id) -> None:
        """connect() uses identity kutana-gateway-{meeting_id} with correct grants."""
        mock_room = AsyncMock()
        mock_adapter = AsyncMock()
        mock_publisher = AsyncMock()
        token_builder = _make_token_builder()

        with (
            patch("agent_gateway.livekit_worker.rtc") as mock_rtc,
            patch("agent_gateway.livekit_worker.api") as mock_api,
            patch("agent_gateway.livekit_worker.LiveKitAudioAdapter", return_value=mock_adapter),
            patch(
                "agent_gateway.livekit_worker.LiveKitAudioPublisher", return_value=mock_publisher
            ),
        ):
            mock_rtc.Room.return_value = mock_room
            mock_api.AccessToken.return_value = token_builder

            await worker.connect()

        mock_api.AccessToken.assert_called_once_with(_LK_KEY, _LK_SECRET)
        token_builder.with_identity.assert_called_once_with(f"kutana-gateway-{meeting_id}")

        # VideoGrants is constructed with the correct kwargs.
        mock_api.VideoGrants.assert_called_once_with(
            room_join=True,
            room=_LK_ROOM,
            can_subscribe=True,
            can_publish=True,
        )

    async def test_connect_skips_adapter_when_no_pipeline(self, worker, mock_bridge) -> None:
        """connect() skips adapter creation when AudioBridge returns None pipeline."""
        mock_room = AsyncMock()
        mock_publisher = AsyncMock()
        mock_bridge.get_pipeline.return_value = None

        with (
            patch("agent_gateway.livekit_worker.rtc") as mock_rtc,
            patch("agent_gateway.livekit_worker.api") as mock_api,
            patch(
                "agent_gateway.livekit_worker.LiveKitAudioAdapter",
            ) as mock_adapter_cls,
            patch(
                "agent_gateway.livekit_worker.LiveKitAudioPublisher",
                return_value=mock_publisher,
            ),
        ):
            mock_rtc.Room.return_value = mock_room
            mock_api.AccessToken.return_value = _make_token_builder()

            await worker.connect()

        mock_adapter_cls.assert_not_called()
        mock_publisher.start.assert_awaited_once()


class TestDisconnect:
    """Tests for LiveKitAgentWorker.disconnect()."""

    async def _connected_worker(self, worker, mock_bridge):
        """Helper: connect the worker with mocked dependencies."""
        mock_room = AsyncMock()
        mock_adapter = AsyncMock()
        mock_publisher = AsyncMock()
        mock_bridge.get_pipeline.return_value = MagicMock()

        with (
            patch("agent_gateway.livekit_worker.rtc") as mock_rtc,
            patch("agent_gateway.livekit_worker.api") as mock_api,
            patch(
                "agent_gateway.livekit_worker.LiveKitAudioAdapter",
                return_value=mock_adapter,
            ),
            patch(
                "agent_gateway.livekit_worker.LiveKitAudioPublisher",
                return_value=mock_publisher,
            ),
        ):
            mock_rtc.Room.return_value = mock_room
            mock_api.AccessToken.return_value = _make_token_builder()
            await worker.connect()

        return mock_room, mock_adapter, mock_publisher

    async def test_disconnect_stops_adapter_publisher_and_room(self, worker, mock_bridge) -> None:
        """disconnect() calls stop() on adapter and publisher, then disconnects room."""
        mock_room, mock_adapter, mock_publisher = await self._connected_worker(worker, mock_bridge)

        await worker.disconnect()

        mock_adapter.stop.assert_awaited_once()
        mock_publisher.stop.assert_awaited_once()
        mock_room.disconnect.assert_awaited_once()

    async def test_disconnect_graceful_on_error(self, worker, mock_bridge) -> None:
        """disconnect() completes teardown even if adapter.stop() raises."""
        mock_room = AsyncMock()
        mock_adapter = AsyncMock()
        mock_publisher = AsyncMock()
        mock_adapter.stop.side_effect = RuntimeError("adapter exploded")
        mock_bridge.get_pipeline.return_value = MagicMock()

        with (
            patch("agent_gateway.livekit_worker.rtc") as mock_rtc,
            patch("agent_gateway.livekit_worker.api") as mock_api,
            patch(
                "agent_gateway.livekit_worker.LiveKitAudioAdapter",
                return_value=mock_adapter,
            ),
            patch(
                "agent_gateway.livekit_worker.LiveKitAudioPublisher",
                return_value=mock_publisher,
            ),
        ):
            mock_rtc.Room.return_value = mock_room
            mock_api.AccessToken.return_value = _make_token_builder()
            await worker.connect()

        # Must not raise despite adapter error
        await worker.disconnect()

        # Publisher and room teardown still complete after adapter failure
        mock_publisher.stop.assert_awaited_once()
        mock_room.disconnect.assert_awaited_once()


class TestProperties:
    """Tests for LiveKitAgentWorker properties."""

    def test_is_connected_false_before_connect(self, worker) -> None:
        assert worker.is_connected is False

    async def test_is_connected_true_after_connect(self, worker, mock_bridge) -> None:
        with (
            patch("agent_gateway.livekit_worker.rtc") as mock_rtc,
            patch("agent_gateway.livekit_worker.api") as mock_api,
            patch("agent_gateway.livekit_worker.LiveKitAudioAdapter", return_value=AsyncMock()),
            patch("agent_gateway.livekit_worker.LiveKitAudioPublisher", return_value=AsyncMock()),
        ):
            mock_rtc.Room.return_value = AsyncMock()
            mock_api.AccessToken.return_value = _make_token_builder()
            mock_bridge.get_pipeline.return_value = MagicMock()
            await worker.connect()

        assert worker.is_connected is True

    async def test_is_connected_false_after_disconnect(self, worker, mock_bridge) -> None:
        with (
            patch("agent_gateway.livekit_worker.rtc") as mock_rtc,
            patch("agent_gateway.livekit_worker.api") as mock_api,
            patch("agent_gateway.livekit_worker.LiveKitAudioAdapter", return_value=AsyncMock()),
            patch("agent_gateway.livekit_worker.LiveKitAudioPublisher", return_value=AsyncMock()),
        ):
            mock_rtc.Room.return_value = AsyncMock()
            mock_api.AccessToken.return_value = _make_token_builder()
            mock_bridge.get_pipeline.return_value = MagicMock()
            await worker.connect()
            await worker.disconnect()

        assert worker.is_connected is False

    def test_publisher_none_before_connect(self, worker) -> None:
        assert worker.publisher is None

    async def test_publisher_set_after_connect(self, worker, mock_bridge) -> None:
        mock_publisher = AsyncMock()

        with (
            patch("agent_gateway.livekit_worker.rtc") as mock_rtc,
            patch("agent_gateway.livekit_worker.api") as mock_api,
            patch("agent_gateway.livekit_worker.LiveKitAudioAdapter", return_value=AsyncMock()),
            patch(
                "agent_gateway.livekit_worker.LiveKitAudioPublisher",
                return_value=mock_publisher,
            ),
        ):
            mock_rtc.Room.return_value = AsyncMock()
            mock_api.AccessToken.return_value = _make_token_builder()
            mock_bridge.get_pipeline.return_value = MagicMock()
            await worker.connect()

        assert worker.publisher is mock_publisher
