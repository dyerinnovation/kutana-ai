"""Integration tests for ConnectionManager + LiveKitAgentWorker.

Tests the ensure_livekit_worker / cleanup_livekit_worker pattern added to
ConnectionManager in the LiveKit Phase 1 wiring task.  These tests patch out
LiveKitAgentWorker so no real LiveKit server is needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from agent_gateway.connection_manager import ConnectionManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_worker() -> MagicMock:
    """Return a mock LiveKitAgentWorker."""
    worker = MagicMock()
    worker.connect = AsyncMock()
    worker.disconnect = AsyncMock()
    worker.is_connected = False
    return worker


def _make_session(meeting_id=None):
    """Return a mock session handler."""
    session = MagicMock()
    session.session_id = uuid4()
    session.agent_name = "test-agent"
    session.meeting_id = meeting_id
    session.capabilities = []
    return session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def manager():
    return ConnectionManager(max_connections=100)


@pytest.fixture
def mock_audio_bridge():
    return MagicMock()


_LK_KWARGS = {
    "livekit_room_name": "test-room",
    "livekit_url": "ws://livekit:7880",
    "livekit_api_key": "api-key",
    "livekit_api_secret": "api-secret",
}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestEnsureLiveKitWorker:
    """Tests for ConnectionManager.ensure_livekit_worker()."""

    async def test_ensure_livekit_worker_creates_on_first_call(
        self, manager, mock_audio_bridge
    ) -> None:
        """First call creates a LiveKitAgentWorker and calls connect()."""
        meeting_id = uuid4()
        mock_worker = _make_mock_worker()

        with patch(
            "agent_gateway.connection_manager.LiveKitAgentWorker",
            return_value=mock_worker,
        ):
            worker = await manager.ensure_livekit_worker(
                meeting_id=meeting_id,
                audio_bridge=mock_audio_bridge,
                **_LK_KWARGS,
            )

        assert worker is mock_worker
        mock_worker.connect.assert_awaited_once()

    async def test_ensure_livekit_worker_returns_existing(self, manager, mock_audio_bridge) -> None:
        """Second call with the same meeting_id returns the existing worker."""
        meeting_id = uuid4()
        mock_worker = _make_mock_worker()

        with patch(
            "agent_gateway.connection_manager.LiveKitAgentWorker",
            return_value=mock_worker,
        ) as mock_worker_cls:
            await manager.ensure_livekit_worker(
                meeting_id=meeting_id,
                audio_bridge=mock_audio_bridge,
                **_LK_KWARGS,
            )
            second = await manager.ensure_livekit_worker(
                meeting_id=meeting_id,
                audio_bridge=mock_audio_bridge,
                **_LK_KWARGS,
            )

        assert second is mock_worker
        # Worker class instantiated only once
        mock_worker_cls.assert_called_once()
        # connect() called only once
        mock_worker.connect.assert_awaited_once()


class TestCleanupLiveKitWorker:
    """Tests for ConnectionManager.cleanup_livekit_worker()."""

    async def test_cleanup_livekit_worker_disconnects_when_empty(
        self, manager, mock_audio_bridge
    ) -> None:
        """Worker is disconnected and removed when no sessions remain in the meeting."""
        meeting_id = uuid4()
        mock_worker = _make_mock_worker()

        with patch(
            "agent_gateway.connection_manager.LiveKitAgentWorker",
            return_value=mock_worker,
        ):
            await manager.ensure_livekit_worker(
                meeting_id=meeting_id,
                audio_bridge=mock_audio_bridge,
                **_LK_KWARGS,
            )
            # No sessions in the meeting — cleanup should disconnect
            await manager.cleanup_livekit_worker(meeting_id)

        mock_worker.disconnect.assert_awaited_once()
        assert meeting_id not in manager._livekit_workers

    async def test_cleanup_livekit_worker_keeps_when_sessions_remain(
        self, manager, mock_audio_bridge
    ) -> None:
        """Worker stays connected while at least one session is in the meeting."""
        meeting_id = uuid4()
        mock_worker = _make_mock_worker()
        session = _make_session(meeting_id=meeting_id)

        with patch(
            "agent_gateway.connection_manager.LiveKitAgentWorker",
            return_value=mock_worker,
        ):
            await manager.ensure_livekit_worker(
                meeting_id=meeting_id,
                audio_bridge=mock_audio_bridge,
                **_LK_KWARGS,
            )
            manager.register(session)
            manager.join_meeting(session.session_id, meeting_id)

            await manager.cleanup_livekit_worker(meeting_id)

        mock_worker.disconnect.assert_not_called()
        assert meeting_id in manager._livekit_workers

    async def test_cleanup_livekit_worker_noop_when_no_worker(self, manager) -> None:
        """cleanup_livekit_worker is a no-op when no worker exists for the meeting."""
        meeting_id = uuid4()
        # Must not raise
        await manager.cleanup_livekit_worker(meeting_id)
