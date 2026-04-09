"""Unit tests for AudioSessionHandler."""

from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from agent_gateway.audio_session import AudioSessionHandler
from agent_gateway.auth import AgentIdentity


def _make_identity(
    agent_config_id=None,
    name="test-agent",
    capabilities=None,
) -> AgentIdentity:
    return AgentIdentity(
        agent_config_id=agent_config_id or uuid4(),
        name=name,
        capabilities=capabilities or ["voice"],
    )


def _make_router(meeting_id=None):
    """Create a mock AudioRouter."""
    router = MagicMock()
    router.meeting_id = meeting_id or uuid4()
    router.add_session = MagicMock()
    router.remove_session = MagicMock()
    router.set_speaking = MagicMock()
    router.route_audio = AsyncMock()
    router.broadcast_speaker_changed = AsyncMock()
    return router


def _make_websocket(messages: list[str] | None = None):
    """Create a mock WebSocket that returns the given text messages then raises."""
    ws = MagicMock()
    ws.send_json = AsyncMock()

    # Build a side_effect that returns messages then raises WebSocketDisconnect
    from fastapi import WebSocketDisconnect

    responses = list(messages or [])
    responses.append(None)  # sentinel — raise after messages

    call_count = [0]

    async def receive_text():
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(responses) - 1:
            return responses[idx]
        raise WebSocketDisconnect(code=1000)

    ws.receive_text = receive_text
    return ws


class TestAudioSessionJoined:
    """Test the audio_session_joined confirmation message."""

    @pytest.mark.asyncio
    async def test_sends_audio_session_joined_on_connect(self) -> None:
        identity = _make_identity()
        router = _make_router()
        meeting_id = uuid4()
        ws = _make_websocket()

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=meeting_id,
            audio_router=router,
        )
        await session.handle()

        # First send_json call should be the audio_session_joined confirmation
        first_call_args = ws.send_json.call_args_list[0][0][0]
        assert first_call_args["type"] == "audio_session_joined"
        assert first_call_args["meeting_id"] == str(meeting_id)
        assert first_call_args["format"] == "pcm16"

    @pytest.mark.asyncio
    async def test_registers_with_router_on_connect(self) -> None:
        identity = _make_identity()
        router = _make_router()
        meeting_id = uuid4()
        ws = _make_websocket()

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=meeting_id,
            audio_router=router,
        )
        await session.handle()

        router.add_session.assert_called_once_with(
            session_id=session.session_id,
            handler=session,
            participant_id=str(identity.agent_config_id),
        )

    @pytest.mark.asyncio
    async def test_unregisters_with_router_on_disconnect(self) -> None:
        identity = _make_identity()
        router = _make_router()
        ws = _make_websocket()

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        await session.handle()

        router.remove_session.assert_called_once_with(session.session_id)


class TestAudioSessionStartStopSpeaking:
    """Tests for start_speaking / stop_speaking messages."""

    @pytest.mark.asyncio
    async def test_start_speaking_sets_speaking_state(self) -> None:
        identity = _make_identity()
        router = _make_router()
        ws = _make_websocket([json.dumps({"type": "start_speaking"})])

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        await session.handle()

        router.set_speaking.assert_any_call(session.session_id, speaking=True)
        router.broadcast_speaker_changed.assert_any_call(
            source_session_id=session.session_id,
            participant_id=str(identity.agent_config_id),
            action="started",
        )

    @pytest.mark.asyncio
    async def test_stop_speaking_clears_speaking_state(self) -> None:
        identity = _make_identity()
        router = _make_router()
        messages = [
            json.dumps({"type": "start_speaking"}),
            json.dumps({"type": "stop_speaking"}),
        ]
        ws = _make_websocket(messages)

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        await session.handle()

        router.set_speaking.assert_any_call(session.session_id, speaking=False)
        router.broadcast_speaker_changed.assert_any_call(
            source_session_id=session.session_id,
            participant_id=str(identity.agent_config_id),
            action="stopped",
        )

    @pytest.mark.asyncio
    async def test_start_speaking_idempotent(self) -> None:
        identity = _make_identity()
        router = _make_router()
        messages = [
            json.dumps({"type": "start_speaking"}),
            json.dumps({"type": "start_speaking"}),  # duplicate
        ]
        ws = _make_websocket(messages)

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        await session.handle()

        # set_speaking(speaking=True) should only be called once
        speaking_true_calls = [
            c for c in router.set_speaking.call_args_list if c.kwargs.get("speaking") is True
        ]
        assert len(speaking_true_calls) == 1

    @pytest.mark.asyncio
    async def test_cleanup_sends_stopped_if_still_speaking(self) -> None:
        identity = _make_identity()
        router = _make_router()
        ws = _make_websocket([json.dumps({"type": "start_speaking"})])

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        await session.handle()

        # On disconnect while speaking, _cleanup should broadcast "stopped"
        stopped_calls = [
            c
            for c in router.broadcast_speaker_changed.call_args_list
            if c.kwargs.get("action") == "stopped"
        ]
        assert len(stopped_calls) >= 1


