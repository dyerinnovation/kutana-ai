"""Core messaging types for the portable message bus abstraction."""

from __future__ import annotations

import dataclasses
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utc_now() -> datetime:
    """Return the current UTC datetime."""
    return datetime.now(tz=UTC)


class Message(BaseModel):
    """A message on the Convene AI message bus.

    Attributes:
        id: Unique message identifier (UUID string).
        topic: The topic this message was published to.
        payload: The message data (arbitrary JSON-serializable dict).
        metadata: Routing and contextual metadata as string key-value pairs.
        timestamp: When the message was created (UTC).
        source: The service that published this message.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    topic: str
    payload: dict[str, Any]
    metadata: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)
    source: str = ""


#: Type alias for async message handler callbacks.
type MessageHandler = Callable[[Message], Awaitable[None]]


@dataclasses.dataclass
class Subscription:
    """An active subscription on the message bus.

    Attributes:
        topic: The topic (or fnmatch pattern) subscribed to.
        handler: Async callback invoked for each delivered message.
        group: Consumer group name for load-balanced delivery. None for fan-out.
        subscription_id: Unique identifier for this subscription instance.
    """

    topic: str
    handler: MessageHandler
    group: str | None = None
    subscription_id: str = dataclasses.field(default_factory=lambda: str(uuid4()))
