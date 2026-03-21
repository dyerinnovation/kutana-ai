"""Portable message bus abstraction for Convene AI."""

from __future__ import annotations

from convene_core.messaging.abc import MessageBus
from convene_core.messaging.types import Message, MessageHandler, Subscription

__all__ = [
    "Message",
    "MessageBus",
    "MessageHandler",
    "Subscription",
]
