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
from uuid import UUID

import redis.asyncio as aioredis
from mcp.server.fastmcp import FastMCP

from convene_providers.turn_management.redis_turn_manager import RedisTurnManager
from mcp_server.api_client import ApiClient
from mcp_server.auth import MCPAuthError, MCPIdentity, validate_mcp_token
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
_mcp_identity: MCPIdentity | None = None
_turn_manager: RedisTurnManager | None = None


def _get_turn_manager() -> RedisTurnManager:
    """Get or create the TurnManager singleton."""
    global _turn_manager
    if _turn_manager is None:
        redis_client = aioredis.from_url(settings.redis_url)
        _turn_manager = RedisTurnManager(redis_client)
    return _turn_manager


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


def authenticate_bearer(bearer_token: str) -> MCPIdentity:
    """Validate a Bearer token and cache the identity.

    Args:
        bearer_token: The raw Bearer token (without 'Bearer ' prefix).

    Returns:
        The validated MCPIdentity.

    Raises:
        MCPAuthError: If validation fails.
    """
    global _mcp_identity
    identity = validate_mcp_token(bearer_token, settings.mcp_jwt_secret)
    _mcp_identity = identity
    return identity


async def _ensure_authenticated() -> MCPIdentity:
    """Ensure MCP client is authenticated, exchanging API key for JWT if needed.

    Returns:
        The validated MCPIdentity.

    Raises:
        RuntimeError: If authentication fails.
    """
    global _mcp_identity
    if _mcp_identity is not None:
        return _mcp_identity

    # Auto-exchange API key for MCP JWT on first call
    client = _get_api_client()
    try:
        token = await client.exchange_for_mcp_token()
        return authenticate_bearer(token)
    except (RuntimeError, MCPAuthError) as e:
        raise RuntimeError(f"MCP authentication failed: {e}") from e


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_meetings() -> str:
    """List available meetings.

    Returns a JSON array of meetings with their IDs, titles, and status.
    Use this to find meetings to join.
    """
    await _ensure_authenticated()
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

    await _ensure_authenticated()

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
    await _ensure_authenticated()
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
    await _ensure_authenticated()
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


@mcp.tool()
async def create_new_meeting(
    title: str,
    platform: str = "convene",
) -> str:
    """Create a new meeting.

    Args:
        title: Human-readable meeting title.
        platform: Meeting platform (default: "convene").

    Returns:
        JSON object of the created meeting.
    """
    await _ensure_authenticated()
    client = _get_api_client()
    meeting = await client.create_meeting(title=title, platform=platform)
    return json.dumps(meeting, indent=2, default=str)


@mcp.tool()
async def start_meeting_session(meeting_id: str) -> str:
    """Start a meeting (transition from scheduled to active).

    The meeting must be in 'scheduled' status. This sets the status to 'active'
    and records the start time.

    Args:
        meeting_id: UUID of the meeting to start.

    Returns:
        JSON object of the updated meeting.
    """
    await _ensure_authenticated()
    client = _get_api_client()
    try:
        meeting = await client.start_meeting(meeting_id)
        return json.dumps(meeting, indent=2, default=str)
    except RuntimeError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def end_meeting_session(meeting_id: str) -> str:
    """End a meeting (transition from active to completed).

    The meeting must be in 'active' status. This sets the status to 'completed'
    and records the end time.

    Args:
        meeting_id: UUID of the meeting to end.

    Returns:
        JSON object of the updated meeting.
    """
    await _ensure_authenticated()
    client = _get_api_client()
    try:
        meeting = await client.end_meeting(meeting_id)
        return json.dumps(meeting, indent=2, default=str)
    except RuntimeError as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
