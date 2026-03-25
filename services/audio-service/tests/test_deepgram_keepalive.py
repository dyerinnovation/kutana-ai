"""Tests for Deepgram STT keepalive, reconnect, and pipeline reset."""

from __future__ import annotations

import asyncio
import contextlib
import json
import struct
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from websockets.exceptions import ConnectionClosedError

from audio_service.audio_pipeline import AudioPipeline
from convene_core.models.transcript import TranscriptSegment
from convene_providers.stt.deepgram_stt import DeepgramSTT
from convene_providers.testing import MockSTT

# ---- Helpers ----

MEETING_ID = uuid4()
FAKE_API_KEY = "test-api-key-123"


def _make_pcm16(num_samples: int = 160) -> bytes:
    """Create valid PCM16 16kHz mono audio bytes."""
    return struct.pack(f"<{num_samples}h", *([0] * num_samples))


def _make_segments(n: int = 2) -> list[TranscriptSegment]:
    """Create sample transcript segments for testing."""
    return [
        TranscriptSegment(
            meeting_id=MEETING_ID,
            speaker_id=f"spk_{i}",
            text=f"Segment {i}",
            start_time=float(i * 10),
            end_time=float(i * 10 + 5),
            confidence=0.9,
        )
        for i in range(n)
    ]


def _make_deepgram_message(
    text: str = "Hello world",
    confidence: float = 0.95,
    is_final: bool = True,
    speaker: int = 0,
) -> str:
    """Create a Deepgram-style JSON response message."""
    return json.dumps(
        {
            "channel": {
                "alternatives": [
                    {
                        "transcript": text,
                        "confidence": confidence,
                        "words": [
                            {"word": w, "start": 0.0, "end": 1.0, "speaker": speaker}
                            for w in text.split()
                        ],
                    }
                ]
            },
            "is_final": is_final,
        }
    )


def _make_async_connect_mock(return_value: object) -> MagicMock:
    """Create a mock for websockets.connect that is properly awaitable.

    websockets.connect() returns a Connect object that acts as both an
    async context manager and an awaitable.  When used as ``await
    websockets.connect(...)``, Python calls ``__await__`` on the result.
    We simulate this by making the mock callable return a coroutine.
    """
    mock = MagicMock()

    async def _connect_coro(*args: object, **kwargs: object) -> object:
        return return_value

    mock.side_effect = _connect_coro
    return mock


# ---- KeepAlive Task Tests ----


class TestDeepgramKeepalive:
    """Tests for the KeepAlive background task."""

    async def test_keepalive_sends_message_on_schedule(self) -> None:
        """KeepAlive task sends a JSON message after the interval elapses."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY, meeting_id=MEETING_ID)

        mock_ws = AsyncMock()
        provider._ws = mock_ws
        # Set last audio time far in the past so keepalive fires
        provider._last_audio_time = 0.0

        # Patch the interval to be very short for testing
        with (
            patch(
                "convene_providers.stt.deepgram_stt._KEEPALIVE_INTERVAL_S",
                0.05,
            ),
            patch(
                "convene_providers.stt.deepgram_stt._AUDIO_FRESHNESS_S",
                0.01,
            ),
        ):
            task = asyncio.create_task(provider._keepalive_loop())
            # Allow time for at least one keepalive to fire
            await asyncio.sleep(0.15)
            task.cancel()
            # The keepalive loop catches CancelledError internally, so
            # the task completes cleanly without re-raising.
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # Verify at least one KeepAlive message was sent
        assert mock_ws.send.call_count >= 1
        sent_msg = json.loads(mock_ws.send.call_args_list[0][0][0])
        assert sent_msg == {"type": "KeepAlive"}

    async def test_keepalive_skips_when_audio_fresh(self) -> None:
        """KeepAlive is not sent if audio was sent recently."""
        import time

        provider = DeepgramSTT(api_key=FAKE_API_KEY, meeting_id=MEETING_ID)

        mock_ws = AsyncMock()
        provider._ws = mock_ws

        # Simulate very recent audio by setting _last_audio_time far in the future
        provider._last_audio_time = time.monotonic() + 9999

        with patch(
            "convene_providers.stt.deepgram_stt._KEEPALIVE_INTERVAL_S",
            0.05,
        ):
            task = asyncio.create_task(provider._keepalive_loop())
            await asyncio.sleep(0.15)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

        # No KeepAlive should have been sent
        mock_ws.send.assert_not_called()

    async def test_keepalive_stops_on_connection_closed(self) -> None:
        """KeepAlive loop exits cleanly on ConnectionClosedError."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY, meeting_id=MEETING_ID)

        mock_ws = AsyncMock()
        mock_ws.send.side_effect = ConnectionClosedError(None, None)
        provider._ws = mock_ws
        provider._last_audio_time = 0.0

        with (
            patch(
                "convene_providers.stt.deepgram_stt._KEEPALIVE_INTERVAL_S",
                0.05,
            ),
            patch(
                "convene_providers.stt.deepgram_stt._AUDIO_FRESHNESS_S",
                0.01,
            ),
        ):
            task = asyncio.create_task(provider._keepalive_loop())
            # Task should exit on its own after the send fails
            await asyncio.sleep(0.15)
            # Task should have completed by now (not still running)
            assert task.done()


