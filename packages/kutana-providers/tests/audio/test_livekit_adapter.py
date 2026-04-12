"""Unit tests for LiveKitAudioAdapter.

Uses unittest.mock to stand in for livekit.rtc so the tests run without
the optional livekit dependency installed.
"""

from __future__ import annotations

import array
import asyncio
import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Stub out livekit.rtc before importing the adapter so the module loads
# even when the livekit package is not installed in the test environment.
# ---------------------------------------------------------------------------


def _make_livekit_stub() -> ModuleType:
    """Return a minimal fake livekit.rtc module."""
    rtc = ModuleType("livekit.rtc")

    class TrackKind:
        KIND_AUDIO = "audio"
        KIND_VIDEO = "video"

    class AudioFrame:
        def __init__(
            self,
            data: bytes,
            sample_rate: int = 48_000,
            num_channels: int = 1,
            samples_per_channel: int = 0,
        ) -> None:
            self.data = memoryview(data)
            self.sample_rate = sample_rate
            self.num_channels = num_channels
            self.samples_per_channel = samples_per_channel

    class AudioFrameEvent:
        def __init__(self, frame: AudioFrame) -> None:
            self.frame = frame

    class Track:
        def __init__(self, kind: str = TrackKind.KIND_AUDIO) -> None:
            self.kind = kind

    class RemoteTrackPublication:
        def __init__(self, track: Track | None = None) -> None:
            self.track = track

    class RemoteParticipant:
        def __init__(self, identity: str = "test-user") -> None:
            self.identity = identity
            self.track_publications: dict[str, RemoteTrackPublication] = {}

    rtc.TrackKind = TrackKind  # type: ignore[attr-defined]
    rtc.AudioFrame = AudioFrame  # type: ignore[attr-defined]
    rtc.AudioFrameEvent = AudioFrameEvent  # type: ignore[attr-defined]
    rtc.Track = Track  # type: ignore[attr-defined]
    rtc.RemoteTrackPublication = RemoteTrackPublication  # type: ignore[attr-defined]
    rtc.RemoteParticipant = RemoteParticipant  # type: ignore[attr-defined]

    return rtc


_rtc_stub = _make_livekit_stub()
sys.modules.setdefault("livekit", ModuleType("livekit"))
sys.modules.setdefault("livekit.rtc", _rtc_stub)
# Also expose as attribute so `from livekit import rtc` works
sys.modules["livekit"].rtc = _rtc_stub  # type: ignore[attr-defined]


# Now import the adapter (livekit is mocked above; audio-service stub kicks in
# automatically when audio_service is not importable).
from kutana_providers.audio.livekit_adapter import LiveKitAudioAdapter  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_int16_bytes(samples: list[int]) -> bytes:
    """Pack a list of int16 values to bytes (little-endian)."""
    arr = array.array("h", samples)
    return arr.tobytes()


def _unpack_int16(data: bytes) -> list[int]:
    """Unpack bytes to a list of int16 values."""
    arr = array.array("h")
    arr.frombytes(data)
    return list(arr)


def _make_frame(samples: list[int], sample_rate: int = 48_000, num_channels: int = 1):
    raw = _make_int16_bytes(samples)
    return _rtc_stub.AudioFrame(  # type: ignore[attr-defined]
        data=raw,
        sample_rate=sample_rate,
        num_channels=num_channels,
        samples_per_channel=len(samples) // num_channels,
    )


def _make_room(participants: dict | None = None) -> MagicMock:
    room = MagicMock()
    room.remote_participants = participants or {}
    return room


def _make_pipeline() -> AsyncMock:
    pipeline = AsyncMock()
    pipeline.process_audio = AsyncMock()
    return pipeline


# ---------------------------------------------------------------------------
# _to_pcm16_16khz — resampling / downmix logic
# ---------------------------------------------------------------------------


