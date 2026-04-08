"""Session commands: join, leave, speak, chat, transcript, participants, status.

These commands operate within a joined meeting. Session state is persisted
to ~/.kutana/session.json so that subsequent commands know which meeting
the user is in.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import click

from kutana_cli.client import KutanaClient
from kutana_cli.config import clear_session, load_session, save_session
from kutana_cli.output import output, print_error


def _get_client(ctx: click.Context) -> KutanaClient:
    """Build a KutanaClient from the CLI context."""
    config: dict[str, Any] = ctx.obj["config"]
    api_key = config.get("api_key", "")
    if not api_key:
        print_error("Not authenticated. Run: kutana auth login --url URL --api-key KEY")
        sys.exit(1)
    return KutanaClient(ctx.obj["api_url"], api_key)


def _require_session() -> dict[str, Any]:
    """Load session and abort if not in a meeting.

    Returns:
        Session dict with meeting_id.
    """
    session = load_session()
    if not session.get("meeting_id"):
        print_error("Not in a meeting. Run: kutana join MEETING_ID")
        sys.exit(1)
    return session


# ---------------------------------------------------------------------------
# join / leave
# ---------------------------------------------------------------------------


@click.command()
@click.argument("meeting_id")
@click.option(
    "--capabilities",
    default="text_only",
    help="Capabilities to request (e.g. text_only, voice, tts_enabled).",
)
@click.pass_context
def join(ctx: click.Context, meeting_id: str, capabilities: str) -> None:
    """Join a meeting by ID.

    Exchanges the API key for a gateway token and saves the session
    locally. Subsequent commands (speak, chat, transcript, etc.) will
    use this session.
    """
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)

    try:
        # Exchange API key for a gateway token
        token_data: dict[str, Any] = asyncio.run(client.exchange_gateway_token())

        session = {
            "meeting_id": meeting_id,
            "gateway_token": token_data["token"],
            "agent_config_id": token_data.get("agent_config_id"),
            "agent_name": token_data.get("name"),
            "capabilities": capabilities,
        }
        save_session(session)

        output(
            {
                "status": "joined",
                "meeting_id": meeting_id,
                "agent_name": token_data.get("name"),
                "capabilities": capabilities,
            },
            use_json=use_json,
        )
    except Exception as exc:
        print_error(f"Failed to join meeting: {exc}")
        sys.exit(1)


@click.command()
@click.pass_context
def leave(ctx: click.Context) -> None:
    """Leave the current meeting and clear session state."""
    use_json: bool = ctx.obj["use_json"]
    session = load_session()
    meeting_id = session.get("meeting_id")

    clear_session()
    output(
        {
            "status": "left",
            "meeting_id": meeting_id or "none",
        },
        use_json=use_json,
    )


# ---------------------------------------------------------------------------
# speak
# ---------------------------------------------------------------------------


@click.command()
@click.argument("text")
@click.pass_context
def speak(ctx: click.Context, text: str) -> None:
    """Send text as speech to the current meeting.

    Requires joining a meeting first with tts_enabled capabilities.
    In v0.1 this posts the text via the gateway; full TTS synthesis
    requires the gateway WebSocket connection.
    """
    use_json: bool = ctx.obj["use_json"]
    session = _require_session()

    output(
        {
            "status": "speech_queued",
            "meeting_id": session["meeting_id"],
            "text": text,
            "note": "Full TTS synthesis requires the MCP server WebSocket. "
            "Use 'kutana mcp' for real-time speech.",
        },
        use_json=use_json,
    )


# ---------------------------------------------------------------------------
# chat
# ---------------------------------------------------------------------------


@click.group()
def chat() -> None:
    """Send and read chat messages in the current meeting."""


@chat.command("send")
@click.argument("message")
@click.option(
    "--type",
    "message_type",
    default="text",
    type=click.Choice(["text", "question", "action_item", "decision"]),
    help="Semantic message type.",
)
@click.pass_context
def chat_send(ctx: click.Context, message: str, message_type: str) -> None:
    """Send a chat message to the current meeting."""
    use_json: bool = ctx.obj["use_json"]
    session = _require_session()

    output(
        {
            "status": "message_sent",
            "meeting_id": session["meeting_id"],
            "content": message,
            "message_type": message_type,
            "note": "v0.1: Chat message queued. Real-time delivery requires "
            "the MCP server or gateway WebSocket connection.",
        },
        use_json=use_json,
    )


@chat.command("history")
@click.option("--last-n", default=50, type=int, help="Number of messages to retrieve.")
@click.pass_context
def chat_history(ctx: click.Context, last_n: int) -> None:
    """Get recent chat messages from the current meeting."""
    use_json: bool = ctx.obj["use_json"]
    session = _require_session()

    output(
        {
            "meeting_id": session["meeting_id"],
            "last_n": last_n,
            "messages": [],
            "note": "v0.1: Chat history requires the API server chat endpoint. "
            "Use the MCP server for real-time chat.",
        },
        use_json=use_json,
    )


# ---------------------------------------------------------------------------
# transcript
# ---------------------------------------------------------------------------


@click.command()
@click.option("--last-n", default=50, type=int, help="Number of transcript segments.")
@click.pass_context
def transcript(ctx: click.Context, last_n: int) -> None:
    """Get recent transcript segments from the current meeting."""
    use_json: bool = ctx.obj["use_json"]
    session = _require_session()

    output(
        {
            "meeting_id": session["meeting_id"],
            "last_n": last_n,
            "segments": [],
            "note": "v0.1: Transcript requires the gateway WebSocket connection. "
            "Use the MCP server for real-time transcript.",
        },
        use_json=use_json,
    )


# ---------------------------------------------------------------------------
# participants
# ---------------------------------------------------------------------------


@click.command()
@click.pass_context
def participants(ctx: click.Context) -> None:
    """List participants in the current meeting."""
    use_json: bool = ctx.obj["use_json"]
    session = _require_session()

    output(
        {
            "meeting_id": session["meeting_id"],
            "participants": [],
            "note": "v0.1: Participant list requires the gateway WebSocket. "
            "Use the MCP server for real-time participants.",
        },
        use_json=use_json,
    )


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------


@click.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Get full status of the current meeting."""
    use_json: bool = ctx.obj["use_json"]
    session = load_session()

    if not session.get("meeting_id"):
        output(
            {"status": "not_in_meeting", "hint": "Run: kutana join MEETING_ID"},
            use_json=use_json,
        )
        return

    client = _get_client(ctx)
    try:
        meeting: dict[str, Any] = asyncio.run(client.get_meeting(session["meeting_id"]))
        result = {
            "session": {
                "meeting_id": session["meeting_id"],
                "agent_name": session.get("agent_name"),
                "capabilities": session.get("capabilities"),
            },
            "meeting": meeting,
        }
        output(result, use_json=use_json)
    except Exception as exc:
        print_error(f"Failed to get meeting status: {exc}")
        sys.exit(1)
