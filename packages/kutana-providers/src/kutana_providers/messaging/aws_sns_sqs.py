"""AWS SNS/SQS implementation of the MessageBus ABC.

Uses SNS as the pub/sub fanout layer and SQS as the durable delivery
queue per consumer.  Each topic maps to an SNS topic; each (topic, group)
pair maps to a dedicated SQS queue that is subscribed to that SNS topic,
providing consumer-group load-balanced delivery.

Requires ``aioboto3`` (install with ``uv add 'kutana-providers[aws]'``).

Configuration environment variables::

    AWS_REGION              AWS region (default: us-east-1)
    AWS_ACCESS_KEY_ID       Static credentials (optional if using IAM role)
    AWS_SECRET_ACCESS_KEY   Static credentials (optional if using IAM role)
    AWS_SESSION_TOKEN       Session token for temporary credentials (optional)
    SNS_TOPIC_PREFIX        Prefix for SNS topic names (default: kutana-)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import Any
from uuid import uuid4

from kutana_core.messaging.abc import MessageBus
from kutana_core.messaging.types import Message, Subscription

logger = logging.getLogger(__name__)

# Lazy import — aioboto3 is an optional dependency.
try:
    import aioboto3  # type: ignore[import-untyped]

    _AIOBOTO3_AVAILABLE = True
except ImportError:
    _AIOBOTO3_AVAILABLE = False


def _require_aioboto3() -> None:
    """Raise ImportError with install instructions if aioboto3 is missing."""
    if not _AIOBOTO3_AVAILABLE:
        msg = (
            "aioboto3 is required for SQSMessageBus. "
            "Install it with: uv add 'kutana-providers[aws]'"
        )
        raise ImportError(msg)


def _topic_to_sns_name(topic: str, prefix: str) -> str:
    """Convert a Kutana topic string to a valid SNS topic name.

    SNS topic names allow only alphanumeric characters, hyphens, and
    underscores (max 256 chars).  Dots and wildcards are replaced with
    underscores.

    Args:
        topic: Kutana topic string (e.g. ``"meeting.abc.events"``).
        prefix: Prefix to prepend (e.g. ``"kutana-"``).

    Returns:
        A valid SNS topic name string.
    """
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", topic)
    full = f"{prefix}{name}"
    return full[:256]


def _queue_name_for_group(topic: str, group: str, prefix: str) -> str:
    """Return an SQS queue name for a (topic, group) consumer pair.

    Args:
        topic: Kutana topic string.
        group: Consumer group name.
        prefix: Topic prefix used for naming.

    Returns:
        A valid SQS queue name (max 80 chars).
    """
    base = _topic_to_sns_name(topic, prefix)
    combined = f"{base}--{group}"
    return combined[:80]


class SQSMessageBus(MessageBus):
    """MessageBus implementation backed by AWS SNS (fanout) and SQS (delivery).

    Each :meth:`publish` call creates the SNS topic if needed and publishes
    the message.  Each :meth:`subscribe` call creates an SQS queue, subscribes
    it to the SNS topic, and starts a long-polling background task.

    Consumer groups are modelled as separate SQS queues per ``(topic, group)``
    pair: all consumers sharing the same group name receive messages in a
    load-balanced manner (standard SQS behaviour).

    Fan-out subscriptions (``group=None``) create a unique ephemeral SQS queue
    per subscriber, ensuring every subscriber receives every message.

    Topic pattern matching (``"meeting.*.events"``) is simulated by listing
    SNS topics and matching against the pattern on each polling cycle.

    Args:
        region: AWS region name.
        access_key_id: AWS access key (optional — omit to use IAM role).
        secret_access_key: AWS secret key (optional — omit to use IAM role).
        session_token: Temporary session token (optional).
        topic_prefix: Prefix for SNS topic names. Defaults to ``"kutana-"``.
        poll_interval_s: Seconds between SQS long-poll cycles. Defaults to 1.
        visibility_timeout_s: SQS message visibility timeout in seconds.
    """

    def __init__(
        self,
        region: str | None = None,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        session_token: str | None = None,
        topic_prefix: str = "kutana-",
        poll_interval_s: float = 1.0,
        visibility_timeout_s: int = 30,
    ) -> None:
        """Initialize the SQS message bus."""
        _require_aioboto3()
        self._region = region or os.getenv("AWS_REGION", "us-east-1")
        self._access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self._secret_access_key = secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self._session_token = session_token or os.getenv("AWS_SESSION_TOKEN")
        self._topic_prefix = topic_prefix
        self._poll_interval_s = poll_interval_s
        self._visibility_timeout_s = visibility_timeout_s

        # Cache: topic -> SNS ARN
        self._sns_arns: dict[str, str] = {}
        # Cache: queue_name -> (queue_url, queue_arn)
        self._sqs_queues: dict[str, tuple[str, str]] = {}

        self._subscriptions: dict[str, Subscription] = {}
        self._tasks: list[asyncio.Task[None]] = []
        self._session: Any = None  # aioboto3.Session

    def _make_session(self) -> Any:
        """Create (or return cached) aioboto3 Session."""
        if self._session is None:
            kwargs: dict[str, Any] = {"region_name": self._region}
            if self._access_key_id:
                kwargs["aws_access_key_id"] = self._access_key_id
            if self._secret_access_key:
                kwargs["aws_secret_access_key"] = self._secret_access_key
            if self._session_token:
                kwargs["aws_session_token"] = self._session_token
            self._session = aioboto3.Session(**kwargs)
        return self._session

    # ------------------------------------------------------------------
    # SNS helpers
    # ------------------------------------------------------------------

    async def _get_or_create_sns_topic(self, topic: str) -> str:
        """Return the ARN of the SNS topic for *topic*, creating it if needed.

        Args:
            topic: Kutana topic string.

        Returns:
            SNS topic ARN.
        """
        if topic in self._sns_arns:
            return self._sns_arns[topic]

        sns_name = _topic_to_sns_name(topic, self._topic_prefix)
        session = self._make_session()
        async with session.client("sns") as sns:
            response: dict[str, Any] = await sns.create_topic(Name=sns_name)
            arn: str = response["TopicArn"]
        self._sns_arns[topic] = arn
        logger.debug("SNS topic %s -> %s", topic, arn)
        return arn

    async def _list_matching_sns_topics(self, pattern: str) -> list[str]:
        """Return Kutana topics whose SNS names match the given fnmatch pattern.

        Fetches the full SNS topic list and filters by name pattern.

        Args:
            pattern: fnmatch-style topic pattern (e.g. ``"meeting.*.events"``).

        Returns:
            List of original Kutana topic strings that match.
        """
        import fnmatch

        sns_pattern = _topic_to_sns_name(pattern, self._topic_prefix)
        matched_topics: list[str] = []
        session = self._make_session()
        async with session.client("sns") as sns:
            paginator = sns.get_paginator("list_topics")
            async for page in paginator.paginate():
                for topic_dict in page.get("Topics", []):
                    arn: str = topic_dict["TopicArn"]
                    name = arn.split(":")[-1]
                    if fnmatch.fnmatch(name, sns_pattern):
                        matched_topics.append(arn)
        return matched_topics

    # ------------------------------------------------------------------
    # SQS helpers
    # ------------------------------------------------------------------

    async def _get_or_create_sqs_queue(self, queue_name: str) -> tuple[str, str]:
        """Return (queue_url, queue_arn) for *queue_name*, creating it if needed.

        Args:
            queue_name: SQS queue name.

        Returns:
            Tuple of (queue_url, queue_arn).
        """
        if queue_name in self._sqs_queues:
            return self._sqs_queues[queue_name]

        session = self._make_session()
        async with session.client("sqs") as sqs:
            response: dict[str, Any] = await sqs.create_queue(
                QueueName=queue_name,
                Attributes={
                    "VisibilityTimeout": str(self._visibility_timeout_s),
                    "MessageRetentionPeriod": "86400",  # 1 day
                },
            )
            queue_url: str = response["QueueUrl"]
            attr_response: dict[str, Any] = await sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=["QueueArn"],
            )
            queue_arn: str = attr_response["Attributes"]["QueueArn"]

        self._sqs_queues[queue_name] = (queue_url, queue_arn)
        logger.debug("SQS queue %s -> %s", queue_name, queue_url)
        return queue_url, queue_arn

    async def _subscribe_sqs_to_sns(self, sns_arn: str, sqs_arn: str, sqs_url: str) -> None:
        """Subscribe an SQS queue to an SNS topic.

        Sets the SQS queue policy to allow SNS to deliver messages, then
        creates the SNS subscription.

        Args:
            sns_arn: SNS topic ARN.
            sqs_arn: SQS queue ARN.
            sqs_url: SQS queue URL (for policy update).
        """
        # Grant SNS permission to publish to SQS
        policy = json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Principal": {"Service": "sns.amazonaws.com"},
                        "Action": "sqs:SendMessage",
                        "Resource": sqs_arn,
                        "Condition": {"ArnEquals": {"aws:SourceArn": sns_arn}},
                    }
                ],
            }
        )
        session = self._make_session()
        async with session.client("sqs") as sqs:
            await sqs.set_queue_attributes(
                QueueUrl=sqs_url,
                Attributes={"Policy": policy},
            )

        async with session.client("sns") as sns:
            await sns.subscribe(
                TopicArn=sns_arn,
                Protocol="sqs",
                Endpoint=sqs_arn,
                Attributes={"RawMessageDelivery": "true"},
            )
        logger.debug("Subscribed SQS %s to SNS %s", sqs_arn, sns_arn)

    # ------------------------------------------------------------------
    # MessageBus interface
    # ------------------------------------------------------------------

    async def publish(
        self,
        topic: str,
        payload: dict[str, Any],
        metadata: dict[str, str] | None = None,
        source: str = "",
    ) -> str:
        """Publish a message to an SNS topic.

        Creates the SNS topic if it does not yet exist.

        Args:
            topic: Kutana topic string — maps to an SNS topic name.
            payload: JSON-serializable message payload.
            metadata: Optional routing metadata.
            source: Name of the publishing service.

        Returns:
            The unique message UUID assigned to this message.
        """
        message = Message(
            topic=topic,
            payload=payload,
            metadata=metadata or {},
            source=source,
        )
        body = json.dumps(
            {
                "message_id": message.id,
                "topic": message.topic,
                "payload": message.payload,
                "metadata": message.metadata,
                "timestamp": message.timestamp.isoformat(),
                "source": message.source,
            }
        )
        sns_arn = await self._get_or_create_sns_topic(topic)
        session = self._make_session()
        async with session.client("sns") as sns:
            await sns.publish(TopicArn=sns_arn, Message=body)
        logger.debug("Published message %s to SNS %s", message.id, sns_arn)
        return message.id

    async def subscribe(
        self,
        topic: str,
        handler: Any,
        group: str | None = None,
    ) -> Subscription:
        """Subscribe to a Kutana topic via an SQS queue.

        Creates the SNS topic and SQS queue if they do not exist, then wires
        SNS→SQS delivery and starts a long-polling background task.

        For fan-out subscriptions (``group=None``) a unique queue is created
        per subscription.  For consumer group subscriptions all subscribers
        sharing the same *group* share the same SQS queue (load-balanced).

        Args:
            topic: Exact topic or fnmatch pattern.
            handler: Async callback ``async def handler(msg: Message) -> None``.
            group: Consumer group name for load-balanced delivery.

        Returns:
            A Subscription object.
        """
        is_pattern = any(c in topic for c in ("*", "?", "["))
        sub = Subscription(topic=topic, handler=handler, group=group)
        self._subscriptions[sub.subscription_id] = sub

        if not is_pattern:
            # Eagerly set up the queue for exact subscriptions
            await self._setup_queue_for_subscription(sub)

        task: asyncio.Task[None] = asyncio.create_task(
            self._consume(sub), name=f"sqs-sub-{sub.subscription_id[:8]}"
        )
        self._tasks.append(task)
        logger.debug(
            "SQS subscribed to %s (group=%s, id=%s)",
            topic,
            group,
            sub.subscription_id,
        )
        return sub

    async def _setup_queue_for_subscription(self, sub: Subscription) -> str:
        """Create/get the SQS queue for a subscription and wire SNS→SQS.

        Args:
            sub: The subscription being set up.

        Returns:
            The SQS queue URL.
        """
        group = sub.group or sub.subscription_id[:16]
        queue_name = _queue_name_for_group(sub.topic, group, self._topic_prefix)
        sns_arn = await self._get_or_create_sns_topic(sub.topic)
        queue_url, queue_arn = await self._get_or_create_sqs_queue(queue_name)
        await self._subscribe_sqs_to_sns(sns_arn, queue_arn, queue_url)
        return queue_url

    async def unsubscribe(self, subscription: Subscription) -> None:
        """Remove an active subscription (stops background polling).

        Args:
            subscription: The subscription to remove.
        """
        self._subscriptions.pop(subscription.subscription_id, None)
        logger.debug(
            "SQS unsubscribed from %s (id=%s)",
            subscription.topic,
            subscription.subscription_id,
        )

    async def ack(self, subscription: Subscription, message_id: str) -> None:
        """Acknowledge a message by deleting it from the SQS queue.

        The *message_id* here is the SQS receipt handle stored by the
        polling loop, not the Kutana UUID.  For fan-out subscriptions
        this is a no-op.

        Args:
            subscription: The subscription that received the message.
            message_id: The SQS receipt handle for the message.
        """
        if subscription.group is None:
            return
        group = subscription.group
        queue_name = _queue_name_for_group(subscription.topic, group, self._topic_prefix)
        cached = self._sqs_queues.get(queue_name)
        if cached is None:
            return
        queue_url = cached[0]
        session = self._make_session()
        try:
            async with session.client("sqs") as sqs:
                await sqs.delete_message(QueueUrl=queue_url, ReceiptHandle=message_id)
        except Exception:
            logger.exception("SQS ack failed for message %s", message_id)

    async def close(self) -> None:
        """Cancel all subscriptions and release resources."""
        self._subscriptions.clear()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        self._session = None
        logger.debug("SQSMessageBus closed")

    # ------------------------------------------------------------------
    # Background poll loop
    # ------------------------------------------------------------------

    async def _consume(self, sub: Subscription) -> None:
        """Long-poll SQS and dispatch messages to the subscription handler."""
        is_pattern = any(c in sub.topic for c in ("*", "?", "["))
        queue_url: str | None = None

        while sub.subscription_id in self._subscriptions:
            try:
                if is_pattern:
                    await self._consume_pattern(sub)
                    continue

                if queue_url is None:
                    queue_url = await self._setup_queue_for_subscription(sub)

                await self._poll_queue(sub, queue_url)

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Error in SQS consume loop for %s", sub.topic)
                await asyncio.sleep(self._poll_interval_s)

    async def _consume_pattern(self, sub: Subscription) -> None:
        """Handle pattern-based subscriptions by iterating matching topics."""
        matched_arns = await self._list_matching_sns_topics(sub.topic)
        if not matched_arns:
            await asyncio.sleep(self._poll_interval_s)
            return
        for arn in matched_arns:
            topic_name = arn.split(":")[-1]
            sub_topic = topic_name.removeprefix(self._topic_prefix)
            group = sub.group or sub.subscription_id[:16]
            queue_name = _queue_name_for_group(sub_topic, group, self._topic_prefix)
            _, queue_arn = await self._get_or_create_sqs_queue(queue_name)
            queue_url_: str = self._sqs_queues[queue_name][0]
            await self._subscribe_sqs_to_sns(arn, queue_arn, queue_url_)
            await self._poll_queue(sub, queue_url_)

    async def _poll_queue(self, sub: Subscription, queue_url: str) -> None:
        """Receive messages from an SQS queue and dispatch them.

        Args:
            sub: The active subscription.
            queue_url: The SQS queue URL to poll.
        """
        session = self._make_session()
        async with session.client("sqs") as sqs:
            response: dict[str, Any] = await sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=10,
                WaitTimeSeconds=min(int(self._poll_interval_s * 10), 20),
                AttributeNames=["All"],
            )
        for sqs_msg in response.get("Messages", []):
            body_str: str = sqs_msg.get("Body", "{}")
            receipt_handle: str = sqs_msg.get("ReceiptHandle", "")
            try:
                body = json.loads(body_str)
                # SNS wraps payloads; handle both raw and wrapped delivery
                if "Message" in body and isinstance(body["Message"], str):
                    body = json.loads(body["Message"])
                message = Message(
                    id=body.get("message_id", str(uuid4())),
                    topic=body.get("topic", sub.topic),
                    payload=body.get("payload", {}),
                    metadata=body.get("metadata", {}),
                    source=body.get("source", ""),
                )
                await sub.handler(message)
                # Auto-ack fan-out subscriptions; group subs need explicit ack
                if sub.group is None:
                    async with session.client("sqs") as sqs:
                        await sqs.delete_message(
                            QueueUrl=queue_url,
                            ReceiptHandle=receipt_handle,
                        )
            except Exception:
                logger.exception("Error dispatching SQS message from %s", queue_url)