class TestToPcm1616Khz:
    def _adapter(self, **kwargs):
        return LiveKitAudioAdapter(
            pipeline=_make_pipeline(),
            room=_make_room(),
            **kwargs,
        )

    def test_passthrough_16khz_mono(self):
        """16 kHz mono frames are returned unchanged."""
        adapter = self._adapter()
        samples = [100, 200, 300, 400]
        frame = _make_frame(samples, sample_rate=16_000, num_channels=1)
        result = _unpack_int16(adapter._to_pcm16_16khz(frame))
        assert result == samples

    def test_48khz_mono_decimation(self):
        """48 kHz mono → 16 kHz via 3:1 decimation (every third sample)."""
        adapter = self._adapter()
        # 9 samples; after 3:1 decimation expect indices 0, 3, 6
        samples = [10, 20, 30, 40, 50, 60, 70, 80, 90]
        frame = _make_frame(samples, sample_rate=48_000, num_channels=1)
        result = _unpack_int16(adapter._to_pcm16_16khz(frame))
        assert result == [10, 40, 70]

    def test_stereo_downmix_averages_channels(self):
        """Stereo frames are averaged to mono before any rate conversion."""
        adapter = self._adapter(target_sample_rate=16_000)
        # 4 stereo pairs → 4 mono samples; sample_rate=16kHz so no decimation
        # Pairs: (100, 200)→150, (300, 100)→200, (50, 50)→50, (1000, 0)→500
        samples = [100, 200, 300, 100, 50, 50, 1000, 0]
        frame = _make_frame(samples, sample_rate=16_000, num_channels=2)
        result = _unpack_int16(adapter._to_pcm16_16khz(frame))
        assert result == [150, 200, 50, 500]

    def test_48khz_stereo_downmix_then_decimate(self):
        """Stereo 48 kHz: average channels first, then decimate 3:1."""
        adapter = self._adapter()
        # 6 stereo pairs → 6 mono samples at 48 kHz → decimate 3:1 → 2 samples
        # Pairs: (0,100)→50, (200,0)→100, (300,300)→300,
        #        (400,600)→500, (100,100)→100, (0,200)→100
        # After decimate [::3]: [50, 500]
        samples = [0, 100, 200, 0, 300, 300, 400, 600, 100, 100, 0, 200]
        frame = _make_frame(samples, sample_rate=48_000, num_channels=2)
        result = _unpack_int16(adapter._to_pcm16_16khz(frame))
        assert result == [50, 500]

    def test_unsupported_rate_emits_warning_and_passthrough(self, caplog):
        """Unsupported sample rate passes samples through with a warning."""
        import logging

        adapter = self._adapter()
        samples = [1, 2, 3]
        frame = _make_frame(samples, sample_rate=22_050, num_channels=1)
        with caplog.at_level(logging.WARNING, logger="kutana_providers.audio.livekit_adapter"):
            result = _unpack_int16(adapter._to_pcm16_16khz(frame))
        assert result == samples
        assert "22050" in caplog.text

    def test_empty_frame_returns_empty_bytes(self):
        adapter = self._adapter()
        frame = _make_frame([], sample_rate=16_000, num_channels=1)
        assert adapter._to_pcm16_16khz(frame) == b""


# ---------------------------------------------------------------------------
# start() — event registration and existing participant wiring
# ---------------------------------------------------------------------------


class TestStart:
    @pytest.mark.asyncio
    async def test_registers_event_handlers(self):
        room = _make_room()
        adapter = LiveKitAudioAdapter(pipeline=_make_pipeline(), room=room)
        await adapter.start()
        room.on.assert_any_call("track_subscribed", adapter._on_track_subscribed_sync)
        room.on.assert_any_call(
            "participant_disconnected", adapter._on_participant_disconnected_sync
        )

    @pytest.mark.asyncio
    async def test_subscribes_to_existing_audio_tracks(self):
        """start() picks up audio tracks already published before start()."""
        track = _rtc_stub.Track(kind=_rtc_stub.TrackKind.KIND_AUDIO)  # type: ignore[attr-defined]
        publication = _rtc_stub.RemoteTrackPublication(track=track)  # type: ignore[attr-defined]
        participant = _rtc_stub.RemoteParticipant(identity="alice")  # type: ignore[attr-defined]
        participant.track_publications = {"t1": publication}

        room = _make_room(participants={"alice": participant})
        pipeline = _make_pipeline()
        adapter = LiveKitAudioAdapter(pipeline=pipeline, room=room)

        with patch.object(adapter, "_on_track_subscribed", new_callable=AsyncMock) as mock_handler:
            await adapter.start()
            mock_handler.assert_awaited_once_with(track, publication, participant)

    @pytest.mark.asyncio
    async def test_ignores_video_tracks_on_start(self):
        """start() does not spawn consumers for video tracks."""
        track = _rtc_stub.Track(kind=_rtc_stub.TrackKind.KIND_VIDEO)  # type: ignore[attr-defined]
        publication = _rtc_stub.RemoteTrackPublication(track=track)  # type: ignore[attr-defined]
        participant = _rtc_stub.RemoteParticipant(identity="bob")  # type: ignore[attr-defined]
        participant.track_publications = {"t1": publication}

        room = _make_room(participants={"bob": participant})
        adapter = LiveKitAudioAdapter(pipeline=_make_pipeline(), room=room)
        await adapter.start()
        assert len(adapter._consumers) == 0

    @pytest.mark.asyncio
    async def test_ignores_unresolved_publications_on_start(self):
        """start() skips publications whose .track is None."""
        publication = _rtc_stub.RemoteTrackPublication(track=None)  # type: ignore[attr-defined]
        participant = _rtc_stub.RemoteParticipant(identity="charlie")  # type: ignore[attr-defined]
        participant.track_publications = {"t1": publication}

        room = _make_room(participants={"charlie": participant})
        adapter = LiveKitAudioAdapter(pipeline=_make_pipeline(), room=room)
        await adapter.start()
        assert len(adapter._consumers) == 0


