"""Tests for the SQSMessageBus provider (mocked AWS clients)."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kutana_core.messaging.abc import MessageBus
from kutana_core.messaging.types import Message, Subscription

# ---------------------------------------------------------------------------
# Helpers: build a mock aioboto3 session / client
# ---------------------------------------------------------------------------


def _make_sns_client(
    create_topic_arn: str = "arn:aws:sns:us-east-1:123456789012:kutana-test-topic",
    publish_message_id: str = "mock-sns-msg-id",
    list_topics_pages: list[list[dict[str, str]]] | None = None,
) -> MagicMock:
    """Build a mock SNS async context-manager client."""
    sns = AsyncMock()
    sns.create_topic = AsyncMock(return_value={"TopicArn": create_topic_arn})
    sns.publish = AsyncMock(return_value={"MessageId": publish_message_id})
    sns.subscribe = AsyncMock(return_value={"SubscriptionArn": "mock-sub-arn"})
    sns.set_queue_attributes = AsyncMock()

    # Paginator for list_topics
    pages = list_topics_pages or [[{"TopicArn": create_topic_arn}]]
    paginator = MagicMock()

    async def _async_for_pages() -> Any:
        for page in pages:
            yield {"Topics": page}

    paginator.paginate = MagicMock(return_value=_async_for_pages())
    sns.get_paginator = MagicMock(return_value=paginator)
    return sns


def _make_sqs_client(
    queue_url: str = "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue",
    queue_arn: str = "arn:aws:sqs:us-east-1:123456789012:test-queue",
    messages: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """Build a mock SQS async context-manager client."""
    sqs = AsyncMock()
    sqs.create_queue = AsyncMock(return_value={"QueueUrl": queue_url})
    sqs.get_queue_attributes = AsyncMock(
        return_value={"Attributes": {"QueueArn": queue_arn}}
    )
    sqs.set_queue_attributes = AsyncMock()
    sqs.receive_message = AsyncMock(
        return_value={"Messages": messages or []}
    )
    sqs.delete_message = AsyncMock()
    return sqs


def _make_session(sns_client: Any, sqs_client: Any) -> MagicMock:
    """Build a mock aioboto3 Session that returns the given clients."""
    session = MagicMock()

    class _AsyncCtxMgr:
        def __init__(self, client: Any) -> None:
            self._client = client

        async def __aenter__(self) -> Any:
            return self._client

        async def __aexit__(self, *args: Any) -> None:
            pass

    def _client(service: str) -> Any:
        if service == "sns":
            return _AsyncCtxMgr(sns_client)
        return _AsyncCtxMgr(sqs_client)

    session.client = _client
    return session


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> tuple[MagicMock, MagicMock, MagicMock]:
    """Return (session, sns_mock, sqs_mock) with default stubs."""
    sns = _make_sns_client()
    sqs = _make_sqs_client()
    session = _make_session(sns, sqs)
    return session, sns, sqs


@pytest.fixture
def bus(mock_session: tuple[MagicMock, MagicMock, MagicMock]) -> Any:
    """Return an SQSMessageBus with aioboto3 patched out."""
    session, _, _ = mock_session
    # Patch aioboto3 at import time
    with patch.dict("sys.modules", {"aioboto3": MagicMock()}):
        # Import inside the patch to pick up the mock
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1", topic_prefix="kutana-")
        b._session = session
        return b


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestSQSMessageBusImportGuard:
    """Tests that the ImportError guard works when aioboto3 is absent."""

    def test_raises_import_error_when_aioboto3_missing(self) -> None:
        """SQSMessageBus raises ImportError if aioboto3 is not installed."""
        import sys

        with patch.dict("sys.modules", {"aioboto3": None}):  # type: ignore[dict-item]
            # Force re-evaluation of _AIOBOTO3_AVAILABLE
            if "kutana_providers.messaging.aws_sns_sqs" in sys.modules:
                del sys.modules["kutana_providers.messaging.aws_sns_sqs"]

            # Re-import with missing dependency simulated
            with patch(
                "kutana_providers.messaging.aws_sns_sqs._AIOBOTO3_AVAILABLE", False
            ):
                from kutana_providers.messaging.aws_sns_sqs import _require_aioboto3

                with pytest.raises(ImportError, match="aioboto3"):
                    _require_aioboto3()


class TestTopicNaming:
    """Tests for the SNS/SQS name derivation helpers."""

    def test_topic_to_sns_name_replaces_dots(self) -> None:
        from kutana_providers.messaging.aws_sns_sqs import _topic_to_sns_name

        assert _topic_to_sns_name("meeting.abc.events", "kutana-") == (
            "kutana-meeting_abc_events"
        )

    def test_topic_to_sns_name_replaces_wildcards(self) -> None:
        from kutana_providers.messaging.aws_sns_sqs import _topic_to_sns_name

        result = _topic_to_sns_name("meeting.*.events", "kutana-")
        assert "*" not in result

    def test_queue_name_for_group_contains_topic_and_group(self) -> None:
        from kutana_providers.messaging.aws_sns_sqs import _queue_name_for_group

        result = _queue_name_for_group("meeting.events", "workers", "kutana-")
        assert "meeting" in result
        assert "workers" in result

    def test_queue_name_truncated_to_80_chars(self) -> None:
        from kutana_providers.messaging.aws_sns_sqs import _queue_name_for_group

        result = _queue_name_for_group(
            "a" * 100, "b" * 100, "c" * 10
        )
        assert len(result) <= 80


class TestSQSPublish:
    """Tests for SQSMessageBus.publish."""

    async def test_publish_creates_sns_topic(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """publish() calls SNS create_topic for the given Kutana topic."""
        session, sns, _ = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1", topic_prefix="kutana-")
        b._session = session

        await b.publish("test.topic", {"key": "value"})
        sns.create_topic.assert_called_once()

    async def test_publish_returns_uuid_string(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """publish() returns a 36-char UUID string."""
        session, _, _ = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1", topic_prefix="kutana-")
        b._session = session

        msg_id = await b.publish("test.topic", {"x": 1})
        assert isinstance(msg_id, str)
        assert len(msg_id) == 36

    async def test_publish_caches_sns_arn(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """publish() caches the SNS ARN and only calls create_topic once."""
        session, sns, _ = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1", topic_prefix="kutana-")
        b._session = session

        await b.publish("test.topic", {})
        await b.publish("test.topic", {})
        assert sns.create_topic.call_count == 1

    async def test_publish_unique_message_ids(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """Each publish() generates a distinct message UUID."""
        session, _, _ = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1", topic_prefix="kutana-")
        b._session = session

        ids = {await b.publish("t", {}) for _ in range(5)}
        assert len(ids) == 5

    async def test_publish_sends_json_body(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """publish() sends a JSON body containing message_id and payload."""
        session, sns, _ = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1", topic_prefix="kutana-")
        b._session = session

        await b.publish("t", {"answer": 42}, source="audio-service")
        call_kwargs = sns.publish.call_args[1]
        body = json.loads(call_kwargs["Message"])
        assert body["payload"] == {"answer": 42}
        assert body["source"] == "audio-service"


class TestSQSSubscribe:
    """Tests for SQSMessageBus.subscribe."""

    async def test_subscribe_returns_subscription(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """subscribe() returns a Subscription with correct fields."""
        session, _, _ = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1", topic_prefix="kutana-")
        b._session = session

        async def handler(msg: Message) -> None:
            pass

        sub = await b.subscribe("test.topic", handler)
        assert isinstance(sub, Subscription)
        assert sub.topic == "test.topic"

        b._subscriptions.clear()
        for t in b._tasks:
            t.cancel()
        await asyncio.gather(*b._tasks, return_exceptions=True)

    async def test_subscribe_creates_sqs_queue(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """subscribe() calls SQS create_queue for the (topic, group) pair."""
        session, _, sqs = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1", topic_prefix="kutana-")
        b._session = session

        async def handler(msg: Message) -> None:
            pass

        await b.subscribe("test.topic", handler, group="workers")
        sqs.create_queue.assert_called_once()

        b._subscriptions.clear()
        for t in b._tasks:
            t.cancel()
        await asyncio.gather(*b._tasks, return_exceptions=True)

    async def test_subscribe_with_group_sets_group_on_subscription(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """subscribe(group=...) sets the group field on the Subscription."""
        session, _, _ = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1", topic_prefix="kutana-")
        b._session = session

        async def handler(msg: Message) -> None:
            pass

        sub = await b.subscribe("test.topic", handler, group="extractors")
        assert sub.group == "extractors"

        b._subscriptions.clear()
        for t in b._tasks:
            t.cancel()
        await asyncio.gather(*b._tasks, return_exceptions=True)

    async def test_subscribe_implements_message_bus_abc(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """SQSMessageBus is a subclass of MessageBus."""
        _, _, _ = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1")
        assert isinstance(b, MessageBus)


class TestSQSAck:
    """Tests for SQSMessageBus.ack."""

    async def test_ack_noop_for_fanout_subscription(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """ack() is a no-op for fan-out (group=None) subscriptions."""
        session, _, sqs = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1")
        b._session = session

        async def handler(msg: Message) -> None:
            pass

        sub = Subscription(topic="t", handler=handler, group=None)
        await b.ack(sub, "receipt-handle-123")
        sqs.delete_message.assert_not_called()

    async def test_ack_deletes_message_for_group_subscription(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """ack() calls SQS delete_message for consumer group subscriptions."""
        session, _, sqs = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1", topic_prefix="kutana-")
        b._session = session

        async def handler(msg: Message) -> None:
            pass

        sub = Subscription(topic="test.topic", handler=handler, group="workers")
        # Pre-populate the SQS queue cache so ack() knows the queue URL
        queue_name = "kutana-test_topic--workers"
        b._sqs_queues[queue_name] = (
            "https://sqs.us-east-1.amazonaws.com/123/q",
            "arn:aws:sqs:us-east-1:123:q",
        )
        await b.ack(sub, "receipt-handle-abc")
        sqs.delete_message.assert_called_once()


class TestSQSClose:
    """Tests for SQSMessageBus.close."""

    async def test_close_clears_subscriptions(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """close() clears the active subscription registry."""
        session, _, _ = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1")
        b._session = session

        async def handler(msg: Message) -> None:
            pass

        await b.subscribe("t", handler)
        assert len(b._subscriptions) == 1
        await b.close()
        assert len(b._subscriptions) == 0

    async def test_close_sets_session_to_none(
        self, mock_session: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        """close() resets the session so it can be recreated."""
        session, _, _ = mock_session
        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus

        b = SQSMessageBus(region="us-east-1")
        b._session = session
        await b.close()
        assert b._session is None


class TestCreateFromEnvAWS:
    """Tests for create_message_bus_from_env with aws-sns-sqs backend."""

    def test_create_sqs_bus_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """create_message_bus_from_env() returns SQSMessageBus for aws-sns-sqs."""
        monkeypatch.setenv("CONVENE_MESSAGE_BUS", "aws-sns-sqs")
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
        monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

        from kutana_providers.messaging.aws_sns_sqs import SQSMessageBus
        from kutana_providers.messaging.redis_streams import create_message_bus_from_env

        bus = create_message_bus_from_env()
        assert isinstance(bus, SQSMessageBus)
        assert bus._region == "eu-west-1"

    def test_create_nats_bus_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """create_message_bus_from_env() returns NATSMessageBus for nats."""
        monkeypatch.setenv("CONVENE_MESSAGE_BUS", "nats")
        monkeypatch.setenv("NATS_URL", "nats://myhost:4222")

        from kutana_providers.messaging.nats_jetstream import NATSMessageBus
        from kutana_providers.messaging.redis_streams import create_message_bus_from_env

        bus = create_message_bus_from_env()
        assert isinstance(bus, NATSMessageBus)
        assert bus._url == "nats://myhost:4222"

    def test_unsupported_backend_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """create_message_bus_from_env() raises ValueError for unknown backend."""
        monkeypatch.setenv("CONVENE_MESSAGE_BUS", "rabbit-mq")

        from kutana_providers.messaging.redis_streams import create_message_bus_from_env

        with pytest.raises(ValueError, match="Unsupported"):
            create_message_bus_from_env()
