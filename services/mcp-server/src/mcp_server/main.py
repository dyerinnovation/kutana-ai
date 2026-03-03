"""Convene AI MCP Server — FastMCP server exposing meeting tools.

Runs as a Streamable HTTP server in a Docker container.
Default endpoint: http://localhost:3001/mcp

Run locally: uv run python -m mcp_server.main
Run via Docker: docker compose up mcp-server
"""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.api_client import ApiClient
from mcp_server.gateway_client import GatewayClient
from mcp_server.settings import MCPServerSettings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

settings = MCPServerSettings()

# Stateless HTTP mode with JSON responses — optimal for Docker / production
mcp = FastMCP(
    "Convene AI",
    instructions="Tools for joining and participating in Convene AI meetings.",
    stateless_http=True,
    json_response=True,
    host=settings.mcp_host,
    port=settings.mcp_port,
)

# Shared state (per-process; stateless_http means no session persistence)
_api_client: ApiClient | None = None
_gateway_client: GatewayClient | None = None


def _get_api_client() -> ApiClient:
    """Get or create the API client singleton."""
    global _api_client
    if _api_client is None:
        if not settings.mcp_api_key:
            raise RuntimeError(
                "MCP_API_KEY not set. Generate an API key in the Convene dashboard."
            )
        _api_client = ApiClient(settings.api_base_url, settings.mcp_api_key)
    return _api_client


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_meetings() -> str:
    """List available meetings.

    Returns a JSON array of meetings with their IDs, titles, and status.
    Use this to find meetings to join.
    """
    client = _get_api_client()
    meetings = await client.list_meetings()
    return json.dumps(meetings, indent=2, default=str)


@mcp.tool()
async def join_meeting(
    meeting_id: str,
    capabilities: list[str] | None = None,
) -> str:
    """Join a meeting via the Convene Agent Gateway.

    This exchanges the API key for a gateway token, connects via WebSocket,
    and joins the specified meeting. Transcript segments will be buffered
    automatically.

    Args:
        meeting_id: UUID of the meeting to join.
        capabilities: Optional list of capabilities to request
                      (default: ["listen", "transcribe"]).

    Returns:
        JSON string with join confirmation details.
    """
    global _gateway_client

    if _gateway_client is not None and _gateway_client.meeting_id is not None:
        return json.dumps({
            "error": "Already in a meeting. Call leave_meeting() first.",
            "current_meeting_id": _gateway_client.meeting_id,
        })

    client = _get_api_client()

    # Exchange API key for gateway JWT
    token = await client.exchange_for_gateway_token()

    # Connect to gateway and join meeting
    _gateway_client = GatewayClient(settings.gateway_ws_url, token)
    result = await _gateway_client.connect_and_join(
        meeting_id=meeting_id,
        capabilities=capabilities,
    )

    return json.dumps(result, indent=2, default=str)


@mcp.tool()
async def leave_meeting() -> str:
    """Leave the current meeting and disconnect from the gateway.

    Returns:
        Confirmation message.
    """
    global _gateway_client

    if _gateway_client is None or _gateway_client.meeting_id is None:
        return json.dumps({"status": "not_in_meeting"})

    meeting_id = _gateway_client.meeting_id
    await _gateway_client.leave()
    _gateway_client = None

    return json.dumps({"status": "left", "meeting_id": meeting_id})


@mcp.tool()
async def get_transcript(last_n: int = 50) -> str:
    """Get recent transcript segments from the current meeting.

    Transcript segments are buffered automatically while connected
    to a meeting. This returns the most recent segments.

    Args:
        last_n: Maximum number of recent segments to return (default 50).

    Returns:
        JSON array of transcript segments with text, speaker, timestamps.
    """
    if _gateway_client is None or _gateway_client.meeting_id is None:
        return json.dumps({"error": "Not in a meeting. Call join_meeting() first."})

    segments = _gateway_client.get_transcript(last_n=last_n)
    return json.dumps(segments, indent=2, default=str)


@mcp.tool()
async def get_tasks(meeting_id: str) -> str:
    """Get tasks for a specific meeting.

    Args:
        meeting_id: UUID of the meeting.

    Returns:
        JSON array of tasks.
    """
    client = _get_api_client()
    tasks = await client.get_tasks(meeting_id)
    return json.dumps(tasks, indent=2, default=str)


@mcp.tool()
async def create_task(
    meeting_id: str,
    description: str,
    priority: str = "medium",
) -> str:
    """Create a new task for a meeting.

    Use this to track action items, follow-ups, and decisions
    extracted from the meeting transcript.

    Args:
        meeting_id: UUID of the meeting this task relates to.
        description: Clear description of what needs to be done.
        priority: Task priority — one of: low, medium, high, critical.

    Returns:
        JSON object of the created task.
    """
    client = _get_api_client()
    task = await client.create_task(meeting_id, description, priority)
    return json.dumps(task, indent=2, default=str)


@mcp.tool()
async def get_participants() -> str:
    """Get the list of participants in the current meeting.

    Returns:
        JSON array of participant information.
    """
    if _gateway_client is None or _gateway_client.meeting_id is None:
        return json.dumps({"error": "Not in a meeting. Call join_meeting() first."})

    participants = _gateway_client.get_participants()
    return json.dumps(participants, indent=2, default=str)


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------


@mcp.resource("meeting://{meeting_id}")
async def meeting_resource(meeting_id: str) -> str:
    """Get details for a specific meeting.

    Args:
        meeting_id: UUID of the meeting.

    Returns:
        JSON string with meeting details.
    """
    info: dict[str, Any] = {"meeting_id": meeting_id}
    if _gateway_client and _gateway_client.meeting_id == meeting_id:
        info["connected"] = True
        info["transcript_count"] = len(_gateway_client.get_transcript(last_n=9999))
        info["participants"] = _gateway_client.get_participants()
    else:
        info["connected"] = False
    return json.dumps(info, indent=2, default=str)


@mcp.resource("meeting://{meeting_id}/transcript")
async def meeting_transcript_resource(meeting_id: str) -> str:
    """Get the full transcript for a meeting.

    Args:
        meeting_id: UUID of the meeting.

    Returns:
        JSON string with all transcript segments.
    """
    if _gateway_client and _gateway_client.meeting_id == meeting_id:
        segments = _gateway_client.get_transcript(last_n=9999)
        return json.dumps(segments, indent=2, default=str)
    return json.dumps({"error": "Not connected to this meeting"})


# ---------------------------------------------------------------------------
# Entry point — Streamable HTTP transport
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info(
        "Starting Convene MCP Server (Streamable HTTP) on %s:%d",
        settings.mcp_host,
        settings.mcp_port,
    )
    mcp.run(transport="streamable-http")