async def join_or_create_meeting(
    title: str,
    capabilities: list[str] | None = None,
) -> str:
    """Find an active meeting with the given title and join it, or create a new one.

    This is a convenience tool that:
    1. Lists all meetings
    2. Looks for an active meeting with matching title
    3. If found, joins it; if not, creates a new meeting, starts it, and joins

    Args:
        title: Meeting title to search for or create.
        capabilities: Optional capabilities to request when joining.

    Returns:
        JSON object with meeting details and join status.
    """
    await _ensure_authenticated()
    client = _get_api_client()

    # Search for existing active meeting with this title
    meetings = await client.list_meetings()
    created = False
    meeting_data: dict[str, Any] | None = None
    for m in meetings:
        if m.get("title") == title and m.get("status") == "active":
            meeting_data = m
            break

    if meeting_data is None:
        # Create and start a new meeting
        meeting_data = await client.create_meeting(title=title)
        meeting_id = str(meeting_data["id"])
        meeting_data = await client.start_meeting(meeting_id)
        created = True

    meeting_id = str(meeting_data["id"])

    # Join the meeting
    global _gateway_client
    if _gateway_client is not None and _gateway_client.meeting_id is not None:
        return json.dumps({
            "meeting": meeting_data,
            "join_status": "already_in_meeting",
            "current_meeting_id": _gateway_client.meeting_id,
            "created": created,
        }, indent=2, default=str)

    token = await client.exchange_for_gateway_token()
    _gateway_client = GatewayClient(settings.gateway_ws_url, token)
    join_result = await _gateway_client.connect_and_join(
        meeting_id=meeting_id,
        capabilities=capabilities,
    )

    return json.dumps({
        "meeting": meeting_data,
        "join_result": join_result,
        "created": created,
    }, indent=2, default=str)


@mcp.tool()
async def subscribe_channel(channel: str) -> str:
    """Subscribe to a data channel in the current meeting.

    Data channels allow agents to exchange structured messages.
    After subscribing, you will receive events on this channel
    via the gateway WebSocket connection.

    Args:
        channel: Channel name to subscribe to (e.g., "tasks", "decisions", "summaries").

    Returns:
        Confirmation of subscription.
    """
    if _gateway_client is None or _gateway_client.meeting_id is None:
        return json.dumps({"error": "Not in a meeting. Call join_meeting() first."})

    _gateway_client.subscribe_channel(channel)
    return json.dumps({
        "status": "subscribed",
        "channel": channel,
        "subscribed_channels": list(_gateway_client.subscribed_channels),
    })


@mcp.tool()
async def publish_to_channel(channel: str, payload: dict[str, Any]) -> str:
    """Publish a message to a data channel in the current meeting.

    Other agents subscribed to this channel will receive the message.

    Args:
        channel: Channel name to publish to.
        payload: JSON-serializable data to publish.

    Returns:
        Confirmation of publication.
    """
    if _gateway_client is None or _gateway_client.meeting_id is None:
        return json.dumps({"error": "Not in a meeting. Call join_meeting() first."})

    await _gateway_client.publish_to_channel(channel, payload)
    return json.dumps({"status": "published", "channel": channel})


# ---------------------------------------------------------------------------
# Turn Management Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def raise_hand(
    meeting_id: str,
    priority: str = "normal",
    topic: str | None = None,
) -> str:
    """Raise your hand to request a turn to speak in a meeting.

    Adds you to the speaker queue. If no one is currently speaking,
    you are immediately promoted to active speaker.

    Args:
        meeting_id: UUID of the meeting.
        priority: Queue priority — "normal" (FIFO) or "urgent" (front of queue).
        topic: Optional short description of what you want to discuss.

    Returns:
        JSON with queue_position, hand_raise_id, estimated_wait, current_speaker.
        queue_position=0 means you were immediately promoted to active speaker.
    """
    identity = await _ensure_authenticated()
    tm = _get_turn_manager()
    mid = UUID(meeting_id)
    pid = identity.agent_config_id

    result = await tm.raise_hand(mid, pid, priority=priority, topic=topic)
    current_speaker_id = await tm.get_active_speaker(mid)

    return json.dumps({
        "queue_position": result.queue_position,
        "hand_raise_id": str(result.hand_raise_id),
        "estimated_wait": None,
        "current_speaker": str(current_speaker_id) if current_speaker_id else None,
    })


