"""Tests for RedisChatStore provider."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from convene_core.models.chat import ChatMessage, ChatMessageType
from convene_providers.chat.redis_chat_store import CHAT_PUBSUB_CHANNEL, RedisChatStore

MEETING_ID = uuid4()
SENDER_A = uuid4()
SENDER_B = uuid4()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Async mock simulating a redis.asyncio.Redis client."""
    redis = AsyncMock()
    redis.xadd = AsyncMock(return_value="1710000000000-0")
    redis.xrange = AsyncMock(return_value=[])
    redis.xrevrange = AsyncMock(return_value=[])
    redis.publish = AsyncMock(return_value=1)
    redis.delete = AsyncMock(return_value=1)
    redis.aclose = AsyncMock()
    return redis


@pytest.fixture
def store(mock_redis: AsyncMock) -> RedisChatStore:
    """RedisChatStore with mocked Redis client."""
    s = RedisChatStore(redis_url="redis://localhost/0")
    s._redis = mock_redis
    return s


# ---------------------------------------------------------------------------
# Key helper
# ---------------------------------------------------------------------------


class TestStreamKey:
    """Tests for the static stream key helper."""

    def test_includes_meeting_id(self) -> None:
        """Stream key includes the meeting UUID."""
        key = RedisChatStore._stream_key(MEETING_ID)
        assert str(MEETING_ID) in key

    def test_key_prefix(self) -> None:
        """Stream key starts with 'chat:'."""
        key = RedisChatStore._stream_key(MEETING_ID)
        assert key.startswith("chat:")

    def test_key_suffix(self) -> None:
        """Stream key ends with ':messages'."""
        key = RedisChatStore._stream_key(MEETING_ID)
        assert key.endswith(":messages")


# ---------------------------------------------------------------------------
# send_message
# ---------------------------------------------------------------------------


