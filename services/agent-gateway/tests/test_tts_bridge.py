"""Unit tests for the TTS bridge — voice pool, budget, cache, and synthesis."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from agent_gateway.tts_bridge import (
    CharBudgetTracker,
    PhraseCache,
    TTSBridge,
    VoicePool,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_provider(audio_data: bytes = b"\xff" * 400) -> Any:
    """Return a mock TTSProvider that returns fixed audio bytes."""
    provider = MagicMock()
    provider.synthesize_batch = AsyncMock(return_value=audio_data)
    provider.list_voices = AsyncMock(return_value=[])
    provider.close = AsyncMock()
    return provider


def _make_mock_manager(sessions: list[Any] | None = None) -> Any:
    """Return a mock ConnectionManager."""
    manager = MagicMock()
    manager.get_meeting_sessions = MagicMock(return_value=sessions or [])
    return manager


def _make_mock_session(capabilities: list[str] | None = None) -> Any:
    """Return a mock SessionHandler."""
    session = MagicMock()
    session.session_id = uuid4()
    session.capabilities = capabilities or ["listen"]
    session.send_event = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# VoicePool
# ---------------------------------------------------------------------------


class TestVoicePool:
    """Tests for VoicePool."""

    def test_round_robin_assignment(self) -> None:
        """Voices are assigned round-robin from the pool."""
        pool = VoicePool(["voice-a", "voice-b", "voice-c"])
        ids = [uuid4() for _ in range(5)]
        voices = [pool.assign(sid) for sid in ids]
        assert voices[0] == "voice-a"
        assert voices[1] == "voice-b"
        assert voices[2] == "voice-c"
        assert voices[3] == "voice-a"  # wraps around
        assert voices[4] == "voice-b"

    def test_requested_voice_takes_precedence(self) -> None:
        """Requested voice overrides pool assignment."""
        pool = VoicePool(["pool-voice"])
        sid = uuid4()
        voice = pool.assign(sid, requested_voice="custom-voice")
        assert voice == "custom-voice"

    def test_existing_assignment_not_overridden(self) -> None:
        """Assigning a second time returns the first assignment."""
        pool = VoicePool(["voice-a", "voice-b"])
        sid = uuid4()
        first = pool.assign(sid)
        second = pool.assign(sid)
        assert first == second == "voice-a"

    def test_release_removes_assignment(self) -> None:
        """Release removes the session's assignment."""
        pool = VoicePool(["voice-a"])
        sid = uuid4()
        pool.assign(sid)
        pool.release(sid)
        assert pool.get(sid) is None

    def test_get_returns_none_for_unassigned(self) -> None:
        """get() returns None for sessions without an assignment."""
        pool = VoicePool()
        assert pool.get(uuid4()) is None

    def test_distinct_voices_per_session(self) -> None:
        """Different sessions get different voices from a 2-voice pool."""
        pool = VoicePool(["voice-a", "voice-b"])
        sid1, sid2 = uuid4(), uuid4()
        v1 = pool.assign(sid1)
        v2 = pool.assign(sid2)
        assert v1 != v2


# ---------------------------------------------------------------------------
# CharBudgetTracker
# ---------------------------------------------------------------------------


class TestCharBudgetTracker:
    """Tests for CharBudgetTracker."""

    def test_within_budget(self) -> None:
        """check_and_consume returns True when within limit."""
        tracker = CharBudgetTracker(limit=100)
        sid = uuid4()
        assert tracker.check_and_consume(sid, 50) is True
        assert tracker.get_usage(sid) == 50

    def test_exact_limit_allowed(self) -> None:
        """Consuming exactly the limit is allowed."""
        tracker = CharBudgetTracker(limit=100)
        sid = uuid4()
        assert tracker.check_and_consume(sid, 100) is True

    def test_exceeds_budget(self) -> None:
        """check_and_consume returns False when budget is exceeded."""
        tracker = CharBudgetTracker(limit=100)
        sid = uuid4()
        tracker.check_and_consume(sid, 60)
        assert tracker.check_and_consume(sid, 50) is False

    def test_budget_not_consumed_on_exceed(self) -> None:
        """Usage is not incremented when check fails."""
        tracker = CharBudgetTracker(limit=100)
        sid = uuid4()
        tracker.check_and_consume(sid, 60)
        tracker.check_and_consume(sid, 50)  # exceeds → no consume
        assert tracker.get_usage(sid) == 60

    def test_release_removes_usage(self) -> None:
        """release() removes the session's usage record."""
        tracker = CharBudgetTracker(limit=100)
        sid = uuid4()
        tracker.check_and_consume(sid, 30)
        tracker.release(sid)
        assert tracker.get_usage(sid) == 0

    def test_get_usage_zero_for_new_session(self) -> None:
        """get_usage returns 0 for sessions that have not consumed anything."""
        tracker = CharBudgetTracker(limit=1000)
        assert tracker.get_usage(uuid4()) == 0

    def test_limit_property(self) -> None:
        """limit property returns the configured limit."""
        tracker = CharBudgetTracker(limit=500)
        assert tracker.limit == 500


