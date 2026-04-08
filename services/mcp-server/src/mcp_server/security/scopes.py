"""JWT scope definitions and per-tool scope enforcement for the MCP server.

Scopes follow the pattern <resource>:<action>:
    meetings:read    — list meetings, read transcript, read chat, get status
    meetings:join    — join/leave meetings, create meetings
    meetings:chat    — send chat messages, publish to channels
    turns:manage     — raise hand, mark finished, cancel hand raise
    tasks:write      — create and update tasks

Default scopes (new API keys): meetings:read, meetings:join
Full scopes require explicit grant via API key configuration.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp_server.auth import MCPIdentity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Scope constants
# ---------------------------------------------------------------------------

SCOPE_MEETINGS_READ = "meetings:read"
SCOPE_MEETINGS_JOIN = "meetings:join"
SCOPE_MEETINGS_CHAT = "meetings:chat"
SCOPE_TURNS_MANAGE = "turns:manage"
SCOPE_TASKS_WRITE = "tasks:write"

# Default scopes granted to new API keys (limited)
DEFAULT_SCOPES: list[str] = [SCOPE_MEETINGS_READ, SCOPE_MEETINGS_JOIN]

# Full set of scopes — requires explicit grant
ALL_SCOPES: list[str] = [
    SCOPE_MEETINGS_READ,
    SCOPE_MEETINGS_JOIN,
    SCOPE_MEETINGS_CHAT,
    SCOPE_TURNS_MANAGE,
    SCOPE_TASKS_WRITE,
]

# ---------------------------------------------------------------------------
# Tool → required scope mapping
# ---------------------------------------------------------------------------

TOOL_REQUIRED_SCOPE: dict[str, str] = {
    # Read-only access
    "list_meetings": SCOPE_MEETINGS_READ,
    "get_transcript": SCOPE_MEETINGS_READ,
    "get_tasks": SCOPE_MEETINGS_READ,
    "get_participants": SCOPE_MEETINGS_READ,
    "get_queue_status": SCOPE_MEETINGS_READ,
    "get_speaking_status": SCOPE_MEETINGS_READ,
    "get_chat_messages": SCOPE_MEETINGS_READ,
    "get_meeting_status": SCOPE_MEETINGS_READ,
    "get_channel_messages": SCOPE_MEETINGS_READ,
    "get_meeting_events": SCOPE_MEETINGS_READ,
    "get_summary": SCOPE_MEETINGS_READ,
    "subscribe_channel": SCOPE_MEETINGS_READ,
    # Join/leave meetings
    "join_meeting": SCOPE_MEETINGS_JOIN,
    "leave_meeting": SCOPE_MEETINGS_JOIN,
    "join_or_create_meeting": SCOPE_MEETINGS_JOIN,
    "create_new_meeting": SCOPE_MEETINGS_JOIN,
    "start_meeting_session": SCOPE_MEETINGS_JOIN,
    "end_meeting_session": SCOPE_MEETINGS_JOIN,
    # Chat / context — requires explicit grant
    "send_chat_message": SCOPE_MEETINGS_CHAT,
    "publish_to_channel": SCOPE_MEETINGS_CHAT,
    "set_context": SCOPE_MEETINGS_CHAT,
    # Turn management — requires explicit grant
    "raise_hand": SCOPE_TURNS_MANAGE,
    "mark_finished_speaking": SCOPE_TURNS_MANAGE,
    "cancel_hand_raise": SCOPE_TURNS_MANAGE,
    "speak": SCOPE_TURNS_MANAGE,
    # Task creation — requires explicit grant
    "create_task": SCOPE_TASKS_WRITE,
}


def require_scope(identity: MCPIdentity, tool_name: str) -> str | None:
    """Check that *identity* holds the scope required for *tool_name*.

    Args:
        identity: The validated MCPIdentity from the JWT.
        tool_name: The name of the MCP tool being invoked.

    Returns:
        None if the scope check passes.
        A JSON error string (suitable for returning from a tool) if it fails.
    """
    required = TOOL_REQUIRED_SCOPE.get(tool_name)
    if required is None:
        # Unknown tool — allow through (no defined restriction)
        return None

    if required in identity.scopes:
        return None

    logger.warning(
        "scope_violation agent_id=%s tool=%s required=%s granted=%s",
        identity.agent_config_id,
        tool_name,
        required,
        identity.scopes,
    )
    return json.dumps(
        {
            "error": "insufficient_scope",
            "message": (
                f"Scope '{required}' is required to call '{tool_name}'. "
                "Contact your administrator to grant additional scopes."
            ),
            "required_scope": required,
            "granted_scopes": identity.scopes,
        }
    )
