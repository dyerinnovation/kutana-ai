"""Unit tests for StreamConsumer.

All tests use mocked Redis so no live server is required.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import ResponseError

from kutana_core.models.transcript import TranscriptSegment
from task_engine.stream_consumer import (
    DEFAULT_GROUP_NAME,
    DEFAULT_STREAM_KEY,
    StreamConsumer,
)

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_segment(meeting_id: Any = None) -> TranscriptSegment:
    """Create a minimal TranscriptSegment for testing."""
    return TranscriptSegment(
        meeting_id=meeting_id or uuid4(),
        speaker_id="spk_0",
        text="Alice will send the report by Friday.",
        start_time=0.0,
        end_time=5.0,
        confidence=0.95,
    )


def _segment_event_entry(segment: TranscriptSegment) -> tuple[str, dict[str, str]]:
    """Build a Redis stream entry tuple for a transcript.segment.final event."""
    from kutana_core.events.definitions import TranscriptSegmentFinal

    event = TranscriptSegmentFinal(
        meeting_id=segment.meeting_id,
        segment=segment,
    )
    payload = json.dumps(event.to_dict(), default=str)
    return ("1-0", {"event_type": "transcript.segment.final", "payload": payload})


def _other_event_entry(event_type: str = "meeting.started") -> tuple[str, dict[str, str]]:
    """Build a Redis stream entry for a non-segment event."""
    payload = json.dumps({"meeting_id": str(uuid4()), "event_type": event_type})
    return ("2-0", {"event_type": event_type, "payload": payload})


def _make_consumer(
    on_segment: Any = None,
    **kwargs: Any,
) -> StreamConsumer:
    """Construct a StreamConsumer with a mock on_segment callback."""
    if on_segment is None:
        on_segment = AsyncMock()
    return StreamConsumer(
        redis_url="redis://localhost:6379/0",
        on_segment=on_segment,
        consumer_name="test-worker",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Initialisation tests
# ---------------------------------------------------------------------------


class TestStreamConsumerInit:
    """Tests for StreamConsumer construction."""

    def test_defaults(self) -> None:
        """Default stream key and group name are set correctly."""
        consumer = _make_consumer()
        assert consumer._stream_key == DEFAULT_STREAM_KEY
        assert consumer._group_name == DEFAULT_GROUP_NAME

    def test_custom_group_and_stream(self) -> None:
        """Custom group and stream key are stored."""
        consumer = _make_consumer(
            group_name="my-group",
            stream_key="my:stream",
        )
        assert consumer._group_name == "my-group"
        assert consumer._stream_key == "my:stream"

    def test_consumer_name_explicit(self) -> None:
        """Explicit consumer name is used as-is."""
        consumer = StreamConsumer(
            redis_url="redis://localhost:6379/0",
            on_segment=AsyncMock(),
            consumer_name="explicit-name",
        )
        assert consumer._consumer_name == "explicit-name"

    def test_consumer_name_defaults_to_hostname(self) -> None:
        """Omitting consumer_name falls back to worker-<hostname>."""
        import socket

        consumer = StreamConsumer(
            redis_url="redis://localhost:6379/0",
            on_segment=AsyncMock(),
        )
        assert consumer._consumer_name == f"worker-{socket.gethostname()}"

    def test_stop_event_initially_clear(self) -> None:
        """Stop event is not set at construction time."""
        consumer = _make_consumer()
        assert not consumer._stop_event.is_set()

    def test_redis_client_initially_none(self) -> None:
        """Redis client is None before start() is called."""
        consumer = _make_consumer()
        assert consumer._redis is None


# ---------------------------------------------------------------------------
# _ensure_group tests
# ---------------------------------------------------------------------------


class TestEnsureGroup:
    """Tests for _ensure_group."""

    async def test_creates_group_when_absent(self) -> None:
        """xgroup_create is called with correct arguments."""
        consumer = _make_consumer()
        mock_redis = AsyncMock()
        consumer._redis = mock_redis

        await consumer._ensure_group()

        mock_redis.xgroup_create.assert_called_once_with(
            DEFAULT_STREAM_KEY,
            DEFAULT_GROUP_NAME,
            id="$",
            mkstream=True,
        )

    async def test_ignores_busygroup_error(self) -> None:
        """BUSYGROUP ResponseError is silently swallowed."""
        consumer = _make_consumer()
        mock_redis = AsyncMock()
        mock_redis.xgroup_create.side_effect = ResponseError("BUSYGROUP Consumer Group already exists")
        consumer._redis = mock_redis

        # Should not raise
        await consumer._ensure_group()

    async def test_reraises_other_response_errors(self) -> None:
        """Non-BUSYGROUP ResponseError propagates."""
        consumer = _make_consumer()
        mock_redis = AsyncMock()
        mock_redis.xgroup_create.side_effect = ResponseError("ERR unknown command")
        consumer._redis = mock_redis

        with pytest.raises(ResponseError, match="ERR unknown command"):
            await consumer._ensure_group()


# ---------------------------------------------------------------------------
# _handle_entry tests
# ---------------------------------------------------------------------------


class TestHandleEntry:
    """Tests for _handle_entry — the per-message processing logic."""

    async def test_calls_on_segment_for_matching_event(self) -> None:
        """on_segment callback is invoked with correct segment."""
        on_segment = AsyncMock()
        consumer = _make_consumer(on_segment=on_segment)
        consumer._redis = AsyncMock()

        segment = _make_segment()
        entry_id, fields = _segment_event_entry(segment)

        await consumer._handle_entry(entry_id, fields)

        on_segment.assert_called_once()
        received: TranscriptSegment = on_segment.call_args[0][0]
        assert received.text == segment.text
        assert received.meeting_id == segment.meeting_id

    async def test_acknowledges_segment_entry(self) -> None:
        """xack is called after on_segment completes."""
        consumer = _make_consumer()
        mock_redis = AsyncMock()
        consumer._redis = mock_redis

        entry_id, fields = _segment_event_entry(_make_segment())
        await consumer._handle_entry(entry_id, fields)

        mock_redis.xack.assert_called_once_with(
            DEFAULT_STREAM_KEY, DEFAULT_GROUP_NAME, entry_id
        )

    async def test_skips_non_segment_events(self) -> None:
        """Non-segment events are acknowledged and the callback is not called."""
        on_segment = AsyncMock()
        consumer = _make_consumer(on_segment=on_segment)
        mock_redis = AsyncMock()
        consumer._redis = mock_redis

        entry_id, fields = _other_event_entry("meeting.started")
        await consumer._handle_entry(entry_id, fields)

        on_segment.assert_not_called()
        mock_redis.xack.assert_called_once_with(
            DEFAULT_STREAM_KEY, DEFAULT_GROUP_NAME, entry_id
        )

    async def test_acknowledges_on_parse_error(self) -> None:
        """Malformed JSON payload is acknowledged to avoid PEL build-up."""
        consumer = _make_consumer()
        mock_redis = AsyncMock()
        consumer._redis = mock_redis

        bad_fields = {"event_type": "transcript.segment.final", "payload": "NOT JSON{{{"}
        await consumer._handle_entry("5-0", bad_fields)

        mock_redis.xack.assert_called_once()

    async def test_acknowledges_when_on_segment_raises(self) -> None:
        """Entry is still ACKed when the callback raises, avoiding repeated delivery."""
        on_segment = AsyncMock(side_effect=RuntimeError("extraction failed"))
        consumer = _make_consumer(on_segment=on_segment)
        mock_redis = AsyncMock()
        consumer._redis = mock_redis

        entry_id, fields = _segment_event_entry(_make_segment())
        # Should not propagate the callback exception
        await consumer._handle_entry(entry_id, fields)

        mock_redis.xack.assert_called_once_with(
            DEFAULT_STREAM_KEY, DEFAULT_GROUP_NAME, entry_id
        )

    async def test_missing_event_type_field_treated_as_skip(self) -> None:
        """Entry with no event_type field is treated as unknown and ACKed."""
        consumer = _make_consumer()
        mock_redis = AsyncMock()
        consumer._redis = mock_redis

        await consumer._handle_entry("9-0", {"payload": "{}"})

        mock_redis.xack.assert_called_once()


# ---------------------------------------------------------------------------
# stop() tests
# ---------------------------------------------------------------------------


class TestStop:
    """Tests for stop() behaviour."""

    async def test_sets_stop_event(self) -> None:
        """stop() signals the internal event."""
        consumer = _make_consumer()
        assert not consumer._stop_event.is_set()
        await consumer.stop()
        assert consumer._stop_event.is_set()

    async def test_stop_before_start_does_not_raise(self) -> None:
        """Calling stop() before start() is safe."""
        consumer = _make_consumer()
        # No exception expected
        await consumer.stop()


# ---------------------------------------------------------------------------
# _consume_loop tests
# ---------------------------------------------------------------------------


class TestConsumeLoop:
    """Tests for the main consume loop."""

    async def test_processes_entries_from_xreadgroup(self) -> None:
        """Loop calls on_segment for each segment entry returned by xreadgroup."""
        on_segment = AsyncMock()
        consumer = _make_consumer(on_segment=on_segment)
        mock_redis = AsyncMock()
        consumer._redis = mock_redis

        segment = _make_segment()
        entry_id, fields = _segment_event_entry(segment)

        call_count = 0

        async def fake_xreadgroup(**kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [(DEFAULT_STREAM_KEY, [(entry_id, fields)])]
            # Stop after first batch
            consumer._stop_event.set()
            return None

        mock_redis.xreadgroup = fake_xreadgroup

        await consumer._consume_loop()

        on_segment.assert_called_once()

    async def test_loop_exits_when_stop_event_set(self) -> None:
        """Loop exits without processing when stop event is already set."""
        on_segment = AsyncMock()
        consumer = _make_consumer(on_segment=on_segment)
        consumer._redis = AsyncMock()
        consumer._stop_event.set()

        await consumer._consume_loop()

        on_segment.assert_not_called()

    async def test_loop_handles_cancellation(self) -> None:
        """CancelledError from xreadgroup is propagated cleanly."""
        consumer = _make_consumer()
        mock_redis = AsyncMock()
        mock_redis.xreadgroup.side_effect = asyncio.CancelledError
        consumer._redis = mock_redis

        with pytest.raises(asyncio.CancelledError):
            await consumer._consume_loop()

    async def test_loop_reconnects_after_connection_error(self) -> None:
        """RedisConnectionError triggers a reconnect and the loop continues."""
        on_segment = AsyncMock()
        consumer = _make_consumer(on_segment=on_segment)
        mock_redis = AsyncMock()
        consumer._redis = mock_redis

        call_count = 0

        async def fake_xreadgroup(**kwargs: Any) -> Any:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RedisConnectionError("Connection refused")
            # After reconnect, stop cleanly
            consumer._stop_event.set()
            return None

        mock_redis.xreadgroup = fake_xreadgroup

        with (
            patch("task_engine.stream_consumer.redis") as mock_redis_module,
            patch.object(consumer, "_close_redis", new_callable=AsyncMock),
            patch.object(consumer, "_ensure_group", new_callable=AsyncMock),
        ):
            new_client = AsyncMock()
            new_client.xreadgroup = fake_xreadgroup
            mock_redis_module.from_url.return_value = new_client
            # Use a very short sleep to keep tests fast
            with patch("asyncio.sleep", new_callable=AsyncMock):
                await consumer._consume_loop()

        assert call_count >= 2


# ---------------------------------------------------------------------------
# start() integration-style test
# ---------------------------------------------------------------------------


class TestStart:
    """Integration-style tests for start()."""

    async def test_start_creates_group_and_enters_loop(self) -> None:
        """start() calls _ensure_group then _consume_loop."""
        consumer = _make_consumer()

        with (
            patch("task_engine.stream_consumer.redis") as mock_redis_module,
            patch.object(consumer, "_ensure_group", new_callable=AsyncMock) as mock_ensure,
            patch.object(consumer, "_consume_loop", new_callable=AsyncMock) as mock_loop,
        ):
            mock_redis_module.from_url.return_value = AsyncMock()
            await consumer.start()

        mock_ensure.assert_called_once()
        mock_loop.assert_called_once()

    async def test_start_closes_redis_on_exit(self) -> None:
        """Redis connection is closed when start() exits normally."""
        consumer = _make_consumer()
        mock_client = AsyncMock()

        with (
            patch("task_engine.stream_consumer.redis") as mock_redis_module,
            patch.object(consumer, "_ensure_group", new_callable=AsyncMock),
            patch.object(consumer, "_consume_loop", new_callable=AsyncMock),
        ):
            mock_redis_module.from_url.return_value = mock_client
            await consumer.start()

        mock_client.aclose.assert_called_once()


# ---------------------------------------------------------------------------
# Main settings tests
# ---------------------------------------------------------------------------


class TestTaskEngineSettings:
    """Tests for TaskEngineSettings defaults and consumer wiring."""

    def test_default_redis_url(self) -> None:
        """Default Redis URL points to localhost."""
        from task_engine.main import TaskEngineSettings

        settings = TaskEngineSettings()
        assert settings.redis_url == "redis://localhost:6379/0"

    def test_default_consumer_group(self) -> None:
        """Default consumer group name is task-engine."""
        from task_engine.main import TaskEngineSettings

        settings = TaskEngineSettings()
        assert settings.consumer_group == "task-engine"

    def test_env_var_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Settings can be overridden via environment variables."""
        from task_engine.main import TaskEngineSettings

        monkeypatch.setenv("REDIS_URL", "redis://redis-host:6380/1")
        monkeypatch.setenv("CONSUMER_GROUP", "my-group")
        monkeypatch.setenv("CONSUMER_NAME", "worker-42")

        settings = TaskEngineSettings()
        assert settings.redis_url == "redis://redis-host:6380/1"
        assert settings.consumer_group == "my-group"
        assert settings.consumer_name == "worker-42"