# ---- send_audio Reconnection Tests ----


class TestSendAudioReconnect:
    """Tests for send_audio reconnection on connection error."""

    async def test_send_audio_reconnects_on_closed_error(self) -> None:
        """send_audio reconnects and retries after ConnectionClosedError."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY, meeting_id=MEETING_ID)

        # First WS: send raises ConnectionClosedError
        mock_ws_dead = AsyncMock()
        mock_ws_dead.send.side_effect = ConnectionClosedError(None, None)

        # After reconnect: a fresh WS that works
        mock_ws_fresh = AsyncMock()

        provider._ws = mock_ws_dead
        provider._keepalive_task = None

        with patch.object(provider, "_reconnect") as mock_reconnect:

            async def do_reconnect() -> None:
                provider._ws = mock_ws_fresh
                provider._keepalive_task = asyncio.create_task(asyncio.sleep(999))

            mock_reconnect.side_effect = do_reconnect

            chunk = _make_pcm16()
            await provider.send_audio(chunk)

            mock_reconnect.assert_called_once()
            mock_ws_fresh.send.assert_called_once_with(chunk)

        # Clean up the keepalive task
        if provider._keepalive_task:
            provider._keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await provider._keepalive_task

    async def test_send_audio_raises_if_not_started(self) -> None:
        """send_audio raises RuntimeError if start_stream was not called."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY)
        with pytest.raises(RuntimeError, match="Stream not started"):
            await provider.send_audio(b"\x00" * 320)


# ---- get_transcript Reconnection Tests ----


class TestGetTranscriptReconnect:
    """Tests for get_transcript reconnection on connection error."""

    async def test_get_transcript_reconnects_on_closed_error(self) -> None:
        """get_transcript reconnects and resumes after ConnectionClosedError."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY, meeting_id=MEETING_ID)

        # First iteration: yields one message then raises ConnectionClosedError
        # Second iteration: yields one message then exhausts
        async def mock_aiter_first(ws: object) -> None:
            """First WS: yield a message then die."""
            yield _make_deepgram_message("first segment")
            raise ConnectionClosedError(None, None)

        async def mock_aiter_second(ws: object) -> None:
            """Second WS: yield a message then finish."""
            yield _make_deepgram_message("second segment")

        mock_ws1 = MagicMock()
        mock_ws1.__aiter__ = lambda self: mock_aiter_first(self)

        mock_ws2 = MagicMock()
        mock_ws2.__aiter__ = lambda self: mock_aiter_second(self)

        provider._ws = mock_ws1

        with patch.object(provider, "_reconnect") as mock_reconnect:

            async def do_reconnect() -> None:
                provider._ws = mock_ws2

            mock_reconnect.side_effect = do_reconnect

            segments = []
            async for seg in provider.get_transcript():
                segments.append(seg)

            assert len(segments) == 2
            assert segments[0].text == "first segment"
            assert segments[1].text == "second segment"
            mock_reconnect.assert_called_once()

    async def test_get_transcript_raises_if_not_started(self) -> None:
        """get_transcript raises RuntimeError if start_stream was not called."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY)
        with pytest.raises(RuntimeError, match="Stream not started"):
            async for _ in provider.get_transcript():
                pass


# ---- _reconnect Tests ----


