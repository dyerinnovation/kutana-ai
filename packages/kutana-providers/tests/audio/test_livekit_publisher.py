"""Unit tests for LiveKitAudioPublisher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from kutana_providers.audio.livekit_publisher import LiveKitAudioPublisher

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

_FRAME_BYTES = 960  # 480 samples @ 24 kHz, mono, PCM16 (2 bytes/sample)


def _make_rtc_mock() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return (rtc_module, audio_source_instance, track_instance)."""
    rtc = MagicMock()

    # AudioSource instance — capture_frame must be awaitable.
    source = MagicMock()
    source.capture_frame = AsyncMock()
    rtc.AudioSource.return_value = source

    # LocalAudioTrack.create_audio_track returns a mock track.
    track = MagicMock()
    rtc.LocalAudioTrack.create_audio_track.return_value = track

    # AudioFrame.create returns a frame with a writable bytearray.
    def _make_frame(sample_rate: int, num_channels: int, samples: int) -> MagicMock:
        frame = MagicMock()
        frame.data = bytearray(samples * num_channels * 2)
        return frame

    rtc.AudioFrame.create.side_effect = _make_frame

    # TrackPublishOptions and TrackSource.SOURCE_MICROPHONE.
    rtc.TrackPublishOptions.return_value = MagicMock()
    rtc.TrackSource.SOURCE_MICROPHONE = MagicMock()

    return rtc, source, track


def _make_room() -> MagicMock:
    """Return a mocked rtc.Room with an async local_participant."""
    room = MagicMock()
    publication = MagicMock()
    publication.sid = "track-sid-test"
    room.local_participant.publish_track = AsyncMock(return_value=publication)
    room.local_participant.unpublish_track = AsyncMock()
    return room


# ---------------------------------------------------------------------------
# Start / stop lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    async def test_start_creates_source_and_publishes(self) -> None:
        """start() creates AudioSource, LocalAudioTrack, and publishes to the room."""
        rtc_mock, source, track = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()

        rtc_mock.AudioSource.assert_called_once_with(sample_rate=24_000, num_channels=1)
        rtc_mock.LocalAudioTrack.create_audio_track.assert_called_once_with("agent-tts", source)
        room.local_participant.publish_track.assert_called_once()

    async def test_start_stores_publication(self) -> None:
        """start() stores the returned publication for later unpublish."""
        rtc_mock, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()

        assert pub._publication is not None
        assert pub._publication.sid == "track-sid-test"

    async def test_stop_unpublishes_by_sid(self) -> None:
        """stop() calls unpublish_track with the publication SID."""
        rtc_mock, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.stop()

        room.local_participant.unpublish_track.assert_called_once_with("track-sid-test")

    async def test_stop_clears_internal_state(self) -> None:
        """stop() sets _source, _track, and _publication to None."""
        rtc_mock, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.stop()

        assert pub._source is None
        assert pub._track is None
        assert pub._publication is None

    async def test_stop_before_start_is_safe(self) -> None:
        """stop() without a prior start() does not raise and skips unpublish."""
        rtc_mock, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.stop()  # must not raise

        room.local_participant.unpublish_track.assert_not_called()

    async def test_stopped_flag_set_after_stop(self) -> None:
        """stop() sets _stopped to True."""
        rtc_mock, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.stop()

        assert pub._stopped is True


# ---------------------------------------------------------------------------
# Frame chunking — push_audio
# ---------------------------------------------------------------------------