# ---------------------------------------------------------------------------
# stop() — task cancellation
# ---------------------------------------------------------------------------


class TestStop:
    @pytest.mark.asyncio
    async def test_stop_cancels_all_consumers(self):
        room = _make_room()
        adapter = LiveKitAudioAdapter(pipeline=_make_pipeline(), room=room)
        await adapter.start()

        # Manually inject fake consumer tasks.
        t1 = asyncio.ensure_future(asyncio.sleep(999))
        t2 = asyncio.ensure_future(asyncio.sleep(999))
        adapter._consumers = {"alice": t1, "bob": t2}

        await adapter.stop()

        assert t1.cancelled()
        assert t2.cancelled()
        assert len(adapter._consumers) == 0

    @pytest.mark.asyncio
    async def test_stop_deregisters_event_handlers(self):
        room = _make_room()
        adapter = LiveKitAudioAdapter(pipeline=_make_pipeline(), room=room)
        await adapter.start()
        await adapter.stop()
        room.off.assert_any_call("track_subscribed", adapter._on_track_subscribed_sync)
        room.off.assert_any_call(
            "participant_disconnected", adapter._on_participant_disconnected_sync
        )


# ---------------------------------------------------------------------------
# participant_disconnected — per-participant task cleanup
# ---------------------------------------------------------------------------


class TestParticipantDisconnected:
    def test_cancels_participant_task(self):
        room = _make_room()
        adapter = LiveKitAudioAdapter(pipeline=_make_pipeline(), room=room)

        task = MagicMock()
        adapter._consumers["alice"] = task

        participant = _rtc_stub.RemoteParticipant(identity="alice")  # type: ignore[attr-defined]
        adapter._on_participant_disconnected_sync(participant)

        task.cancel.assert_called_once()
        assert "alice" not in adapter._consumers

    def test_noop_for_unknown_participant(self):
        """Disconnecting an unknown participant does not raise."""
        room = _make_room()
        adapter = LiveKitAudioAdapter(pipeline=_make_pipeline(), room=room)
        participant = _rtc_stub.RemoteParticipant(identity="ghost")  # type: ignore[attr-defined]
        adapter._on_participant_disconnected_sync(participant)  # should not raise


# ---------------------------------------------------------------------------
# _consume_track — frame forwarding to pipeline
# ---------------------------------------------------------------------------


class TestConsumeTrack:
    @pytest.mark.asyncio
    async def test_forwards_frames_to_pipeline(self):
        """_consume_track reads frames and calls pipeline.process_audio."""
        pipeline = _make_pipeline()
        room = _make_room()
        adapter = LiveKitAudioAdapter(pipeline=pipeline, room=room)

        samples = list(range(48))  # 48 samples at 48kHz → 16 samples after decimation
        frame = _make_frame(samples, sample_rate=48_000, num_channels=1)
        event = _rtc_stub.AudioFrameEvent(frame=frame)  # type: ignore[attr-defined]

        async def _fake_stream():
            yield event

        mock_stream = AsyncMock()
        mock_stream.__aiter__ = lambda s: _fake_stream()
        mock_stream.aclose = AsyncMock()

        with patch("kutana_providers.audio.livekit_adapter.rtc") as mock_rtc:
            mock_rtc.AudioStream.return_value = mock_stream
            mock_rtc.AudioFrame = _rtc_stub.AudioFrame  # type: ignore[attr-defined]
            mock_rtc.TrackKind = _rtc_stub.TrackKind  # type: ignore[attr-defined]

            track = MagicMock()
            await adapter._consume_track(track, "alice")

        pipeline.process_audio.assert_awaited_once()
        forwarded: bytes = pipeline.process_audio.call_args[0][0]
        assert len(forwarded) > 0

    @pytest.mark.asyncio
    async def test_aclose_called_on_stream_after_cancellation(self):
        """AudioStream.aclose() is called even when the task is cancelled."""
        pipeline = _make_pipeline()
        room = _make_room()
        adapter = LiveKitAudioAdapter(pipeline=pipeline, room=room)

        mock_stream = AsyncMock()
        mock_stream.aclose = AsyncMock()

        async def _blocking_iter():
            await asyncio.sleep(999)
            return
            yield  # make it an async generator

        mock_stream.__aiter__ = lambda s: _blocking_iter()

        with patch("kutana_providers.audio.livekit_adapter.rtc") as mock_rtc:
            mock_rtc.AudioStream.return_value = mock_stream

            track = MagicMock()
            task = asyncio.ensure_future(adapter._consume_track(track, "alice"))
            await asyncio.sleep(0)  # let the coroutine start
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

        mock_stream.aclose.assert_awaited_once()