# ---------------------------------------------------------------------------
# PhraseCache
# ---------------------------------------------------------------------------


class TestPhraseCache:
    """Tests for PhraseCache."""

    def test_put_and_get(self) -> None:
        """put() stores audio and get() retrieves it."""
        cache = PhraseCache(max_size=10)
        cache.put("voice-a", "hello world", b"\xff" * 100)
        result = cache.get("voice-a", "hello world")
        assert result == b"\xff" * 100

    def test_miss_returns_none(self) -> None:
        """get() returns None for uncached entries."""
        cache = PhraseCache()
        assert cache.get("voice-a", "missing phrase") is None

    def test_different_voices_are_separate_entries(self) -> None:
        """Same text with different voices are distinct cache entries."""
        cache = PhraseCache()
        cache.put("voice-a", "hello", b"\x01" * 10)
        cache.put("voice-b", "hello", b"\x02" * 10)
        assert cache.get("voice-a", "hello") == b"\x01" * 10
        assert cache.get("voice-b", "hello") == b"\x02" * 10

    def test_eviction_when_full(self) -> None:
        """Oldest entry is evicted when max_size is reached."""
        cache = PhraseCache(max_size=2)
        cache.put("v", "first", b"\x01")
        cache.put("v", "second", b"\x02")
        cache.put("v", "third", b"\x03")  # evicts "first"
        assert cache.get("v", "first") is None
        assert cache.get("v", "second") == b"\x02"
        assert cache.get("v", "third") == b"\x03"

    def test_size_property(self) -> None:
        """size reflects the current number of cached entries."""
        cache = PhraseCache()
        assert cache.size == 0
        cache.put("v", "a", b"\x00")
        assert cache.size == 1


# ---------------------------------------------------------------------------
# TTSBridge
# ---------------------------------------------------------------------------


class TestTTSBridge:
    """Tests for TTSBridge synthesis, budget, and broadcast."""

    @pytest.mark.asyncio
    async def test_synthesize_text_returns_audio(self) -> None:
        """synthesize_text returns audio bytes from the provider."""
        provider = _make_mock_provider(b"\xab" * 200)
        manager = _make_mock_manager()
        bridge = TTSBridge(provider, manager, char_limit=10_000)
        sid = uuid4()
        bridge.assign_voice(sid)

        result = await bridge.synthesize_text(sid, "hello")
        assert result == b"\xab" * 200

    @pytest.mark.asyncio
    async def test_synthesize_empty_text_returns_none(self) -> None:
        """synthesize_text returns None for empty/whitespace-only text."""
        provider = _make_mock_provider()
        manager = _make_mock_manager()
        bridge = TTSBridge(provider, manager)
        sid = uuid4()

        assert await bridge.synthesize_text(sid, "") is None
        assert await bridge.synthesize_text(sid, "   ") is None

    @pytest.mark.asyncio
    async def test_synthesize_uses_cache_on_repeat(self) -> None:
        """Repeated identical text hits the cache — provider called once."""
        audio = b"\xcc" * 100
        provider = _make_mock_provider(audio)
        manager = _make_mock_manager()
        bridge = TTSBridge(provider, manager, char_limit=100_000)
        sid = uuid4()
        bridge.assign_voice(sid)

        await bridge.synthesize_text(sid, "cached phrase")
        await bridge.synthesize_text(sid, "cached phrase")  # cache hit
        provider.synthesize_batch.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_budget_exceeded_returns_none(self) -> None:
        """synthesize_text returns None when char budget is exceeded."""
        provider = _make_mock_provider()
        manager = _make_mock_manager()
        bridge = TTSBridge(provider, manager, char_limit=5)
        sid = uuid4()
        bridge.assign_voice(sid)

        result = await bridge.synthesize_text(sid, "more than 5 chars")
        assert result is None

    @pytest.mark.asyncio
    async def test_synthesize_and_broadcast_delivers_to_listeners(self) -> None:
        """synthesize_and_broadcast sends tts.audio to listen-capable sessions."""
        audio = b"\xdd" * 50
        provider = _make_mock_provider(audio)
        listener = _make_mock_session(capabilities=["listen"])
        deaf_session = _make_mock_session(capabilities=["data_only"])
        manager = _make_mock_manager(sessions=[listener, deaf_session])

        bridge = TTSBridge(provider, manager, char_limit=100_000)
        sid = uuid4()
        bridge.assign_voice(sid)
        meeting_id = uuid4()

        success = await bridge.synthesize_and_broadcast(
            session_id=sid,
            meeting_id=meeting_id,
            text="Hello meeting",
            speaker_name="Agent-1",
        )

        assert success is True
        listener.send_event.assert_awaited_once()
        event_type, payload = listener.send_event.call_args[0]
        assert event_type == "tts.audio"
        assert payload["speaker_name"] == "Agent-1"
        assert "data" in payload
        # Sessions without 'listen' should NOT receive audio
        deaf_session.send_event.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_synthesize_and_broadcast_returns_false_on_budget_exceeded(
        self,
    ) -> None:
        """synthesize_and_broadcast returns False when budget is exceeded."""
        provider = _make_mock_provider()
        manager = _make_mock_manager()
        bridge = TTSBridge(provider, manager, char_limit=0)
        sid = uuid4()
        bridge.assign_voice(sid)

        result = await bridge.synthesize_and_broadcast(
            session_id=sid,
            meeting_id=uuid4(),
            text="any text",
            speaker_name="Agent",
        )
        assert result is False

    def test_assign_voice_returns_pool_voice(self) -> None:
        """assign_voice returns a voice from the pool."""
        provider = _make_mock_provider()
        manager = _make_mock_manager()
        bridge = TTSBridge(provider, manager, voice_pool=["v1", "v2"])
        sid = uuid4()
        voice = bridge.assign_voice(sid)
        assert voice in ("v1", "v2")

    def test_assign_voice_respects_requested(self) -> None:
        """assign_voice uses the requested voice if provided."""
        provider = _make_mock_provider()
        manager = _make_mock_manager()
        bridge = TTSBridge(provider, manager)
        sid = uuid4()
        voice = bridge.assign_voice(sid, requested_voice="special-voice")
        assert voice == "special-voice"

    def test_release_session_clears_state(self) -> None:
        """release_session removes voice and budget records."""
        provider = _make_mock_provider()
        manager = _make_mock_manager()
        bridge = TTSBridge(provider, manager, char_limit=100)
        sid = uuid4()
        bridge.assign_voice(sid)
        bridge.release_session(sid)
        assert bridge.get_voice(sid) is None
        assert bridge.get_budget_info(sid)["used"] == 0

    def test_get_budget_info(self) -> None:
        """get_budget_info returns correct used/limit/remaining."""
        provider = _make_mock_provider()
        manager = _make_mock_manager()
        bridge = TTSBridge(provider, manager, char_limit=1000)
        sid = uuid4()
        # No chars consumed yet
        info = bridge.get_budget_info(sid)
        assert info["used"] == 0
        assert info["limit"] == 1000
        assert info["remaining"] == 1000

    @pytest.mark.asyncio
    async def test_close_calls_provider_close(self) -> None:
        """close() propagates to the underlying provider."""
        provider = _make_mock_provider()
        manager = _make_mock_manager()
        bridge = TTSBridge(provider, manager)
        await bridge.close()
        provider.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# TTS protocol message tests
