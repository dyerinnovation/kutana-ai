"""Tests for WhisperRemoteSTT hallucination filter — especially None-safe handling."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from kutana_providers.stt.whisper_remote_stt import WhisperRemoteSTT


def _make_provider(
    api_url: str = "http://localhost:8080/v1",
) -> WhisperRemoteSTT:
    """Create a WhisperRemoteSTT with test defaults."""
    return WhisperRemoteSTT(
        api_url=api_url,
        meeting_id=uuid4(),
    )


def _mock_response(segments: list[dict] | None = None, text: str | None = None) -> MagicMock:
    """Build a mock aiohttp response with the given Whisper output."""
    body: dict = {}
    if segments is not None:
        body["segments"] = segments
    if text is not None:
        body["text"] = text

    resp = MagicMock()
    resp.status = 200
    resp.json = AsyncMock(return_value=body)
    resp.text = AsyncMock(return_value=json.dumps(body))
    resp.__aenter__ = AsyncMock(return_value=resp)
    resp.__aexit__ = AsyncMock(return_value=False)
    return resp


class TestNullFieldHandling:
    """Segments where Whisper returns null for no_speech_prob or compression_ratio."""

    async def test_no_speech_prob_none_does_not_crash(self) -> None:
        """Segment with no_speech_prob=None should not raise TypeError."""
        provider = _make_provider()
        provider._buffer = bytearray(b"\x00" * 32000)  # 1 second of silence
        provider._started = True

        segment = {
            "start": 0.0,
            "end": 1.0,
            "text": "Hello world",
            "no_speech_prob": None,
            "compression_ratio": 1.2,
            "avg_logprob": -0.3,
        }
        resp = _mock_response(segments=[segment])

        session_mock = MagicMock()
        session_mock.post = MagicMock(return_value=resp)

        with patch.object(provider, "_session", session_mock):
            results = [seg async for seg in provider.get_transcript()]

        assert len(results) == 1
        assert results[0].text == "Hello world"

    async def test_compression_ratio_none_does_not_crash(self) -> None:
        """Segment with compression_ratio=None should not raise TypeError."""
        provider = _make_provider()
        provider._buffer = bytearray(b"\x00" * 32000)
        provider._started = True

        segment = {
            "start": 0.0,
            "end": 1.0,
            "text": "Hello world",
            "no_speech_prob": 0.1,
            "compression_ratio": None,
            "avg_logprob": -0.3,
        }
        resp = _mock_response(segments=[segment])

        session_mock = MagicMock()
        session_mock.post = MagicMock(return_value=resp)

        with patch.object(provider, "_session", session_mock):
            results = [seg async for seg in provider.get_transcript()]

        assert len(results) == 1
        assert results[0].text == "Hello world"

    async def test_both_fields_none_does_not_crash(self) -> None:
        """Segment with both no_speech_prob and compression_ratio as None."""
        provider = _make_provider()
        provider._buffer = bytearray(b"\x00" * 32000)
        provider._started = True

        segment = {
            "start": 0.0,
            "end": 1.0,
            "text": "Testing one two three",
            "no_speech_prob": None,
            "compression_ratio": None,
            "avg_logprob": -0.5,
        }
        resp = _mock_response(segments=[segment])

        session_mock = MagicMock()
        session_mock.post = MagicMock(return_value=resp)

        with patch.object(provider, "_session", session_mock):
            results = [seg async for seg in provider.get_transcript()]

        assert len(results) == 1
        assert results[0].text == "Testing one two three"

    async def test_fields_missing_entirely_does_not_crash(self) -> None:
        """Segment with no_speech_prob and compression_ratio keys absent entirely."""
        provider = _make_provider()
        provider._buffer = bytearray(b"\x00" * 32000)
        provider._started = True

        segment = {
            "start": 0.0,
            "end": 1.0,
            "text": "Just text, no metadata",
        }
        resp = _mock_response(segments=[segment])

        session_mock = MagicMock()
        session_mock.post = MagicMock(return_value=resp)

        with patch.object(provider, "_session", session_mock):
            results = [seg async for seg in provider.get_transcript()]

        assert len(results) == 1
        assert results[0].text == "Just text, no metadata"


class TestFilterBehavior:
    """Verify that the hallucination gates still filter correctly."""

    async def test_high_no_speech_prob_drops_segment(self) -> None:
        """Segment with no_speech_prob above threshold is dropped."""
        provider = _make_provider()
        provider._buffer = bytearray(b"\x00" * 32000)
        provider._started = True

        segment = {
            "start": 0.0,
            "end": 1.0,
            "text": "Should be dropped",
            "no_speech_prob": 0.9,
            "compression_ratio": 1.0,
        }
        resp = _mock_response(segments=[segment])

        session_mock = MagicMock()
        session_mock.post = MagicMock(return_value=resp)

        with patch.object(provider, "_session", session_mock):
            results = [seg async for seg in provider.get_transcript()]

        assert len(results) == 0

    async def test_too_short_segment_dropped(self) -> None:
        """Segment shorter than min_segment_duration_s is dropped."""
        provider = _make_provider()
        provider._buffer = bytearray(b"\x00" * 32000)
        provider._started = True

        segment = {
            "start": 0.0,
            "end": 0.08,
            "text": "I'm sorry.",
            "no_speech_prob": 0.1,
            "compression_ratio": 1.0,
        }
        resp = _mock_response(segments=[segment])

        session_mock = MagicMock()
        session_mock.post = MagicMock(return_value=resp)

        with patch.object(provider, "_session", session_mock):
            results = [seg async for seg in provider.get_transcript()]

        assert len(results) == 0

    async def test_hallucination_phrase_dropped(self) -> None:
        """Known hallucination phrase is dropped by blocklist."""
        provider = _make_provider()
        provider._buffer = bytearray(b"\x00" * 32000)
        provider._started = True

        segment = {
            "start": 0.0,
            "end": 1.0,
            "text": "Thank you.",
            "no_speech_prob": 0.1,
            "compression_ratio": 1.0,
        }
        resp = _mock_response(segments=[segment])

        session_mock = MagicMock()
        session_mock.post = MagicMock(return_value=resp)

        with patch.object(provider, "_session", session_mock):
            results = [seg async for seg in provider.get_transcript()]

        assert len(results) == 0

    async def test_normal_segment_passes_all_gates(self) -> None:
        """A legitimate speech segment passes all five gates."""
        provider = _make_provider()
        provider._buffer = bytearray(b"\x00" * 32000)
        provider._started = True

        segment = {
            "start": 0.5,
            "end": 2.5,
            "text": "The quarterly revenue exceeded expectations by twelve percent.",
            "no_speech_prob": 0.02,
            "compression_ratio": 1.1,
            "avg_logprob": -0.15,
        }
        resp = _mock_response(segments=[segment])

        session_mock = MagicMock()
        session_mock.post = MagicMock(return_value=resp)

        with patch.object(provider, "_session", session_mock):
            results = [seg async for seg in provider.get_transcript()]

        assert len(results) == 1
        assert results[0].text == "The quarterly revenue exceeded expectations by twelve percent."
        assert results[0].confidence > 0.8
