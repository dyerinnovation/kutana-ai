"""Tests for the PubSubMessageBus provider (mocked GCP Pub/Sub clients)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kutana_core.messaging.abc import MessageBus
from kutana_core.messaging.types import Message, Subscription

# ---------------------------------------------------------------------------
# Helpers: build mock Pub/Sub clients
# ---------------------------------------------------------------------------


def _make_publisher(
    topic_path: str = "projects/test-project/topics/kutana-test_topic",
) -> AsyncMock:
    """Build a mock PublisherAsyncClient."""
    publisher = AsyncMock()
    publisher.create_topic = AsyncMock(return_value=MagicMock(name=topic_path))
    publisher.publish = AsyncMock(return_value="mock-message-id")
    # Transport for close()
    publisher.transport = MagicMock()
    publisher.transport.close = AsyncMock()
    return publisher


def _make_subscriber(
    subscription_path: str = "projects/test-project/subscriptions/kutana-test_topic--workers",
    messages: list[Any] | None = None,
) -> AsyncMock:
    """Build a mock SubscriberAsyncClient."""
    subscriber = AsyncMock()
    subscriber.create_subscription = AsyncMock()
    subscriber.acknowledge = AsyncMock()

    # pull() returns a response with ReceivedMessage objects
    received = []
    for msg_data in (messages or []):
        rm = MagicMock()
        rm.ack_id = f"ack-{id(msg_data)}"
        rm.message = MagicMock()
        rm.message.data = json.dumps(msg_data).encode("utf-8")
        received.append(rm)

    pull_response = MagicMock()
    pull_response.received_messages = received
    subscriber.pull = AsyncMock(return_value=pull_response)

    # list_subscriptions() — async iterable
    async def _list_subs(*args: Any, **kwargs: Any) -> Any:
        yield MagicMock(topic="projects/test-project/topics/kutana-test_topic")

    subscriber.list_subscriptions = _list_subs

    subscriber.transport = MagicMock()
    subscriber.transport.close = AsyncMock()
    return subscriber


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def publisher() -> AsyncMock:
    return _make_publisher()


@pytest.fixture
def subscriber() -> AsyncMock:
    return _make_subscriber()


@pytest.fixture
def bus(publisher: AsyncMock, subscriber: AsyncMock) -> Any:
    """Return a PubSubMessageBus with mocked GCP clients."""
    from kutana_providers.messaging.gcp_pubsub import PubSubMessageBus

    b = PubSubMessageBus(project_id="test-project", topic_prefix="kutana-")
    b._publisher = publisher
    b._subscriber = subscriber
    return b


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------


class TestPubSubImportGuard:
    """Tests that the ImportError guard works when google-cloud-pubsub is absent."""

    def test_raises_import_error_when_pubsub_missing(self) -> None:
        """PubSubMessageBus raises ImportError if google-cloud-pubsub is missing."""
        with patch(
            "kutana_providers.messaging.gcp_pubsub._PUBSUB_AVAILABLE", False
        ):
            from kutana_providers.messaging.gcp_pubsub import _require_pubsub

            with pytest.raises(ImportError, match="google-cloud-pubsub"):
                _require_pubsub()


class TestPubSubNaming:
    """Tests for Pub/Sub topic/subscription name helpers."""

    def test_topic_name_replaces_wildcards(self) -> None:
        from kutana_providers.messaging.gcp_pubsub import _topic_to_pubsub_name

        result = _topic_to_pubsub_name("meeting.*.events", "kutana-")
        assert "*" not in result

    def test_subscription_name_contains_topic_and_group(self) -> None:
        from kutana_providers.messaging.gcp_pubsub import _subscription_name_for_group

        result = _subscription_name_for_group("meeting.events", "workers", "kutana-")
        assert "workers" in result

    def test_subscription_name_max_255_chars(self) -> None:
        from kutana_providers.messaging.gcp_pubsub import _subscription_name_for_group

        result = _subscription_name_for_group("a" * 200, "b" * 200, "c-")
        assert len(result) <= 255


class TestPubSubPublish:
    """Tests for PubSubMessageBus.publish."""

    async def test_publish_creates_topic(
        self, bus: Any, publisher: AsyncMock
    ) -> None:
        """publish() calls publisher.create_topic."""
        await bus.publish("test.topic", {"x": 1})
        publisher.create_topic.assert_called_once()

    async def test_publish_returns_uuid_string(
        self, bus: Any
    ) -> None:
        """publish() returns a 36-char UUID."""
        msg_id = await bus.publish("test.topic", {})
        assert isinstance(msg_id, str)
        assert len(msg_id) == 36

    async def test_publish_sends_encoded_json(
        self, bus: Any, publisher: AsyncMock
    ) -> None:
        """publish() sends UTF-8 JSON to the Pub/Sub publisher."""
        await bus.publish("t", {"answer": 42}, source="test-svc")
        call_kwargs = publisher.publish.call_args[1]
        body = json.loads(call_kwargs["data"].decode("utf-8"))
        assert body["payload"] == {"answer": 42}
        assert body["source"] == "test-svc"

    async def test_publish_caches_topic_path(
        self, bus: Any, publisher: AsyncMock
    ) -> None:
        """publish() only creates the topic once per unique topic string."""
        await bus.publish("my.topic", {})
        await bus.publish("my.topic", {})
        assert publisher.create_topic.call_count == 1

    async def test_publish_unique_message_ids(self, bus: Any) -> None:
        """Each publish() generates a distinct message UUID."""
        ids = {await bus.publish("t", {}) for _ in range(5)}
        assert len(ids) == 5

    async def test_publish_implements_message_bus_abc(self, bus: Any) -> None:
        """PubSubMessageBus is a subclass of MessageBus."""
        assert isinstance(bus, MessageBus)


class TestPubSubSubscribe:
    """Tests for PubSubMessageBus.subscribe."""

    async def test_subscribe_returns_subscription(
        self, bus: Any
    ) -> None:
        """subscribe() returns a Subscription with correct topic."""

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("test.topic", handler)
        assert isinstance(sub, Subscription)
        assert sub.topic == "test.topic"

        bus._subscriptions.clear()
        for t in bus._tasks:
            t.cancel()
        import asyncio
        await asyncio.gather(*bus._tasks, return_exceptions=True)

    async def test_subscribe_creates_pubsub_subscription(
        self, bus: Any, subscriber: AsyncMock
    ) -> None:
        """subscribe() calls subscriber.create_subscription."""

        async def handler(msg: Message) -> None:
            pass

        await bus.subscribe("test.topic", handler, group="workers")
        subscriber.create_subscription.assert_called_once()

        bus._subscriptions.clear()
        for t in bus._tasks:
            t.cancel()
        import asyncio
        await asyncio.gather(*bus._tasks, return_exceptions=True)

    async def test_subscribe_with_group_sets_group(
        self, bus: Any
    ) -> None:
        """subscribe(group=...) sets the group on the Subscription."""

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("t", handler, group="my-group")
        assert sub.group == "my-group"

        bus._subscriptions.clear()
        for t in bus._tasks:
            t.cancel()
        import asyncio
        await asyncio.gather(*bus._tasks, return_exceptions=True)


class TestPubSubAck:
    """Tests for PubSubMessageBus.ack."""

    async def test_ack_noop_for_fanout_subscription(
        self, bus: Any, subscriber: AsyncMock
    ) -> None:
        """ack() is a no-op for fan-out (group=None) subscriptions."""

        async def handler(msg: Message) -> None:
            pass

        sub = Subscription(topic="t", handler=handler, group=None)
        await bus.ack(sub, "ack-id-123")
        subscriber.acknowledge.assert_not_called()

    async def test_ack_calls_acknowledge_for_group_subscription(
        self, bus: Any, subscriber: AsyncMock
    ) -> None:
        """ack() calls subscriber.acknowledge for group subscriptions."""

        async def handler(msg: Message) -> None:
            pass

        sub = Subscription(topic="test.topic", handler=handler, group="workers")
        # Pre-populate the sub_path cache
        bus._sub_paths["test.topic::workers"] = (
            "projects/test-project/subscriptions/kutana-test_topic--workers"
        )
        await bus.ack(sub, "ack-id-xyz")
        subscriber.acknowledge.assert_called_once()


class TestPubSubClose:
    """Tests for PubSubMessageBus.close."""

    async def test_close_clears_subscriptions(self, bus: Any) -> None:
        """close() clears the active subscription registry."""

        async def handler(msg: Message) -> None:
            pass

        await bus.subscribe("t", handler)
        assert len(bus._subscriptions) == 1
        await bus.close()
        assert len(bus._subscriptions) == 0

    async def test_close_nils_publisher_and_subscriber(self, bus: Any) -> None:
        """close() sets publisher and subscriber to None."""
        await bus.close()
        assert bus._publisher is None
        assert bus._subscriber is None


class TestCreateFromEnvGCP:
    """Tests for create_message_bus_from_env with gcp-pubsub backend."""

    def test_create_pubsub_bus_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_message_bus_from_env() returns PubSubMessageBus for gcp-pubsub."""
        monkeypatch.setenv("KUTANA_MESSAGE_BUS", "gcp-pubsub")
        monkeypatch.setenv("GCP_PROJECT_ID", "my-gcp-project")

        from kutana_providers.messaging.gcp_pubsub import PubSubMessageBus
        from kutana_providers.messaging.redis_streams import create_message_bus_from_env

        bus = create_message_bus_from_env()
        assert isinstance(bus, PubSubMessageBus)
        assert bus._project_id == "my-gcp-project"

    def test_gcp_bus_raises_without_project_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """PubSubMessageBus raises ValueError when GCP_PROJECT_ID is unset."""
        monkeypatch.delenv("GCP_PROJECT_ID", raising=False)

        from kutana_providers.messaging.gcp_pubsub import PubSubMessageBus

        with pytest.raises(ValueError, match="GCP_PROJECT_ID"):
            PubSubMessageBus(project_id=None)
