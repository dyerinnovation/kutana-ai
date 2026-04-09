"""Langfuse SDK singleton and helper functions for LLM observability.

Provides a singleton Langfuse client and convenience helpers for creating
traces, generation spans, and scoring agent eval results.
"""

from __future__ import annotations

import logging
from typing import Any

from langfuse import Langfuse

logger = logging.getLogger(__name__)

_client: Langfuse | None = None


def init_langfuse(
    secret_key: str,
    public_key: str,
    host: str = "http://localhost:3100",
) -> Langfuse:
    """Initialise the singleton Langfuse client.

    Should be called once during application lifespan startup.

    Args:
        secret_key: Langfuse secret key.
        public_key: Langfuse public key.
        host: Langfuse server URL.

    Returns:
        The initialised Langfuse client.
    """
    global _client
    _client = Langfuse(
        secret_key=secret_key,
        public_key=public_key,
        host=host,
    )
    logger.info("Langfuse client initialised (host=%s)", host)
    return _client


def get_langfuse() -> Langfuse | None:
    """Return the singleton Langfuse client, or None if not initialised.

    Returns:
        The Langfuse client, or None.
    """
    return _client


def flush_langfuse() -> None:
    """Flush pending events and shut down the Langfuse client.

    Safe to call even if Langfuse was never initialised.
    """
    global _client
    if _client is not None:
        try:
            _client.flush()
            _client.shutdown()
            logger.info("Langfuse client flushed and shut down")
        except Exception:
            logger.warning("Error flushing Langfuse client", exc_info=True)
        _client = None


def create_trace(
    name: str,
    metadata: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
) -> Any:
    """Create a new Langfuse trace.

    Args:
        name: Trace name (e.g. "managed-agent-session").
        metadata: Optional metadata dict.
        tags: Optional tags for filtering.
        user_id: Optional user ID for attribution.
        session_id: Optional session ID for grouping.

    Returns:
        A Langfuse trace object, or None if client not initialised.
    """
    if _client is None:
        return None
    return _client.trace(
        name=name,
        metadata=metadata or {},
        tags=tags or [],
        user_id=user_id,
        session_id=session_id,
    )


def score_trace(
    trace_id: str,
    name: str,
    value: float,
    comment: str = "",
) -> None:
    """Attach a score to a Langfuse trace.

    Args:
        trace_id: ID of the trace to score.
        name: Score name (e.g. "overall", "accuracy").
        value: Numeric score value.
        comment: Optional comment explaining the score.
    """
    if _client is None:
        return
    _client.score(
        trace_id=trace_id,
        name=name,
        value=value,
        comment=comment,
    )