class TestAudioSessionAudioData:
    """Tests for audio_data message handling."""

    @pytest.mark.asyncio
    async def test_audio_data_dropped_when_not_speaking(self) -> None:
        identity = _make_identity()
        router = _make_router()
        audio_b64 = base64.b64encode(b"\x00\x01" * 160).decode()
        ws = _make_websocket([json.dumps({"type": "audio_data", "data": audio_b64})])

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        await session.handle()

        router.route_audio.assert_not_called()

    @pytest.mark.asyncio
    async def test_audio_data_routed_when_speaking(self) -> None:
        identity = _make_identity()
        router = _make_router()
        audio_bytes = b"\x00\x01" * 160
        audio_b64 = base64.b64encode(audio_bytes).decode()
        messages = [
            json.dumps({"type": "start_speaking"}),
            json.dumps({"type": "audio_data", "data": audio_b64}),
        ]
        ws = _make_websocket(messages)

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        await session.handle()

        router.route_audio.assert_called_once_with(session.session_id, audio_bytes)

    @pytest.mark.asyncio
    async def test_invalid_base64_sends_error(self) -> None:
        identity = _make_identity()
        router = _make_router()
        messages = [
            json.dumps({"type": "start_speaking"}),
            json.dumps({"type": "audio_data", "data": "not-valid-base64!!!"}),
        ]
        ws = _make_websocket(messages)

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        await session.handle()

        # Should have sent an error message through the outbound queue / send_json
        error_calls = [
            call for call in ws.send_json.call_args_list if call[0][0].get("type") == "error"
        ]
        assert len(error_calls) >= 1


class TestAudioSessionPing:
    """Tests for ping/pong."""

    @pytest.mark.asyncio
    async def test_ping_receives_pong(self) -> None:
        identity = _make_identity()
        router = _make_router()
        ws = _make_websocket([json.dumps({"type": "ping"})])

        session = AudioSessionHandler(
            websocket=ws,
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        await session.handle()

        pong_calls = [c for c in ws.send_json.call_args_list if c[0][0].get("type") == "pong"]
        assert len(pong_calls) >= 1


class TestAudioSessionReceiveAudio:
    """Tests for the receive_audio callback (router → session)."""

    @pytest.mark.asyncio
    async def test_receive_audio_enqueues_mixed_audio(self) -> None:
        identity = _make_identity()
        router = _make_router()
        meeting_id = uuid4()

        session = AudioSessionHandler(
            websocket=MagicMock(),
            identity=identity,
            meeting_id=meeting_id,
            audio_router=router,
        )

        audio_bytes = b"\xaa\xbb" * 80
        speakers = ["participant-abc"]
        await session.receive_audio(audio_bytes=audio_bytes, speakers=speakers)

        # Message should be in the outbound queue
        assert not session._outbound_queue.empty()
        msg = session._outbound_queue.get_nowait()
        assert msg["type"] == "mixed_audio"
        assert msg["speakers"] == speakers
        decoded = base64.b64decode(msg["data"])
        assert decoded == audio_bytes


class TestAudioSessionSpeakerChanged:
    """Tests for the send_speaker_changed callback."""

    @pytest.mark.asyncio
    async def test_send_speaker_changed_enqueues_event(self) -> None:
        identity = _make_identity()
        router = _make_router()

        session = AudioSessionHandler(
            websocket=MagicMock(),
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )

        await session.send_speaker_changed(participant_id="p1", action="started")

        assert not session._outbound_queue.empty()
        msg = session._outbound_queue.get_nowait()
        assert msg["type"] == "speaker_changed"
        assert msg["participant_id"] == "p1"
        assert msg["action"] == "started"


class TestAudioSessionVADCallback:
    """Tests for on_vad_silence_timeout."""

    @pytest.mark.asyncio
    async def test_vad_timeout_clears_speaking_flag(self) -> None:
        identity = _make_identity()
        router = _make_router()

        session = AudioSessionHandler(
            websocket=MagicMock(),
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        session.is_speaking = True

        await session.on_vad_silence_timeout()

        assert not session.is_speaking

    @pytest.mark.asyncio
    async def test_vad_timeout_noop_when_not_speaking(self) -> None:
        identity = _make_identity()
        router = _make_router()

        session = AudioSessionHandler(
            websocket=MagicMock(),
            identity=identity,
            meeting_id=uuid4(),
            audio_router=router,
        )
        session.is_speaking = False

        await session.on_vad_silence_timeout()  # Should not raise
        assert not session.is_speaking


class TestCreateAudioToken:
    """Tests for the create_audio_token auth helper."""

    def test_creates_valid_jwt(self) -> None:
        import jwt as pyjwt
        from agent_gateway.auth import create_audio_token

        agent_id = uuid4()
        meeting_id = uuid4()
        secret = "test-audio-secret"

        token = create_audio_token(
            agent_config_id=agent_id,
            meeting_id=meeting_id,
            secret=secret,
        )

        payload = pyjwt.decode(token, secret, algorithms=["HS256"])
        assert payload["sub"] == str(agent_id)
        assert payload["meeting_id"] == str(meeting_id)
        assert payload["token_type"] == "audio"

    def test_default_expiry_is_5_minutes(self) -> None:
        import jwt as pyjwt
        from agent_gateway.auth import create_audio_token

        token = create_audio_token(
            agent_config_id=uuid4(),
            meeting_id=uuid4(),
            secret="s",
        )
        payload = pyjwt.decode(token, "s", algorithms=["HS256"])
        assert payload["exp"] - payload["iat"] == 300

    def test_control_session_id_included_when_provided(self) -> None:
        import jwt as pyjwt
        from agent_gateway.auth import create_audio_token

        control_id = uuid4()
        token = create_audio_token(
            agent_config_id=uuid4(),
            meeting_id=uuid4(),
            secret="s",
            control_session_id=control_id,
        )
        payload = pyjwt.decode(token, "s", algorithms=["HS256"])
        assert payload["control_session_id"] == str(control_id)

    def test_control_session_id_absent_when_not_provided(self) -> None:
        import jwt as pyjwt
        from agent_gateway.auth import create_audio_token

        token = create_audio_token(
            agent_config_id=uuid4(),
            meeting_id=uuid4(),
            secret="s",
        )
        payload = pyjwt.decode(token, "s", algorithms=["HS256"])
        assert "control_session_id" not in payload
