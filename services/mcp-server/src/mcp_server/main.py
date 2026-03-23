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

from convene_providers.chat.redis_chat_store import RedisChatStore
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
_chat_store: RedisChatStore | None = None


def _get_turn_manager() -> RedisTurnManager:
    """Get or create the TurnManager singleton."""
    global _turn_manager
    if _turn_manager is None:
        redis_client = aioredis.from_url(settings.redis_url)
        _turn_manager = RedisTurnManager(redis_client)
    return _turn_manager


def _get_chat_store() -> RedisChatStore:
    """Get or create the ChatStore singleton."""
    global _chat_store
    if _chat_store is None:
        _chat_store = RedisChatStore(redis_url=settings.redis_url)
    return _chat_store


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


@mcp.tool()
async def get_channel_messages(channel: str, last_n: int = 50) -> str:
    """Get buffered messages received on a data channel.

    Returns messages that arrived on the channel since you subscribed.
    Call subscribe_channel(channel) first to start receiving messages.

    Args:
        channel: Channel name to read from.
        last_n: Maximum number of recent messages to return (default 50).

    Returns:
        JSON array of channel message payloads in order received.
    """
    if _gateway_client is None or _gateway_client.meeting_id is None:
        return json.dumps({"error": "Not in a meeting. Call join_meeting() first."})

    messages = _gateway_client.get_channel_messages(channel, last_n=last_n)
    return json.dumps(messages, indent=2, default=str)


@mcp.tool()
async def get_meeting_events(last_n: int = 50, event_type: str | None = None) -> str:
    """Get recent meeting events pushed by the gateway WebSocket connection.

    Returns real-time events buffered since you joined: turn queue changes,
    speaker transitions, participant joins/leaves, and chat messages.

    These events are pushed by the gateway as they happen — this tool lets
    you poll the buffer to see what has occurred since you last checked.

    Args:
        last_n: Maximum number of recent events to return (default 50).
        event_type: Optional filter. One of:
                    "turn_queue_updated" — speaker queue changed,
                    "turn_speaker_changed" — active speaker changed,
                    "turn_your_turn" — it is now your turn to speak,
                    "participant_update" — someone joined or left,
                    "chat_message" — a chat message was sent.

    Returns:
        JSON array of event objects in order received.
    """
    if _gateway_client is None or _gateway_client.meeting_id is None:
        return json.dumps({"error": "Not in a meeting. Call join_meeting() first."})

    events = _gateway_client.get_events(last_n=last_n, event_type=event_type)
    return json.dumps(events, indent=2, default=str)


# ---------------------------------------------------------------------------
# Turn Management Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def start_speaking(meeting_id: str) -> str:
    """Confirm you have the floor and are now actively speaking.

    Call this after raise_hand() returns queue_position=0 (immediate promotion)
    or after receiving a turn_your_turn event from get_meeting_events().

    This is a state-check / acknowledgement step in the turn workflow:
      raise_hand → [wait for turn_your_turn] → start_speaking → [speak] → mark_finished_speaking

    Args:
        meeting_id: UUID of the meeting.

    Returns:
        JSON with status "speaking" if you are the active speaker, or an
        error with guidance if you are not yet the active speaker.
    """
    identity = await _ensure_authenticated()
    tm = _get_turn_manager()
    mid = UUID(meeting_id)
    pid = identity.agent_config_id

    status = await tm.get_speaking_status(mid, pid)
    if not status.is_speaking:
        queue_info = ""
        if status.in_queue and status.queue_position is not None:
            queue_info = f" You are #{status.queue_position} in queue."
        return json.dumps({
            "error": f"Not the active speaker.{queue_info} "
                     "Call raise_hand() and wait for a turn_your_turn event.",
            "is_in_queue": status.in_queue,
            "queue_position": status.queue_position,
        })

    return json.dumps({
        "status": "speaking",
        "meeting_id": meeting_id,
        "message": "You have the floor. Call mark_finished_speaking() when done.",
    })


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
# Chat & Status Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def send_chat_message(
    meeting_id: str,
    content: str,
    message_type: str = "text",
) -> str:
    """Send a chat message to a meeting.

    Posts a message to the meeting's chat channel. All participants
    connected to the meeting (via WebSocket or MCP) will receive it.

    Args:
        meeting_id: UUID of the meeting.
        content: The message text to send.
        message_type: Semantic type — one of: text, question, action_item, decision.
                      Use "question" when asking something, "action_item" for tasks
                      to track, "decision" for recorded decisions, "text" for general chat.

    Returns:
        JSON object with the stored message details including message_id and sent_at.
    """
    from convene_core.models.chat import ChatMessageType

    identity = await _ensure_authenticated()
    cs = _get_chat_store()
    mid = UUID(meeting_id)

    try:
        msg_type = ChatMessageType(message_type)
    except ValueError:
        return json.dumps({"error": f"Invalid message_type '{message_type}'. Must be one of: text, question, action_item, decision."})

    msg = await cs.send_message(
        meeting_id=mid,
        sender_id=identity.agent_config_id,
        sender_name=identity.name,
        content=content,
        message_type=msg_type,
    )

    return json.dumps({
        "message_id": str(msg.message_id),
        "meeting_id": str(msg.meeting_id),
        "sender_id": str(msg.sender_id),
        "sender_name": msg.sender_name,
        "content": msg.content,
        "message_type": msg.message_type.value,
        "sent_at": msg.sent_at.isoformat(),
        "sequence": msg.sequence,
    })


