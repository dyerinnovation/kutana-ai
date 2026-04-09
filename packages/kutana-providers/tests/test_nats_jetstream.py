"""Tests for the NATSMessageBus provider (mocked nats-py client)."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kutana_core.messaging.abc import MessageBus
from kutana_core.messaging.types import Message, Subscription

# ---------------------------------------------------------------------------
# Helpers: build mock NATS client / JetStream
# ---------------------------------------------------------------------------


def _make_nats_msg(body: dict[str, Any]) -> MagicMock:
    """Build a mock NATS message with a JSON-encoded body."""
    msg = MagicMock()
    msg.data = json.dumps(body).encode("utf-8")
    msg.ack = AsyncMock()
    msg.nak = AsyncMock()
    return msg


def _make_nats_sub(callback_store: list[Any]) -> MagicMock:
    """Build a mock NATS JetStream subscription that records its callback."""
    sub = MagicMock()
    sub.unsubscribe = AsyncMock()
    return sub


def _make_js(
    published_subjects: list[str] | None = None,
) -> AsyncMock:
    """Build a mock JetStream context."""
    js = AsyncMock()
    js.find_stream = AsyncMock(side_effect=Exception("stream not found"))
    js.add_stream = AsyncMock()
    js.publish = AsyncMock(return_value=MagicMock(seq=1))
    js.subscribe = AsyncMock(return_value=_make_nats_sub([]))
    return js


def _make_nc(js: AsyncMock) -> MagicMock:
    """Build a mock NATS client that returns the given JetStream context."""
    nc = MagicMock()
    nc.is_connected = True
    nc.jetstream = MagicMock(return_value=js)
    nc.drain = AsyncMock()
    return nc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_js() -> AsyncMock:
    return _make_js()


@pytest.fixture
def mock_nc(mock_js: AsyncMock) -> MagicMock:
    return _make_nc(mock_js)


@pytest.fixture
def bus(mock_nc: MagicMock, mock_js: AsyncMock) -> Any:
    """Return a NATSMessageBus with mocked NATS client."""
    from kutana_providers.messaging.nats_jetstream import NATSMessageBus

    b = NATSMessageBus(url="nats://localhost:4222", stream_name="CONVENE")
    b._nc = mock_nc
    b._js = mock_js
    b._stream_created = True  # Skip stream setup in unit tests
    return b


# ---------------------------------------------------------------------------
# Import guard
# ---------------------------------------------------------------------------


class TestNATSImportGuard:
    """Tests that the ImportError guard works when nats-py is absent."""

    def test_raises_import_error_when_nats_missing(self) -> None:
        """NATSMessageBus raises ImportError if nats-py is not installed."""
        with patch("kutana_providers.messaging.nats_jetstream._NATS_AVAILABLE", False):
            from kutana_providers.messaging.nats_jetstream import _require_nats

            with pytest.raises(ImportError, match="nats-py"):
                _require_nats()


class TestNATSSubjectNaming:
    """Tests for subject / consumer name helpers."""

    def test_topic_to_subject_preserves_dots(self) -> None:
        from kutana_providers.messaging.nats_jetstream import _topic_to_subject

        assert _topic_to_subject("meeting.abc.events") == "meeting.abc.events"

    def test_topic_to_subject_preserves_wildcards(self) -> None:
        from kutana_providers.messaging.nats_jetstream import _topic_to_subject

        assert _topic_to_subject("meeting.*.events") == "meeting.*.events"

    def test_consumer_name_contains_topic_and_group(self) -> None:
        from kutana_providers.messaging.nats_jetstream import _consumer_name

        result = _consumer_name("meeting.events", "workers")
        assert "workers" in result

    def test_consumer_name_max_256_chars(self) -> None:
        from kutana_providers.messaging.nats_jetstream import _consumer_name

        result = _consumer_name("a" * 200, "b" * 200)
        assert len(result) <= 256

    def test_consumer_name_alphanumeric_plus_hyphen_underscore(self) -> None:
        import re

        from kutana_providers.messaging.nats_jetstream import _consumer_name

        result = _consumer_name("meeting.events", "my-workers")
        assert re.fullmatch(r"[a-zA-Z0-9_-]+", result)


class TestNATSPublish:
    """Tests for NATSMessageBus.publish."""

    async def test_publish_calls_js_publish(self, bus: Any, mock_js: AsyncMock) -> None:
        """publish() calls JetStream publish on the subject."""
        await bus.publish("meeting.events", {"type": "started"})
        mock_js.publish.assert_called_once()
        call_args = mock_js.publish.call_args
        assert call_args[0][0] == "meeting.events"

    async def test_publish_returns_uuid(self, bus: Any) -> None:
        """publish() returns a 36-char UUID string."""
        msg_id = await bus.publish("t", {})
        assert isinstance(msg_id, str)
        assert len(msg_id) == 36

    async def test_publish_sends_json_body(self, bus: Any, mock_js: AsyncMock) -> None:
        """publish() encodes the full message as UTF-8 JSON."""
        await bus.publish("t", {"answer": 42}, source="svc")
        call_args = mock_js.publish.call_args
        body = json.loads(call_args[0][1].decode("utf-8"))
        assert body["payload"] == {"answer": 42}
        assert body["source"] == "svc"

    async def test_publish_unique_message_ids(self, bus: Any) -> None:
        """Each publish() generates a distinct message UUID."""
        ids = {await bus.publish("t", {}) for _ in range(5)}
        assert len(ids) == 5

    async def test_nats_bus_implements_message_bus_abc(self, bus: Any) -> None:
        """NATSMessageBus is a subclass of MessageBus."""
        assert isinstance(bus, MessageBus)


class TestNATSSubscribe:
    """Tests for NATSMessageBus.subscribe."""

    async def test_subscribe_returns_subscription(self, bus: Any) -> None:
        """subscribe() returns a Subscription with correct topic."""

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("meeting.events", handler)
        assert isinstance(sub, Subscription)
        assert sub.topic == "meeting.events"
        bus._subscriptions.clear()

    async def test_subscribe_calls_js_subscribe(self, bus: Any, mock_js: AsyncMock) -> None:
        """subscribe() calls jetstream.subscribe for the subject."""

        async def handler(msg: Message) -> None:
            pass

        await bus.subscribe("meeting.events", handler)
        mock_js.subscribe.assert_called_once()
        bus._subscriptions.clear()

    async def test_subscribe_with_group_uses_queue(self, bus: Any, mock_js: AsyncMock) -> None:
        """subscribe(group=...) passes queue= and durable= to JetStream."""

        async def handler(msg: Message) -> None:
            pass

        await bus.subscribe("meeting.events", handler, group="workers")
        call_kwargs = mock_js.subscribe.call_args[1]
        assert call_kwargs.get("queue") == "workers"
        assert "durable" in call_kwargs
        bus._subscriptions.clear()

    async def test_subscribe_without_group_no_queue(self, bus: Any, mock_js: AsyncMock) -> None:
        """Fan-out subscribe (group=None) does not set queue=."""

        async def handler(msg: Message) -> None:
            pass

        await bus.subscribe("meeting.events", handler, group=None)
        call_kwargs = mock_js.subscribe.call_args[1]
        assert "queue" not in call_kwargs
        bus._subscriptions.clear()

    async def test_subscribe_registers_in_subscriptions_dict(self, bus: Any) -> None:
        """subscribe() adds to the internal _subscriptions dict."""

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("t", handler)
        assert sub.subscription_id in bus._subscriptions
        bus._subscriptions.clear()


class TestNATSHandlerDispatch:
    """Tests for _make_handler callback dispatch."""

    async def test_handler_dispatches_message_to_callback(self, bus: Any) -> None:
        """_make_handler callback deserialises message and calls handler."""
        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        sub = Subscription(topic="t", handler=handler)
        bus._subscriptions[sub.subscription_id] = sub

        callback = bus._make_handler(sub)
        nats_msg = _make_nats_msg(
            {
                "message_id": "test-uuid-1234",
                "topic": "t",
                "payload": {"x": 99},
                "metadata": {},
                "source": "svc",
            }
        )
        await callback(nats_msg)

        assert len(received) == 1
        assert received[0].id == "test-uuid-1234"
        assert received[0].payload == {"x": 99}
        nats_msg.ack.assert_called_once()

    async def test_handler_naks_on_exception(self, bus: Any) -> None:
        """_make_handler nacks the message when the handler raises."""

        async def bad_handler(msg: Message) -> None:
            raise RuntimeError("test error")

        sub = Subscription(topic="t", handler=bad_handler)
        bus._subscriptions[sub.subscription_id] = sub

        callback = bus._make_handler(sub)
        nats_msg = _make_nats_msg(
            {
                "message_id": "x",
                "topic": "t",
                "payload": {},
                "metadata": {},
                "source": "",
            }
        )
        await callback(nats_msg)
        # ack should NOT be called; nak should be called
        nats_msg.ack.assert_not_called()
        nats_msg.nak.assert_called_once()


class TestNATSAck:
    """Tests for NATSMessageBus.ack — should be a no-op (auto-acked)."""

    async def test_ack_is_noop(self, bus: Any) -> None:
        """ack() is a no-op for JetStream push consumers (auto-acked)."""

        async def handler(msg: Message) -> None:
            pass

        sub = Subscription(topic="t", handler=handler)
        # Should not raise
        await bus.ack(sub, "unused-id")


class TestNATSUnsubscribe:
    """Tests for NATSMessageBus.unsubscribe."""

    async def test_unsubscribe_removes_from_subscriptions(self, bus: Any) -> None:
        """unsubscribe() removes the subscription from the registry."""

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("t", handler)
        assert sub.subscription_id in bus._subscriptions
        await bus.unsubscribe(sub)
        assert sub.subscription_id not in bus._subscriptions

    async def test_unsubscribe_calls_nats_sub_unsubscribe(self, bus: Any) -> None:
        """unsubscribe() drains the underlying NATS subscription."""

        async def handler(msg: Message) -> None:
            pass

        sub = await bus.subscribe("t", handler)
        nats_sub = bus._nats_subs.get(sub.subscription_id)
        await bus.unsubscribe(sub)
        assert nats_sub is not None
        nats_sub.unsubscribe.assert_called_once()


class TestNATSClose:
    """Tests for NATSMessageBus.close."""

    async def test_close_clears_subscriptions(self, bus: Any) -> None:
        """close() clears the subscription registry."""

        async def handler(msg: Message) -> None:
            pass

        await bus.subscribe("t", handler)
        assert len(bus._subscriptions) == 1
        await bus.close()
        assert len(bus._subscriptions) == 0

    async def test_close_drains_nats_connection(self, bus: Any, mock_nc: MagicMock) -> None:
        """close() calls nc.drain() on the NATS client."""
        await bus.close()
        mock_nc.drain.assert_called_once()

    async def test_close_sets_nc_to_none(self, bus: Any) -> None:
        """close() resets the NATS client reference."""
        await bus.close()
        assert bus._nc is None


class TestNATSRegistry:
    """Tests that NATSMessageBus is registered in the default registry."""

    def test_nats_in_registry(self) -> None:
        """NATSMessageBus is registered as 'nats' in the default registry."""
        from kutana_providers.registry import ProviderType, default_registry

        providers = default_registry.list_providers(ProviderType.MESSAGE_BUS)
        assert "nats" in providers

    def test_aws_sns_sqs_in_registry(self) -> None:
        """SQSMessageBus is registered as 'aws-sns-sqs' in the default registry."""
        from kutana_providers.registry import ProviderType, default_registry

        providers = default_registry.list_providers(ProviderType.MESSAGE_BUS)
        assert "aws-sns-sqs" in providers

    def test_gcp_pubsub_in_registry(self) -> None:
        """PubSubMessageBus is registered as 'gcp-pubsub' in the default registry."""
        from kutana_providers.registry import ProviderType, default_registry

        providers = default_registry.list_providers(ProviderType.MESSAGE_BUS)
        assert "gcp-pubsub" in providers

    def test_all_four_backends_registered(self) -> None:
        """All four message bus backends are registered."""
        from kutana_providers.registry import ProviderType, default_registry

        providers = set(default_registry.list_providers(ProviderType.MESSAGE_BUS))
        assert {"redis", "aws-sns-sqs", "gcp-pubsub", "nats"}.issubset(providers)
