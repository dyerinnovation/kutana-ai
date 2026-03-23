"""Unit tests for AudioRouter — mixed-minus routing and VAD."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from agent_gateway.audio_router import AudioRouter


def _make_handler(session_id=None, participant_id=None):
    """Create a mock AudioSessionHandler."""
    handler = MagicMock()
    handler.session_id = session_id or uuid4()
    handler.participant_id = participant_id or str(uuid4())
    handler.is_speaking = False
    handler.receive_audio = AsyncMock()
    handler.send_speaker_changed = AsyncMock()
    handler.on_vad_silence_timeout = AsyncMock()
    return handler


class TestAudioRouterSessionManagement:
    """Tests for session add/remove and is_empty."""

    def test_initially_empty(self) -> None:
        meeting_id = uuid4()
        router = AudioRouter(meeting_id=meeting_id)
        assert router.is_empty

    def test_add_session(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        h = _make_handler()
        router.add_session(h.session_id, h, participant_id=h.participant_id)
        assert not router.is_empty

    def test_remove_session(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        h = _make_handler()
        router.add_session(h.session_id, h, participant_id=h.participant_id)
        router.remove_session(h.session_id)
        assert router.is_empty

    def test_remove_nonexistent_session_is_noop(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        router.remove_session(uuid4())  # Should not raise

    def test_remove_clears_speaking_state(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        h = _make_handler()
        router.add_session(h.session_id, h, participant_id=h.participant_id)
        router.set_speaking(h.session_id, speaking=True)
        router.remove_session(h.session_id)
        # Active speakers dict should no longer contain the session
        assert h.session_id not in router._active_speakers


class TestAudioRouterSpeakingState:
    """Tests for set_speaking and update_audio_timestamp."""

    def test_set_speaking_true_enters_active_speakers(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        h = _make_handler()
        router.add_session(h.session_id, h, participant_id=h.participant_id)
        router.set_speaking(h.session_id, speaking=True)
        assert h.session_id in router._active_speakers

    def test_set_speaking_false_leaves_active_speakers(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        h = _make_handler()
        router.add_session(h.session_id, h, participant_id=h.participant_id)
        router.set_speaking(h.session_id, speaking=True)
        router.set_speaking(h.session_id, speaking=False)
        assert h.session_id not in router._active_speakers

    def test_update_audio_timestamp_refreshes_time(self) -> None:
        import time

        router = AudioRouter(meeting_id=uuid4())
        h = _make_handler()
        router.add_session(h.session_id, h, participant_id=h.participant_id)
        router.set_speaking(h.session_id, speaking=True)

        # Set an old timestamp
        router._active_speakers[h.session_id] = time.monotonic() - 5.0
        old_ts = router._active_speakers[h.session_id]

        router.update_audio_timestamp(h.session_id)
        assert router._active_speakers[h.session_id] > old_ts

    def test_update_audio_timestamp_noop_if_not_speaking(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        h = _make_handler()
        router.add_session(h.session_id, h, participant_id=h.participant_id)
        # session not speaking — should not raise
        router.update_audio_timestamp(h.session_id)


class TestAudioRouterRouteAudio:
    """Tests for route_audio (mixed-minus distribution)."""

    @pytest.mark.asyncio
    async def test_audio_not_routed_when_not_speaking(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        sender = _make_handler()
        receiver = _make_handler()
        router.add_session(sender.session_id, sender, participant_id=sender.participant_id)
        router.add_session(receiver.session_id, receiver, participant_id=receiver.participant_id)

        # sender is NOT speaking
        audio = b"\x00\x01" * 160
        await router.route_audio(sender.session_id, audio)

        receiver.receive_audio.assert_not_called()

    @pytest.mark.asyncio
    async def test_audio_routed_to_other_sessions(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        sender = _make_handler()
        receiver = _make_handler()
        router.add_session(sender.session_id, sender, participant_id=sender.participant_id)
        router.add_session(receiver.session_id, receiver, participant_id=receiver.participant_id)
        router.set_speaking(sender.session_id, speaking=True)

        audio = b"\x00\x01" * 160
        await router.route_audio(sender.session_id, audio)

        receiver.receive_audio.assert_called_once_with(
            audio_bytes=audio,
            speakers=[sender.participant_id],
        )

    @pytest.mark.asyncio
    async def test_mixed_minus_sender_does_not_receive_own_audio(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        sender = _make_handler()
        router.add_session(sender.session_id, sender, participant_id=sender.participant_id)
        router.set_speaking(sender.session_id, speaking=True)

        audio = b"\x00\x01" * 160
        await router.route_audio(sender.session_id, audio)

        sender.receive_audio.assert_not_called()

    @pytest.mark.asyncio
    async def test_audio_routed_to_multiple_receivers(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        sender = _make_handler()
        r1 = _make_handler()
        r2 = _make_handler()
        for h in (sender, r1, r2):
            router.add_session(h.session_id, h, participant_id=h.participant_id)
        router.set_speaking(sender.session_id, speaking=True)

        audio = b"\x01\x02" * 320
        await router.route_audio(sender.session_id, audio)

        r1.receive_audio.assert_called_once()
        r2.receive_audio.assert_called_once()
        sender.receive_audio.assert_not_called()

    @pytest.mark.asyncio
    async def test_route_audio_updates_vad_timestamp(self) -> None:
        import time

        router = AudioRouter(meeting_id=uuid4())
        sender = _make_handler()
        router.add_session(sender.session_id, sender, participant_id=sender.participant_id)
        router.set_speaking(sender.session_id, speaking=True)

        # Set old timestamp
        router._active_speakers[sender.session_id] = time.monotonic() - 5.0
        old_ts = router._active_speakers[sender.session_id]

        await router.route_audio(sender.session_id, b"\x00" * 32)
        assert router._active_speakers[sender.session_id] > old_ts


class TestAudioRouterBroadcastSpeakerChanged:
    """Tests for broadcast_speaker_changed."""

    @pytest.mark.asyncio
    async def test_broadcast_reaches_all_sessions(self) -> None:
        router = AudioRouter(meeting_id=uuid4())
        h1 = _make_handler()
        h2 = _make_handler()
        h3 = _make_handler()
        for h in (h1, h2, h3):
            router.add_session(h.session_id, h, participant_id=h.participant_id)

        await router.broadcast_speaker_changed(
            source_session_id=h1.session_id,
            participant_id=h1.participant_id,
            action="started",
        )

        for h in (h1, h2, h3):
            h.send_speaker_changed.assert_called_once_with(
                participant_id=h1.participant_id,
                action="started",
            )


class TestAudioRouterVAD:
    """Tests for VAD silence detection."""

    @pytest.mark.asyncio
    async def test_vad_auto_stops_silent_speaker(self) -> None:
        import time

        router = AudioRouter(meeting_id=uuid4(), vad_timeout_s=1)
        h = _make_handler()
        router.add_session(h.session_id, h, participant_id=h.participant_id)
        router.set_speaking(h.session_id, speaking=True)

        # Set timestamp to well in the past (simulating silence)
        router._active_speakers[h.session_id] = time.monotonic() - 10.0

        await router._check_vad()

        # Speaker should be removed from active_speakers
        assert h.session_id not in router._active_speakers
        # on_vad_silence_timeout callback should have been called
        h.on_vad_silence_timeout.assert_called_once()
        # speaker_changed(stopped) should be broadcast
        h.send_speaker_changed.assert_called_once_with(
            participant_id=h.participant_id,
            action="stopped",
        )

    @pytest.mark.asyncio
    async def test_vad_does_not_stop_recent_speaker(self) -> None:
        import time

        router = AudioRouter(meeting_id=uuid4(), vad_timeout_s=10)
        h = _make_handler()
        router.add_session(h.session_id, h, participant_id=h.participant_id)
        router.set_speaking(h.session_id, speaking=True)
        # Timestamp is recent (1 second ago, timeout is 10s)
        router._active_speakers[h.session_id] = time.monotonic() - 1.0

        await router._check_vad()

        assert h.session_id in router._active_speakers
        h.on_vad_silence_timeout.assert_not_called()

    @pytest.mark.asyncio
    async def test_vad_task_starts_and_stops(self) -> None:
        router = AudioRouter(meeting_id=uuid4(), vad_timeout_s=5)
        router.start()
        assert router._vad_task is not None
        assert not router._vad_task.done()

        await router.stop()
        assert router._vad_task is None