@mcp.tool()
async def get_chat_messages(
    meeting_id: str,
    limit: int = 50,
    message_type: str | None = None,
    since: str | None = None,
) -> str:
    """Get chat messages from a meeting.

    Retrieves chat history in chronological order. Supports filtering
    by message type and returning only messages after a given timestamp.

    Args:
        meeting_id: UUID of the meeting.
        limit: Maximum number of messages to return (default 50, max 200).
        message_type: Filter by type — one of: text, question, action_item, decision.
                      Omit or pass null to return all types.
        since: ISO 8601 datetime string — only return messages after this time.
               Example: "2026-03-23T14:30:00Z"

    Returns:
        JSON array of chat messages in chronological order (oldest first).
    """
    from datetime import datetime
    from convene_core.models.chat import ChatMessageType

    await _ensure_authenticated()
    cs = _get_chat_store()
    mid = UUID(meeting_id)

    # Validate and clamp limit
    limit = max(1, min(limit, 200))

    # Parse optional message_type filter
    type_filter: ChatMessageType | None = None
    if message_type is not None:
        try:
            type_filter = ChatMessageType(message_type)
        except ValueError:
            return json.dumps({"error": f"Invalid message_type '{message_type}'."})

    # Parse optional since timestamp
    since_dt: datetime | None = None
    if since is not None:
        try:
            since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError:
            return json.dumps({"error": f"Invalid since timestamp '{since}'. Use ISO 8601 format."})

    messages = await cs.get_messages(
        meeting_id=mid,
        limit=limit,
        message_type=type_filter,
        since=since_dt,
    )

    return json.dumps(
        [
            {
                "message_id": str(m.message_id),
                "sender_id": str(m.sender_id),
                "sender_name": m.sender_name,
                "content": m.content,
                "message_type": m.message_type.value,
                "sent_at": m.sent_at.isoformat(),
                "sequence": m.sequence,
            }
            for m in messages
        ],
        indent=2,
    )


@mcp.tool()
async def get_meeting_status(meeting_id: str) -> str:
    """Get a comprehensive status snapshot for a meeting.

    Returns the current state of the meeting including:
    - Meeting metadata (title, status, start time)
    - Active speaker and speaker queue
    - Connected participants (if you are joined via WebSocket)
    - Recent chat messages (last 10)

    Use this to orient yourself when joining a meeting mid-session,
    or to get a quick overview of the current meeting state.

    Args:
        meeting_id: UUID of the meeting.

    Returns:
        JSON object with meeting, queue, participants, and recent_chat fields.
    """
    await _ensure_authenticated()
    tm = _get_turn_manager()
    cs = _get_chat_store()
    client = _get_api_client()
    mid = UUID(meeting_id)

    # Gather meeting info, queue status, and recent chat concurrently
    import asyncio as _asyncio

    meetings_task = _asyncio.create_task(client.list_meetings())
    queue_task = _asyncio.create_task(tm.get_queue_status(mid))
    chat_task = _asyncio.create_task(cs.get_messages(mid, limit=10))

    meetings, queue_status, recent_messages = await _asyncio.gather(
        meetings_task, queue_task, chat_task
    )

    # Find the specific meeting from the list
    meeting_data: dict[str, Any] | None = None
    for m in meetings:
        if str(m.get("id", "")) == meeting_id:
            meeting_data = m
            break

    # Participants from gateway client (if connected)
    participants: list[Any] = []
    if _gateway_client is not None and _gateway_client.meeting_id == meeting_id:
        participants = _gateway_client.get_participants()

    return json.dumps(
        {
            "meeting": meeting_data,
            "queue": {
                "active_speaker": str(queue_status.active_speaker_id) if queue_status.active_speaker_id else None,
                "queue_length": len(queue_status.queue),
                "entries": [
                    {
                        "position": e.position,
                        "participant_id": str(e.participant_id),
                        "priority": e.priority.value,
                        "topic": e.topic,
                    }
                    for e in queue_status.queue
                ],
            },
            "participants": participants,
            "recent_chat": [
                {
                    "sender_name": m.sender_name,
                    "content": m.content,
                    "message_type": m.message_type.value,
                    "sent_at": m.sent_at.isoformat(),
                }
                for m in recent_messages
            ],
        },
        indent=2,
        default=str,
    )


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