class TestReconnect:
    """Tests for the _reconnect method."""

    async def test_reconnect_establishes_new_connection(self) -> None:
        """_reconnect closes dead WS and opens a new one."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY, meeting_id=MEETING_ID)

        mock_ws_dead = AsyncMock()
        provider._ws = mock_ws_dead
        provider._keepalive_task = None

        mock_ws_fresh = AsyncMock()

        with patch(
            "convene_providers.stt.deepgram_stt.websockets.connect",
            _make_async_connect_mock(mock_ws_fresh),
        ):
            await provider._reconnect()

            assert provider._ws is mock_ws_fresh
            mock_ws_dead.close.assert_called_once()
            assert provider._keepalive_task is not None

        # Clean up
        if provider._keepalive_task:
            provider._keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await provider._keepalive_task

    async def test_reconnect_retries_on_failure(self) -> None:
        """_reconnect retries up to MAX_RECONNECT_ATTEMPTS."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY, meeting_id=MEETING_ID)
        provider._ws = AsyncMock()
        provider._keepalive_task = None

        mock_ws_fresh = AsyncMock()
        call_count = 0

        async def connect_with_failures(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise OSError(f"fail {call_count}")
            return mock_ws_fresh

        mock_connect = MagicMock(side_effect=connect_with_failures)

        with (
            patch(
                "convene_providers.stt.deepgram_stt.websockets.connect",
                mock_connect,
            ),
            patch("convene_providers.stt.deepgram_stt._RECONNECT_DELAY_S", 0.01),
        ):
            await provider._reconnect()

            assert mock_connect.call_count == 3
            assert provider._ws is mock_ws_fresh

        # Clean up
        if provider._keepalive_task:
            provider._keepalive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await provider._keepalive_task

    async def test_reconnect_raises_after_exhausted_attempts(self) -> None:
        """_reconnect raises ConnectionClosedError after all retries fail."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY, meeting_id=MEETING_ID)
        provider._ws = AsyncMock()
        provider._keepalive_task = None

        async def always_fail(*args: object, **kwargs: object) -> None:
            raise OSError("always fails")

        mock_connect = MagicMock(side_effect=always_fail)

        with (
            patch(
                "convene_providers.stt.deepgram_stt.websockets.connect",
                mock_connect,
            ),
            patch("convene_providers.stt.deepgram_stt._RECONNECT_DELAY_S", 0.01),
            pytest.raises(ConnectionClosedError),
        ):
            await provider._reconnect()


# ---- AudioPipeline reset_provider Tests ----


class TestPipelineResetProvider:
    """Tests for AudioPipeline.reset_provider."""

    async def test_reset_provider_swaps_stt(self) -> None:
        """reset_provider replaces the STT provider and resets state."""
        old_stt = MockSTT()
        pipeline = AudioPipeline(stt_provider=old_stt, meeting_id=MEETING_ID)

        # Start the pipeline
        await pipeline.process_audio(_make_pcm16())
        assert pipeline._started

        # Reset with new provider
        new_stt = MockSTT(segments=_make_segments(1))
        pipeline.reset_provider(new_stt)

        assert pipeline._stt is new_stt
        assert not pipeline._started
        assert len(pipeline._audio_buffer) == 0

    async def test_reset_provider_allows_restart(self) -> None:
        """After reset_provider, process_audio re-starts the stream."""
        old_stt = MockSTT()
        pipeline = AudioPipeline(stt_provider=old_stt, meeting_id=MEETING_ID)

        await pipeline.process_audio(_make_pcm16())
        assert old_stt._started

        new_stt = MockSTT(segments=_make_segments(2))
        pipeline.reset_provider(new_stt)
        assert not new_stt._started

        # Process audio should start the new provider
        await pipeline.process_audio(_make_pcm16())
        assert new_stt._started

        # Should yield the new segments
        result = [seg async for seg in pipeline.get_segments()]
        assert len(result) == 2

    async def test_reset_clears_audio_buffer(self) -> None:
        """reset_provider clears any buffered audio data."""
        mock_stt = MagicMock()
        mock_stt.start_stream = AsyncMock()
        mock_stt.send_audio = AsyncMock(side_effect=RuntimeError("fail"))

        pipeline = AudioPipeline(stt_provider=mock_stt, meeting_id=MEETING_ID)

        with patch("audio_service.audio_pipeline._RETRY_DELAY_S", 0.01):
            await pipeline.process_audio(_make_pcm16())

        assert len(pipeline._audio_buffer) > 0

        new_stt = MockSTT()
        pipeline.reset_provider(new_stt)
        assert len(pipeline._audio_buffer) == 0


# ---- close() Tests ----


class TestDeepgramClose:
    """Tests for DeepgramSTT.close with keepalive cleanup."""

    async def test_close_cancels_keepalive_task(self) -> None:
        """close() cancels the keepalive task."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY, meeting_id=MEETING_ID)

        mock_ws = AsyncMock()
        provider._ws = mock_ws

        # Create a long-running keepalive task
        provider._keepalive_task = asyncio.create_task(asyncio.sleep(9999))

        await provider.close()

        assert provider._ws is None
        assert provider._keepalive_task is None

    async def test_close_without_start_is_safe(self) -> None:
        """close() is a no-op if the stream was never started."""
        provider = DeepgramSTT(api_key=FAKE_API_KEY)
        # Should not raise
        await provider.close()
        assert provider._ws is None
        assert provider._keepalive_task is None