class TestSendMessage:
    """Tests for send_message operations."""

    async def test_returns_chat_message(self, store: RedisChatStore) -> None:
        """send_message returns a ChatMessage with correct fields."""
        msg = await store.send_message(
            meeting_id=MEETING_ID,
            sender_id=SENDER_A,
            sender_name="Agent Alpha",
            content="Hello from the test",
        )

        assert isinstance(msg, ChatMessage)
        assert msg.meeting_id == MEETING_ID
        assert msg.sender_id == SENDER_A
        assert msg.sender_name == "Agent Alpha"
        assert msg.content == "Hello from the test"
        assert msg.message_type == ChatMessageType.TEXT

    async def test_default_message_type_is_text(self, store: RedisChatStore) -> None:
        """Default message_type is TEXT."""
        msg = await store.send_message(
            meeting_id=MEETING_ID,
            sender_id=SENDER_A,
            sender_name="Agent",
            content="hi",
        )
        assert msg.message_type == ChatMessageType.TEXT

    async def test_explicit_message_type(self, store: RedisChatStore) -> None:
        """Explicit message_type is preserved on the returned message."""
        msg = await store.send_message(
            meeting_id=MEETING_ID,
            sender_id=SENDER_A,
            sender_name="Agent",
            content="We decided to proceed",
            message_type=ChatMessageType.DECISION,
        )
        assert msg.message_type == ChatMessageType.DECISION

    async def test_xadd_called_with_correct_fields(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """xadd is called with all required message fields."""
        await store.send_message(
            meeting_id=MEETING_ID,
            sender_id=SENDER_A,
            sender_name="Agent",
            content="Test content",
        )

        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        stream_key = call_args.args[0]
        fields = call_args.args[1]

        assert str(MEETING_ID) in stream_key
        assert "message_id" in fields
        assert fields["sender_id"] == str(SENDER_A)
        assert fields["sender_name"] == "Agent"
        assert fields["content"] == "Test content"
        assert fields["message_type"] == "text"
        assert "sent_at" in fields

    async def test_publish_called_after_xadd(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """publish is called with CHAT_PUBSUB_CHANNEL after xadd."""
        await store.send_message(
            meeting_id=MEETING_ID,
            sender_id=SENDER_A,
            sender_name="Agent",
            content="Broadcast test",
        )

        mock_redis.publish.assert_called_once()
        channel = mock_redis.publish.call_args.args[0]
        assert channel == CHAT_PUBSUB_CHANNEL

    async def test_publish_payload_contains_meeting_id(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """Pub/sub payload includes the meeting_id for routing."""
        await store.send_message(
            meeting_id=MEETING_ID,
            sender_id=SENDER_A,
            sender_name="Agent",
            content="Routing test",
        )

        payload_str = mock_redis.publish.call_args.args[1]
        payload = json.loads(payload_str)
        assert payload["meeting_id"] == str(MEETING_ID)

    async def test_sequence_from_stream_entry_id(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """Sequence is parsed from the Redis stream entry ID timestamp."""
        mock_redis.xadd.return_value = "1710500000000-0"

        msg = await store.send_message(
            meeting_id=MEETING_ID,
            sender_id=SENDER_A,
            sender_name="Agent",
            content="Sequence test",
        )

        assert msg.sequence == 1710500000000

    async def test_message_id_is_unique(self, store: RedisChatStore) -> None:
        """Each send_message call produces a unique message_id."""
        msg1 = await store.send_message(
            meeting_id=MEETING_ID,
            sender_id=SENDER_A,
            sender_name="A",
            content="first",
        )
        msg2 = await store.send_message(
            meeting_id=MEETING_ID,
            sender_id=SENDER_A,
            sender_name="A",
            content="second",
        )
        assert msg1.message_id != msg2.message_id


# ---------------------------------------------------------------------------
# get_messages
# ---------------------------------------------------------------------------


def _make_stream_entry(
    ts_ms: int,
    sender_id: str | None = None,
    sender_name: str = "Agent",
    content: str = "hello",
    message_type: str = "text",
) -> tuple[str, dict[str, str]]:
    """Build a fake Redis stream entry tuple."""
    mid = str(uuid4())
    sid = sender_id or str(uuid4())
    return (
        f"{ts_ms}-0",
        {
            "message_id": mid,
            "sender_id": sid,
            "sender_name": sender_name,
            "content": content,
            "message_type": message_type,
            "sent_at": datetime.now(tz=UTC).isoformat(),
        },
    )


class TestGetMessages:
    """Tests for get_messages operations."""

    async def test_empty_stream_returns_empty_list(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """Returns empty list when the stream has no messages."""
        mock_redis.xrevrange.return_value = []

        result = await store.get_messages(MEETING_ID)

        assert result == []

    async def test_returns_messages_in_chronological_order(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """Messages are returned oldest-first (chronological) without since."""
        # xrevrange returns newest first; store reverses them
        entry_old = _make_stream_entry(1710000000000, content="older")
        entry_new = _make_stream_entry(1710000001000, content="newer")
        mock_redis.xrevrange.return_value = [entry_new, entry_old]

        result = await store.get_messages(MEETING_ID)

        assert len(result) == 2
        assert result[0].content == "older"
        assert result[1].content == "newer"

    async def test_limit_respected(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """Limit parameter is passed to xrevrange."""
        mock_redis.xrevrange.return_value = []

        await store.get_messages(MEETING_ID, limit=10)

        call_kwargs = mock_redis.xrevrange.call_args
        assert call_kwargs.kwargs.get("count") == 10 or call_kwargs.args[3:] == (10,)

    async def test_message_type_filter(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """message_type filter excludes non-matching messages."""
        entries = [
            _make_stream_entry(1710000000000, message_type="text"),
            _make_stream_entry(1710000001000, message_type="decision"),
            _make_stream_entry(1710000002000, message_type="text"),
        ]
        mock_redis.xrevrange.return_value = list(reversed(entries))

        result = await store.get_messages(
            MEETING_ID, message_type=ChatMessageType.DECISION
        )

        assert len(result) == 1
        assert result[0].message_type == ChatMessageType.DECISION

    async def test_since_uses_xrange(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """When since is provided, xrange is used (not xrevrange)."""
        since = datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)
        mock_redis.xrange.return_value = []

        await store.get_messages(MEETING_ID, since=since)

        mock_redis.xrange.assert_called_once()
        mock_redis.xrevrange.assert_not_called()

    async def test_since_converts_to_ms_id(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """since datetime is correctly converted to a Redis stream ID."""
        since = datetime(2026, 3, 10, 12, 0, 0, tzinfo=UTC)
        mock_redis.xrange.return_value = []

        await store.get_messages(MEETING_ID, since=since)

        call_args = mock_redis.xrange.call_args
        min_id: str = call_args.kwargs.get("min") or call_args.args[1]
        expected_ms = int(since.timestamp() * 1000)
        assert min_id == f"{expected_ms}-0"

    async def test_malformed_entry_skipped(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """Malformed stream entries are skipped without raising."""
        good = _make_stream_entry(1710000001000, content="good")
        bad_entry_id = "1710000000000-0"
        bad_fields: dict[str, str] = {}  # missing required fields
        mock_redis.xrevrange.return_value = [good, (bad_entry_id, bad_fields)]

        result = await store.get_messages(MEETING_ID)

        assert len(result) == 1
        assert result[0].content == "good"


# ---------------------------------------------------------------------------
# clear_meeting
# ---------------------------------------------------------------------------


class TestClearMeeting:
    """Tests for clear_meeting operations."""

    async def test_deletes_stream_key(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """clear_meeting calls delete on the stream key."""
        await store.clear_meeting(MEETING_ID)

        mock_redis.delete.assert_called_once_with(
            RedisChatStore._stream_key(MEETING_ID)
        )

    async def test_correct_meeting_key_deleted(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """Only the specified meeting's stream key is deleted."""
        other_meeting = uuid4()
        await store.clear_meeting(other_meeting)

        deleted_key: str = mock_redis.delete.call_args.args[0]
        assert str(other_meeting) in deleted_key
        assert str(MEETING_ID) not in deleted_key


# ---------------------------------------------------------------------------
# close
# ---------------------------------------------------------------------------


class TestClose:
    """Tests for close operation."""

    async def test_closes_redis_connection(
        self, store: RedisChatStore, mock_redis: AsyncMock
    ) -> None:
        """close() calls aclose on the underlying Redis client."""
        await store.close()
        mock_redis.aclose.assert_called_once()

    async def test_idempotent_close(self, store: RedisChatStore) -> None:
        """Calling close twice does not raise."""
        await store.close()
        await store.close()  # Should not raise


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    """Tests that RedisChatStore is registered in the default registry."""

    def test_registered(self) -> None:
        """RedisChatStore is available in the default registry."""
        from convene_providers.registry import ProviderType, default_registry

        assert default_registry.is_registered(ProviderType.CHAT_STORE, "redis")

    def test_create_from_registry(self) -> None:
        """Registry can instantiate a RedisChatStore."""
        from convene_providers.registry import ProviderType, default_registry

        instance = default_registry.create(
            ProviderType.CHAT_STORE,
            "redis",
            redis_url="redis://localhost/0",
        )
        assert isinstance(instance, RedisChatStore)