class TestFrameChunking:
    async def test_exact_single_frame(self) -> None:
        """One 960-byte chunk produces exactly one captured frame."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.push_audio(b"\x01" * _FRAME_BYTES)

        assert source.capture_frame.call_count == 1
        assert pub._remainder == b""

    async def test_partial_chunk_buffered(self) -> None:
        """A sub-frame chunk produces no captured frames; bytes go to remainder."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.push_audio(b"\x02" * 500)

        assert source.capture_frame.call_count == 0
        assert len(pub._remainder) == 500

    async def test_cartesia_chunk_splits_correctly(self) -> None:
        """4 096-byte Cartesia chunk → 4 frames + 256-byte remainder."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.push_audio(b"\x00" * 4096)

        assert source.capture_frame.call_count == 4
        assert len(pub._remainder) == 4096 % _FRAME_BYTES  # 256

    async def test_remainder_combines_with_next_chunk(self) -> None:
        """Two partial chunks that together span > one frame produce one frame."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.push_audio(b"\x00" * 500)
            assert source.capture_frame.call_count == 0

            await pub.push_audio(b"\x00" * 500)  # 500 + 500 = 1000 > 960

        assert source.capture_frame.call_count == 1
        assert len(pub._remainder) == 1000 - _FRAME_BYTES  # 40

    async def test_multiple_frames_across_many_calls(self) -> None:
        """Sequential calls accumulate remainder correctly across many frames."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            # 10 x 960 = exactly 10 frames, no remainder.
            for _ in range(10):
                await pub.push_audio(b"\x00" * _FRAME_BYTES)

        assert source.capture_frame.call_count == 10
        assert pub._remainder == b""

    async def test_no_capture_after_stop(self) -> None:
        """push_audio after stop() is a no-op."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.stop()
            source.capture_frame.reset_mock()
            await pub.push_audio(b"\x00" * _FRAME_BYTES)

        source.capture_frame.assert_not_called()


# ---------------------------------------------------------------------------
# stop() remainder flush
# ---------------------------------------------------------------------------


class TestStopFlush:
    async def test_partial_remainder_flushed_on_stop(self) -> None:
        """stop() zero-pads any buffered partial frame and captures it."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.push_audio(b"\xff" * 400)  # partial — below 960 bytes
            assert source.capture_frame.call_count == 0

            await pub.stop()

        assert source.capture_frame.call_count == 1
        assert pub._remainder == b""

    async def test_no_flush_when_remainder_empty(self) -> None:
        """stop() does not push an extra silent frame if remainder is empty."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.push_audio(b"\x00" * _FRAME_BYTES)  # exactly one frame, no remainder
            source.capture_frame.reset_mock()

            await pub.stop()

        source.capture_frame.assert_not_called()


# ---------------------------------------------------------------------------
# push_audio_stream
# ---------------------------------------------------------------------------


class TestPushAudioStream:
    async def test_stream_processes_all_chunks(self) -> None:
        """push_audio_stream feeds each yielded chunk through push_audio."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        async def _five_frames():
            for _ in range(5):
                yield b"\x00" * _FRAME_BYTES

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.push_audio_stream(_five_frames())

        assert source.capture_frame.call_count == 5

    async def test_stream_exits_early_on_stop(self) -> None:
        """push_audio_stream stops consuming after _stopped is set True."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()

            chunks_yielded = 0

            async def _chunks_with_stop():
                nonlocal chunks_yielded
                for i in range(6):
                    if i == 3:
                        pub._stopped = True
                    yield b"\x00" * _FRAME_BYTES
                    chunks_yielded += 1

            await pub.push_audio_stream(_chunks_with_stop())

        # First 3 chunks (i=0,1,2) processed; i=3 sets stopped before yield,
        # so the loop breaks before processing it.
        assert source.capture_frame.call_count == 3

    async def test_stream_with_partial_chunks(self) -> None:
        """push_audio_stream handles sub-frame chunks via internal buffering."""
        rtc_mock, source, *_ = _make_rtc_mock()
        room = _make_room()

        async def _partial_chunks():
            # 3 x 320 bytes = 960 bytes = exactly 1 frame.
            for _ in range(3):
                yield b"\x00" * 320

        with patch("kutana_providers.audio.livekit_publisher.rtc", rtc_mock):
            pub = LiveKitAudioPublisher(room)
            await pub.start()
            await pub.push_audio_stream(_partial_chunks())

        assert source.capture_frame.call_count == 1
        assert pub._remainder == b""
