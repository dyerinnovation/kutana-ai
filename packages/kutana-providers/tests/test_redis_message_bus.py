"""Tests for the RedisStreamsMessageBus provider."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

from kutana_core.messaging.abc import MessageBus
from kutana_core.messaging.types import Message, Subscription
from kutana_providers.messaging.redis_streams import (
    RedisStreamsMessageBus,
    create_message_bus_from_env,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis() -> AsyncMock:
    """Async mock that simulates a redis.asyncio.Redis client."""
    redis = AsyncMock()
    redis.xadd = AsyncMock(return_value="1234567890-0")
    redis.xreadgroup = AsyncMock(return_value=[])
    redis.xread = AsyncMock(return_value=[])
    redis.xgroup_create = AsyncMock()
    redis.xack = AsyncMock()
    redis.scan = AsyncMock(return_value=(0, []))
    redis.aclose = AsyncMock()
    return redis


@pytest.fixture
async def bus(mock_redis: AsyncMock) -> AsyncGenerator[RedisStreamsMessageBus, None]:
    """RedisStreamsMessageBus with a mocked Redis connection."""
    b = RedisStreamsMessageBus(url="redis://localhost:6379/0", poll_block_ms=50)
    b._redis = mock_redis
    yield b
    # Cleanup: cancel any background tasks without re-calling aclose
    b._subscriptions.clear()
    for task in b._tasks:
        task.cancel()
    if b._tasks:
        await asyncio.gather(*b._tasks, return_exceptions=True)
    b._tasks.clear()
    b._redis = None


# ---------------------------------------------------------------------------
# publish tests
# ---------------------------------------------------------------------------


class TestPublish:
    """Tests for RedisStreamsMessageBus.publish."""

    async def test_publish_returns_message_uuid(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """publish() returns the Message UUID, not the Redis stream entry ID."""
        mock_redis.xadd.return_value = "9999-0"
        msg_id = await bus.publish("test.topic", {"key": "value"})
        assert isinstance(msg_id, str)
        assert len(msg_id) == 36  # UUID format
        assert msg_id != "9999-0"

    async def test_publish_calls_xadd_with_topic_as_key(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """publish() uses the topic as the Redis stream key."""
        await bus.publish("meeting.events", {"x": 1})
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == "meeting.events"

    async def test_publish_serializes_payload_as_json(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """publish() JSON-encodes the payload in the stream entry."""
        await bus.publish("events", {"meeting_id": "abc", "count": 42})
        entry: dict[str, str] = mock_redis.xadd.call_args[0][1]
        assert json.loads(entry["payload"]) == {"meeting_id": "abc", "count": 42}

    async def test_publish_includes_metadata(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """publish() JSON-encodes metadata in the stream entry."""
        await bus.publish("events", {}, metadata={"region": "us-east-1"})
        entry: dict[str, str] = mock_redis.xadd.call_args[0][1]
        assert json.loads(entry["metadata"]) == {"region": "us-east-1"}

    async def test_publish_includes_source(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """publish() stores the source service in the stream entry."""
        await bus.publish("events", {}, source="audio-service")
        entry: dict[str, str] = mock_redis.xadd.call_args[0][1]
        assert entry["source"] == "audio-service"

    async def test_publish_stores_topic_in_entry(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """publish() stores the topic inside the stream entry fields."""
        await bus.publish("task.created", {})
        entry: dict[str, str] = mock_redis.xadd.call_args[0][1]
        assert entry["topic"] == "task.created"

    async def test_publish_empty_metadata_by_default(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """publish() stores empty metadata dict when none provided."""
        await bus.publish("t", {})
        entry: dict[str, str] = mock_redis.xadd.call_args[0][1]
        assert json.loads(entry["metadata"]) == {}

    async def test_publish_unique_message_ids(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """Each publish() call generates a distinct message ID."""
        ids = {await bus.publish("t", {}) for _ in range(10)}
        assert len(ids) == 10


# ---------------------------------------------------------------------------
# subscribe tests
# ---------------------------------------------------------------------------


class TestSubscribe:
    """Tests for RedisStreamsMessageBus.subscribe."""

    async def test_subscribe_returns_subscription(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """subscribe() returns a Subscription with the correct fields."""

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("test.topic", handler)
        assert isinstance(sub, Subscription)
        assert sub.topic == "test.topic"
        assert sub.group is None

    async def test_subscribe_without_group_no_xgroup_create(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """Fan-out subscribe (no group) does not call XGROUP CREATE."""

        async def handler(msg: Message) -> None:
            pass

        await bus.subscribe("events", handler)
        mock_redis.xgroup_create.assert_not_called()

    async def test_subscribe_with_group_calls_xgroup_create(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """subscribe(group=...) calls XGROUP CREATE on the stream."""

        async def handler(msg: Message) -> None:
            pass

        await bus.subscribe("events", handler, group="workers")
        mock_redis.xgroup_create.assert_called_once()
        call = mock_redis.xgroup_create.call_args
        assert call[0][0] == "events"
        assert call[0][1] == "workers"

    async def test_subscribe_with_group_ignores_existing_group_error(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """subscribe() does not raise if XGROUP CREATE fails (group exists)."""
        mock_redis.xgroup_create.side_effect = Exception(
            "BUSYGROUP Consumer Group name already exists"
        )

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("events", handler, group="workers")
        assert sub.group == "workers"  # subscription created despite error

    async def test_subscribe_creates_background_task(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """subscribe() creates a background asyncio task for polling."""

        async def handler(msg: Message) -> None:
            pass

        task_count_before = len(bus._tasks)
        await bus.subscribe("events", handler)
        assert len(bus._tasks) == task_count_before + 1

    async def test_subscribe_registers_in_subscriptions(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """subscribe() adds the Subscription to the internal registry."""

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("events", handler)
        assert sub.subscription_id in bus._subscriptions

    async def test_subscribe_pattern_no_xgroup_create_upfront(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """Pattern subscriptions defer group creation until streams are found."""

        async def handler(msg: Message) -> None:
            pass

        await bus.subscribe("meeting.*.events", handler, group="workers")
        # XGROUP CREATE is deferred to when matching streams are discovered
        mock_redis.xgroup_create.assert_not_called()


# ---------------------------------------------------------------------------
# unsubscribe tests
# ---------------------------------------------------------------------------


class TestUnsubscribe:
    """Tests for RedisStreamsMessageBus.unsubscribe."""

    async def test_unsubscribe_removes_from_subscriptions(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """unsubscribe() removes the subscription from the registry."""

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("test.topic", handler)
        assert sub.subscription_id in bus._subscriptions
        await bus.unsubscribe(sub)
        assert sub.subscription_id not in bus._subscriptions

    async def test_unsubscribe_nonexistent_is_safe(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """unsubscribe() with an unknown subscription does not raise."""

        async def handler(msg: Message) -> None:
            pass

        orphan = Subscription(topic="t", handler=handler)
        await bus.unsubscribe(orphan)  # should not raise


# ---------------------------------------------------------------------------
# ack tests
# ---------------------------------------------------------------------------


class TestAck:
    """Tests for RedisStreamsMessageBus.ack."""

    async def test_ack_calls_xack_for_group_subscription(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """ack() calls XACK for consumer group subscriptions."""

        async def handler(msg: Message) -> None:
            pass

        sub = Subscription(topic="events", handler=handler, group="workers")
        await bus.ack(sub, "msg-uuid-1234")
        mock_redis.xack.assert_called_once_with("events", "workers", "msg-uuid-1234")

    async def test_ack_noop_without_group(
        self, bus: RedisStreamsMessageBus, mock_redis: AsyncMock
    ) -> None:
        """ack() is a no-op for fan-out (non-group) subscriptions."""

        async def handler(msg: Message) -> None:
            pass

        sub = Subscription(topic="events", handler=handler, group=None)
        await bus.ack(sub, "msg-uuid-1234")
        mock_redis.xack.assert_not_called()


# ---------------------------------------------------------------------------
# close tests
# ---------------------------------------------------------------------------


class TestClose:
    """Tests for RedisStreamsMessageBus.close."""

    async def test_close_calls_redis_aclose(self, mock_redis: AsyncMock) -> None:
        """close() calls aclose() on the Redis client."""
        b = RedisStreamsMessageBus(url="redis://localhost:6379/0")
        b._redis = mock_redis
        await b.close()
        mock_redis.aclose.assert_called_once()

    async def test_close_sets_redis_to_none(self, mock_redis: AsyncMock) -> None:
        """close() sets _redis to None for idempotency."""
        b = RedisStreamsMessageBus(url="redis://localhost:6379/0")
        b._redis = mock_redis
        await b.close()
        assert b._redis is None

    async def test_close_clears_subscriptions(self, mock_redis: AsyncMock) -> None:
        """close() clears the active subscription registry."""
        b = RedisStreamsMessageBus(url="redis://localhost:6379/0", poll_block_ms=50)
        b._redis = mock_redis

        async def handler(msg: Message) -> None:
            pass

        await b.subscribe("events", handler)
        assert len(b._subscriptions) == 1
        await b.close()
        assert len(b._subscriptions) == 0

    async def test_close_is_idempotent(self, mock_redis: AsyncMock) -> None:
        """Calling close() twice does not raise."""
        b = RedisStreamsMessageBus(url="redis://localhost:6379/0")
        b._redis = mock_redis
        await b.close()
        await b.close()  # second call should be safe


# ---------------------------------------------------------------------------
# _parse_entry tests
# ---------------------------------------------------------------------------


class TestParseEntry:
    """Tests for internal _parse_entry deserialization."""

    def test_parse_entry_roundtrip(self, bus: RedisStreamsMessageBus) -> None:
        """_parse_entry correctly reconstructs a Message from a stream entry."""
        ts = datetime.now(tz=UTC)
        fields = {
            "message_id": "test-uuid-abcd-1234-efgh-5678",
            "topic": "meeting.started",
            "payload": json.dumps({"meeting_id": "m1", "name": "Standup"}),
            "metadata": json.dumps({"region": "eu-west-1"}),
            "timestamp": ts.isoformat(),
            "source": "api-server",
        }
        msg = bus._parse_entry(fields)
        assert msg.id == "test-uuid-abcd-1234-efgh-5678"
        assert msg.topic == "meeting.started"
        assert msg.payload == {"meeting_id": "m1", "name": "Standup"}
        assert msg.metadata == {"region": "eu-west-1"}
        assert msg.source == "api-server"

    def test_parse_entry_missing_fields_use_defaults(self, bus: RedisStreamsMessageBus) -> None:
        """_parse_entry handles missing fields gracefully."""
        msg = bus._parse_entry({})
        assert msg.topic == ""
        assert msg.payload == {}
        assert msg.metadata == {}
        assert msg.source == ""


# ---------------------------------------------------------------------------
# _make_entry / roundtrip tests
# ---------------------------------------------------------------------------


class TestMakeEntry:
    """Tests for internal _make_entry serialization."""

    def test_make_entry_contains_all_fields(self, bus: RedisStreamsMessageBus) -> None:
        """_make_entry produces a dict with all required stream fields."""
        msg = Message(
            topic="task.created",
            payload={"id": "t1"},
            metadata={"x": "y"},
            source="task-engine",
        )
        entry = bus._make_entry(msg)
        assert entry["message_id"] == msg.id
        assert entry["topic"] == "task.created"
        assert json.loads(entry["payload"]) == {"id": "t1"}
        assert json.loads(entry["metadata"]) == {"x": "y"}
        assert entry["source"] == "task-engine"
        assert "timestamp" in entry

    def test_make_parse_roundtrip(self, bus: RedisStreamsMessageBus) -> None:
        """_make_entry + _parse_entry reconstructs the original Message."""
        original = Message(
            topic="agent.joined",
            payload={"agent_id": "a1", "room": "main"},
            metadata={"env": "prod"},
            source="agent-gateway",
        )
        entry = bus._make_entry(original)
        restored = bus._parse_entry(entry)
        assert restored.id == original.id
        assert restored.topic == original.topic
        assert restored.payload == original.payload
        assert restored.metadata == original.metadata
        assert restored.source == original.source


# ---------------------------------------------------------------------------
# Registry integration tests
# ---------------------------------------------------------------------------


class TestRegistryIntegration:
    """Tests that RedisStreamsMessageBus is registered in the default registry."""

    def test_redis_bus_in_default_registry(self) -> None:
        """RedisStreamsMessageBus is registered as 'redis' in the registry."""
        from kutana_providers.registry import ProviderType, default_registry

        providers = default_registry.list_providers(ProviderType.MESSAGE_BUS)
        assert "redis" in providers

    def test_create_redis_bus_from_registry(self) -> None:
        """default_registry.create(MESSAGE_BUS, 'redis') returns correct type."""
        from kutana_providers.registry import ProviderType, default_registry

        bus = default_registry.create(ProviderType.MESSAGE_BUS, "redis")
        assert isinstance(bus, RedisStreamsMessageBus)
        assert isinstance(bus, MessageBus)

    def test_registry_create_passes_kwargs(self) -> None:
        """kwargs are forwarded to RedisStreamsMessageBus constructor."""
        from kutana_providers.registry import ProviderType, default_registry

        bus = default_registry.create(
            ProviderType.MESSAGE_BUS,
            "redis",
            url="redis://myhost:6380/1",
            consumer_name="test-consumer",
        )
        assert bus._url == "redis://myhost:6380/1"
        assert bus._consumer_name == "test-consumer"


# ---------------------------------------------------------------------------
# create_message_bus_from_env tests
# ---------------------------------------------------------------------------


class TestCreateFromEnv:
    """Tests for the create_message_bus_from_env helper."""

    def test_defaults_to_redis(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returns a RedisStreamsMessageBus when KUTANA_MESSAGE_BUS is unset."""
        monkeypatch.delenv("KUTANA_MESSAGE_BUS", raising=False)
        monkeypatch.delenv("REDIS_URL", raising=False)
        bus = create_message_bus_from_env()
        assert isinstance(bus, RedisStreamsMessageBus)
        assert bus._url == "redis://localhost:6379/0"

    def test_respects_redis_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Uses REDIS_URL when set."""
        monkeypatch.setenv("KUTANA_MESSAGE_BUS", "redis")
        monkeypatch.setenv("REDIS_URL", "redis://prod-redis:6379/2")
        bus = create_message_bus_from_env()
        assert bus._url == "redis://prod-redis:6379/2"

    def test_unsupported_backend_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raises ValueError for unsupported KUTANA_MESSAGE_BUS values."""
        monkeypatch.setenv("KUTANA_MESSAGE_BUS", "kafka")
        with pytest.raises(ValueError, match="Unsupported"):
            create_message_bus_from_env()