@mcp.tool()
async def get_queue_status(meeting_id: str) -> str:
    """Get the current speaker queue status for a meeting.

    Shows who is currently speaking, who is waiting, and your position.

    Args:
        meeting_id: UUID of the meeting.

    Returns:
        JSON with current_speaker, ordered queue entries with positions,
        your_position (null if not in queue), and total_in_queue.
    """
    identity = await _ensure_authenticated()
    tm = _get_turn_manager()
    mid = UUID(meeting_id)
    pid = identity.agent_config_id

    status = await tm.get_queue_status(mid)

    your_position: int | None = None
    for entry in status.queue:
        if entry.participant_id == pid:
            your_position = entry.position
            break

    return json.dumps({
        "current_speaker": str(status.active_speaker_id) if status.active_speaker_id else None,
        "queue": [
            {
                "position": e.position,
                "participant_id": str(e.participant_id),
                "priority": e.priority.value,
                "topic": e.topic,
                "raised_at": e.raised_at.isoformat(),
            }
            for e in status.queue
        ],
        "your_position": your_position,
        "total_in_queue": len(status.queue),
    })


@mcp.tool()
async def mark_finished_speaking(meeting_id: str) -> str:
    """Signal that you have finished speaking, advancing the queue.

    Removes you as the active speaker and promotes the next participant
    in the queue. If the queue is empty, the floor becomes open.

    This is a no-op if you are not the current active speaker.

    Args:
        meeting_id: UUID of the meeting.

    Returns:
        JSON with status, next_speaker (UUID or null), and queue_remaining count.
    """
    identity = await _ensure_authenticated()
    tm = _get_turn_manager()
    mid = UUID(meeting_id)
    pid = identity.agent_config_id

    next_speaker_id = await tm.mark_finished_speaking(mid, pid)
    queue_status = await tm.get_queue_status(mid)

    return json.dumps({
        "status": "finished",
        "next_speaker": str(next_speaker_id) if next_speaker_id else None,
        "queue_remaining": len(queue_status.queue),
    })


@mcp.tool()
async def cancel_hand_raise(
    meeting_id: str,
    hand_raise_id: str | None = None,
) -> str:
    """Withdraw from the speaker queue (lower your hand).

    Removes you from the queue. If hand_raise_id is provided, cancels
    that specific hand raise; otherwise cancels your current hand raise.

    Args:
        meeting_id: UUID of the meeting.
        hand_raise_id: Specific hand raise UUID to cancel (optional).

    Returns:
        JSON with status ("cancelled" or "not_in_queue") and was_position.
    """
    identity = await _ensure_authenticated()
    tm = _get_turn_manager()
    mid = UUID(meeting_id)
    pid = identity.agent_config_id

    speaking_status = await tm.get_speaking_status(mid, pid)
    was_position = speaking_status.queue_position

    hrid: UUID | None = UUID(hand_raise_id) if hand_raise_id else None
    removed = await tm.cancel_hand_raise(mid, pid, hrid)

    return json.dumps({
        "status": "cancelled" if removed else "not_in_queue",
        "was_position": was_position,
    })


@mcp.tool()
async def get_speaking_status(meeting_id: str) -> str:
    """Check your current speaking status in a meeting.

    Returns whether you are the active speaker, in the queue,
    and who is currently speaking.

    Args:
        meeting_id: UUID of the meeting.

    Returns:
        JSON with is_speaking, is_in_queue, queue_position, current_speaker,
        and meeting_phase.
    """
    identity = await _ensure_authenticated()
    tm = _get_turn_manager()
    mid = UUID(meeting_id)
    pid = identity.agent_config_id

    status = await tm.get_speaking_status(mid, pid)
    current_speaker_id = await tm.get_active_speaker(mid)

    return json.dumps({
        "is_speaking": status.is_speaking,
        "is_in_queue": status.in_queue,
        "queue_position": status.queue_position,
        "current_speaker": str(current_speaker_id) if current_speaker_id else None,
        "meeting_phase": "active",
    })


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