# ---------------------------------------------------------------------------


class TestTTSProtocolMessages:
    """Tests for the new TTS protocol message types."""

    def test_join_meeting_tts_defaults(self) -> None:
        """JoinMeeting TTS fields default to disabled."""
        from agent_gateway.protocol import JoinMeeting

        msg = JoinMeeting(meeting_id=uuid4())
        assert msg.tts_enabled is False
        assert msg.tts_voice is None

    def test_join_meeting_tts_enabled(self) -> None:
        """JoinMeeting accepts tts_enabled and tts_voice."""
        from agent_gateway.protocol import JoinMeeting

        msg = JoinMeeting(
            meeting_id=uuid4(),
            tts_enabled=True,
            tts_voice="en_US-amy-medium",
        )
        assert msg.tts_enabled is True
        assert msg.tts_voice == "en_US-amy-medium"

    def test_start_speaking_type(self) -> None:
        """StartSpeaking has the correct type literal."""
        from agent_gateway.protocol import StartSpeaking

        msg = StartSpeaking()
        assert msg.type == "start_speaking"

    def test_spoken_text_type(self) -> None:
        """SpokenText has the correct type literal and text field."""
        from agent_gateway.protocol import SpokenText

        msg = SpokenText(text="Hello, I am an AI agent.")
        assert msg.type == "spoken_text"
        assert msg.text == "Hello, I am an AI agent."

    def test_stop_speaking_type(self) -> None:
        """StopSpeaking has the correct type literal."""
        from agent_gateway.protocol import StopSpeaking

        msg = StopSpeaking()
        assert msg.type == "stop_speaking"

    def test_start_speaking_parses(self) -> None:
        """start_speaking parses via parse_client_message."""
        from agent_gateway.protocol import StartSpeaking, parse_client_message

        msg = parse_client_message({"type": "start_speaking"})
        assert isinstance(msg, StartSpeaking)

    def test_spoken_text_parses(self) -> None:
        """spoken_text parses via parse_client_message."""
        from agent_gateway.protocol import SpokenText, parse_client_message

        msg = parse_client_message({"type": "spoken_text", "text": "Hi there"})
        assert isinstance(msg, SpokenText)
        assert msg.text == "Hi there"

    def test_stop_speaking_parses(self) -> None:
        """stop_speaking parses via parse_client_message."""
        from agent_gateway.protocol import StopSpeaking, parse_client_message

        msg = parse_client_message({"type": "stop_speaking"})
        assert isinstance(msg, StopSpeaking)
