"""Integration tests for the voice agent audio sidecar.

Tests the AudioSessionHandler silence-padded streaming, mixed-minus
distribution, and the /v1/audio/{session_id} WebSocket endpoint.
"""

from __future__ import annotations

import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from agent_gateway.audio_session import (
    _FRAME_INTERVAL_S,
    _OUTBOUND_QUEUE_MAX,
    _SILENCE_FRAME_BYTES,
    AudioSessionHandler,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_MEETING_ID = uuid4()
_AGENT_CONFIG_ID = uuid4()


def _make_identity() -> MagicMock:
    """Create a mock AgentIdentity."""
    identity = MagicMock()
    identity.agent_config_id = _AGENT_CONFIG_ID
    identity.name = "VoiceAgent"
    identity.source = "agent"
    identity.capabilities = ["listen", "transcribe", "voice"]
    return identity


def _make_websocket() -> AsyncMock:
    """Create a mock WebSocket that captures sent messages."""
    ws = AsyncMock()
    ws.send_json = AsyncMock()
    ws.receive_text = AsyncMock(side_effect=asyncio.CancelledError)
    return ws


def _make_router() -> MagicMock:
    """Create a mock AudioRouter."""
    router = MagicMock()
    router.add_session = MagicMock()
    router.remove_session = MagicMock()
    router.set_speaking = MagicMock()
    router.route_audio = AsyncMock()
    router.broadcast_speaker_changed = AsyncMock()
    return router


def _make_handler(
    ws: AsyncMock | None = None,
    router: MagicMock | None = None,
) -> tuple[AudioSessionHandler, AsyncMock, MagicMock]:
    """Create an AudioSessionHandler with mocked dependencies.

    Returns:
        Tuple of (handler, mock_websocket, mock_router).
    """
    ws = ws or _make_websocket()
    router = router or _make_router()
    identity = _make_identity()
    handler = AudioSessionHandler(
        websocket=ws,
        identity=identity,
        meeting_id=_MEETING_ID,
        audio_router=router,
        audio_format="pcm16",
    )
    return handler, ws, router


# ---------------------------------------------------------------------------
# Tests: Silence-padded streaming
# ---------------------------------------------------------------------------


class TestSilencePadding:
    """Tests that continuous 20ms silence frames are sent when no audio arrives."""

    @pytest.mark.asyncio
    async def test_silence_clock_sends_frames(self) -> None:
        """Silence clock enqueues silence frames every 20ms tick."""
        handler, _ws, _router = _make_handler()

        # Run silence clock for a few ticks
        task = asyncio.create_task(handler._silence_clock())
        await asyncio.sleep(_FRAME_INTERVAL_S * 3.5)
        task.cancel()
        # _silence_clock catches CancelledError internally, so await completes normally
        await task

        # Should have enqueued at least 2 silence frames
        count = 0
        while not handler._outbound_queue.empty():
            msg = handler._outbound_queue.get_nowait()
            if msg["type"] == "mixed_audio":
                assert msg["speakers"] == []
                audio_bytes = base64.b64decode(msg["data"])
                assert audio_bytes == _SILENCE_FRAME_BYTES
                count += 1
        assert count >= 2

    @pytest.mark.asyncio
    async def test_silence_suppressed_when_audio_received(self) -> None:
        """Silence clock skips frames when real audio was received that tick."""
        handler, _ws, _router = _make_handler()

        # Simulate receiving audio every tick
        async def keep_receiving() -> None:
            for _ in range(5):
                handler._received_audio_this_tick = True
                await asyncio.sleep(_FRAME_INTERVAL_S)

        task = asyncio.create_task(handler._silence_clock())
        recv_task = asyncio.create_task(keep_receiving())
        await recv_task
        task.cancel()
        await task

        # Queue should be empty or near-empty (no silence frames)
        count = 0
        while not handler._outbound_queue.empty():
            msg = handler._outbound_queue.get_nowait()
            if msg["type"] == "mixed_audio" and msg["speakers"] == []:
                count += 1
        # At most 1 (timing edge), but not the full 5
        assert count <= 1

    @pytest.mark.asyncio
    async def test_receive_audio_sets_flag(self) -> None:
        """receive_audio() sets _received_audio_this_tick flag."""
        handler, _ws, _router = _make_handler()
        assert not handler._received_audio_this_tick

        await handler.receive_audio(b"\x00" * 640, ["speaker-1"])
        assert handler._received_audio_this_tick

    @pytest.mark.asyncio
    async def test_receive_audio_enqueues_mixed_audio(self) -> None:
        """receive_audio() enqueues a mixed_audio frame with speakers."""
        handler, _ws, _router = _make_handler()

        audio = b"\x01\x02" * 320
        await handler.receive_audio(audio, ["agent-1", "agent-2"])

        msg = handler._outbound_queue.get_nowait()
        assert msg["type"] == "mixed_audio"
        assert base64.b64decode(msg["data"]) == audio
        assert msg["speakers"] == ["agent-1", "agent-2"]


# ---------------------------------------------------------------------------
# Tests: Session lifecycle
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    """Tests for session registration, speaking state, and cleanup."""

    @pytest.mark.asyncio
    async def test_session_registers_with_router(self) -> None:
        """handle() registers the session with the audio router."""
        handler, ws, router = _make_handler()

        # Make inbound loop exit immediately
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await handler.handle()

        router.add_session.assert_called_once_with(
            session_id=handler.session_id,
            handler=handler,
            participant_id=str(_AGENT_CONFIG_ID),
        )

    @pytest.mark.asyncio
    async def test_session_sends_joined_on_connect(self) -> None:
        """handle() sends audio_session_joined immediately."""
        handler, ws, _router = _make_handler()
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await handler.handle()

        # First send_json call should be audio_session_joined
        first_call = ws.send_json.call_args_list[0][0][0]
        assert first_call["type"] == "audio_session_joined"
        assert first_call["format"] == "pcm16"

    @pytest.mark.asyncio
    async def test_cleanup_removes_session_from_router(self) -> None:
        """Cleanup removes session from router."""
        handler, ws, router = _make_handler()
        ws.receive_text = AsyncMock(side_effect=Exception("disconnect"))

        await handler.handle()

        router.remove_session.assert_called_once_with(handler.session_id)

    @pytest.mark.asyncio
    async def test_cleanup_broadcasts_stop_if_speaking(self) -> None:
        """Cleanup broadcasts stop_speaking if agent was speaking."""
        handler, _ws, router = _make_handler()
        handler.is_speaking = True

        await handler._cleanup()

        router.set_speaking.assert_called_once_with(handler.session_id, speaking=False)
        router.broadcast_speaker_changed.assert_called_once_with(
            source_session_id=handler.session_id,
            participant_id=str(_AGENT_CONFIG_ID),
            action="stopped",
        )


# ---------------------------------------------------------------------------
# Tests: Message dispatch
# ---------------------------------------------------------------------------


class TestMessageDispatch:
    """Tests for inbound message handling."""

    @pytest.mark.asyncio
    async def test_start_speaking_sets_flag_and_broadcasts(self) -> None:
        """start_speaking message sets is_speaking and broadcasts."""
        handler, _ws, router = _make_handler()

        await handler._handle_start_speaking()

        assert handler.is_speaking
        router.set_speaking.assert_called_once_with(handler.session_id, speaking=True)
        router.broadcast_speaker_changed.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_speaking_clears_flag_and_broadcasts(self) -> None:
        """stop_speaking message clears is_speaking and broadcasts."""
        handler, _ws, router = _make_handler()
        handler.is_speaking = True

        await handler._handle_stop_speaking()

        assert not handler.is_speaking
        router.set_speaking.assert_called_once_with(handler.session_id, speaking=False)

    @pytest.mark.asyncio
    async def test_audio_data_dropped_when_not_speaking(self) -> None:
        """audio_data frames are silently dropped if not speaking."""
        handler, _ws, router = _make_handler()
        handler.is_speaking = False

        audio_b64 = base64.b64encode(b"\x00" * 640).decode()
        await handler._handle_audio_data({"type": "audio_data", "data": audio_b64})

        router.route_audio.assert_not_called()

    @pytest.mark.asyncio
    async def test_audio_data_routed_when_speaking(self) -> None:
        """audio_data frames are forwarded to router when speaking."""
        handler, _ws, router = _make_handler()
        handler.is_speaking = True

        raw_audio = b"\x01\x02" * 320
        audio_b64 = base64.b64encode(raw_audio).decode()
        await handler._handle_audio_data({"type": "audio_data", "data": audio_b64})

        router.route_audio.assert_called_once_with(handler.session_id, raw_audio)

    @pytest.mark.asyncio
    async def test_ping_pong(self) -> None:
        """ping message enqueues a pong response."""
        handler, _ws, _router = _make_handler()

        await handler._dispatch({"type": "ping"})

        msg = handler._outbound_queue.get_nowait()
        assert msg["type"] == "pong"

    @pytest.mark.asyncio
    async def test_unknown_type_sends_error(self) -> None:
        """Unknown message type enqueues an error."""
        handler, _ws, _router = _make_handler()

        await handler._dispatch({"type": "bogus"})

        msg = handler._outbound_queue.get_nowait()
        assert msg["type"] == "error"
        assert msg["code"] == "unknown_type"


# ---------------------------------------------------------------------------
# Tests: VAD silence timeout callback
# ---------------------------------------------------------------------------


class TestVADCallback:
    """Tests for the on_vad_silence_timeout callback."""

    @pytest.mark.asyncio
    async def test_vad_timeout_clears_speaking(self) -> None:
        """VAD silence timeout clears is_speaking without broadcasting."""
        handler, _ws, router = _make_handler()
        handler.is_speaking = True

        await handler.on_vad_silence_timeout()

        assert not handler.is_speaking
        # Router handles its own broadcast — handler should NOT broadcast
        router.broadcast_speaker_changed.assert_not_called()

    @pytest.mark.asyncio
    async def test_vad_timeout_noop_when_not_speaking(self) -> None:
        """VAD silence timeout is no-op if not speaking."""
        handler, _ws, _router = _make_handler()
        handler.is_speaking = False

        await handler.on_vad_silence_timeout()
        assert not handler.is_speaking


# ---------------------------------------------------------------------------
# Tests: speaker_changed callback
# ---------------------------------------------------------------------------


class TestSpeakerChanged:
    """Tests for the send_speaker_changed callback."""

    @pytest.mark.asyncio
    async def test_speaker_changed_enqueued(self) -> None:
        """send_speaker_changed enqueues a speaker_changed message."""
        handler, _ws, _router = _make_handler()

        await handler.send_speaker_changed("agent-2", "started")

        msg = handler._outbound_queue.get_nowait()
        assert msg["type"] == "speaker_changed"
        assert msg["participant_id"] == "agent-2"
        assert msg["action"] == "started"


# ---------------------------------------------------------------------------
# Tests: Outbound queue backpressure
# ---------------------------------------------------------------------------


class TestBackpressure:
    """Tests for outbound queue overflow handling."""

    @pytest.mark.asyncio
    async def test_queue_full_drops_frame(self) -> None:
        """Frames are silently dropped when outbound queue is full."""
        handler, _ws, _router = _make_handler()

        # Fill the queue
        for i in range(_OUTBOUND_QUEUE_MAX):
            handler._enqueue_nowait({"type": "filler", "idx": i})

        assert handler._outbound_queue.full()

        # This should not raise
        handler._enqueue_nowait({"type": "dropped"})

        # Queue size should still be at max
        assert handler._outbound_queue.qsize() == _OUTBOUND_QUEUE_MAX


# ---------------------------------------------------------------------------
# Tests: Constants
# ---------------------------------------------------------------------------


class TestConstants:
    """Verify audio constants are correct for PCM16 16kHz mono."""

    def test_silence_frame_size(self) -> None:
        """Silence frame is 640 bytes (16kHz * 2 bytes * 20ms)."""
        assert len(_SILENCE_FRAME_BYTES) == 640

    def test_silence_frame_is_zeros(self) -> None:
        """Silence frame is all zero bytes."""
        assert _SILENCE_FRAME_BYTES == b"\x00" * 640

    def test_frame_interval(self) -> None:
        """Frame interval is 20ms."""
        assert _FRAME_INTERVAL_S == 0.020
