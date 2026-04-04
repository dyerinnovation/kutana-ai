"""Structured audit logging for MCP auth events and tool calls.

All audit records are emitted as JSON to the "kutana.audit" logger.
In production this logger should be wired to a Redis Stream or a
structured log sink (e.g. Loki, CloudWatch Logs).

Record schema
-------------
Auth events::

    {
        "event":     "auth",
        "type":      "<event_type>",      # "token_validated", "scope_check", etc.
        "agent_id":  "<uuid | null>",
        "timestamp": <unix float>,
        ...extra kwargs
    }

Tool-call events::

    {
        "event":      "tool_call",
        "tool":       "<tool_name>",
        "agent_id":   "<uuid>",
        "meeting_id": "<uuid | null>",
        "success":    <bool>,
        "error":      "<message | null>",
        "timestamp":  <unix float>,
    }
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from uuid import UUID

_audit_logger = logging.getLogger("kutana.audit")


# ---------------------------------------------------------------------------
# Auth event logging
# ---------------------------------------------------------------------------


def log_auth_event(
    event_type: str,
    *,
    agent_id: UUID | None = None,
    success: bool = True,
    **kwargs: object,
) -> None:
    """Emit a structured auth audit record.

    Args:
        event_type: Descriptive event label, e.g. "token_validated",
                    "token_rejected", "scope_check_failed".
        agent_id: Agent UUID if known at the time of the event.
        success: Whether the auth action succeeded.
        **kwargs: Extra key/value pairs merged into the log record.
    """
    record: dict[str, object] = {
        "event": "auth",
        "type": event_type,
        "agent_id": str(agent_id) if agent_id else None,
        "success": success,
        "timestamp": time.time(),
    }
    record.update(kwargs)
    _audit_logger.info(json.dumps(record))


# ---------------------------------------------------------------------------
# Tool-call logging
# ---------------------------------------------------------------------------


def log_tool_call(
    tool_name: str,
    *,
    agent_id: UUID,
    meeting_id: str | UUID | None = None,
    success: bool = True,
    error: str | None = None,
) -> None:
    """Emit a structured tool-call audit record.

    Args:
        tool_name: Name of the MCP tool invoked.
        agent_id: The calling agent's config UUID.
        meeting_id: Meeting context (UUID or string) if applicable.
        success: False if the call failed (validation error, scope denial, etc.).
        error: Short error description when *success* is False.
    """
    record: dict[str, object] = {
        "event": "tool_call",
        "tool": tool_name,
        "agent_id": str(agent_id),
        "meeting_id": str(meeting_id) if meeting_id else None,
        "success": success,
        "error": error,
        "timestamp": time.time(),
    }
    _audit_logger.info(json.dumps(record))


# ---------------------------------------------------------------------------
# Rate-limit logging helper
# ---------------------------------------------------------------------------


def log_rate_limit_exceeded(
    tool_name: str,
    *,
    agent_id: UUID,
    retry_after: int,
) -> None:
    """Emit a rate-limit-exceeded audit record.

    Args:
        tool_name: The throttled tool.
        agent_id: The throttled agent.
        retry_after: Seconds until the window resets.
    """
    record: dict[str, object] = {
        "event": "rate_limit_exceeded",
        "tool": tool_name,
        "agent_id": str(agent_id),
        "retry_after": retry_after,
        "timestamp": time.time(),
    }
    _audit_logger.warning(json.dumps(record))
