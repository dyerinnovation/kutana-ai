"""Turn management commands for the Kutana CLI.

Commands interact with the REST turn-management endpoints on the API server,
which proxy to the RedisTurnManager. An active session (``kutana join``) is
required so the CLI knows which meeting to target.
"""

from __future__ import annotations

import asyncio
import sys
from typing import Any

import click

from kutana_cli.client import KutanaClient
from kutana_cli.config import load_session
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
    """Load session and abort if not in a meeting."""
    session = load_session()
    if not session.get("meeting_id"):
        print_error("Not in a meeting. Run: kutana join MEETING_ID")
        sys.exit(1)
    return session


@click.group()
def turn() -> None:
    """Manage the speaker turn queue."""


@turn.command("raise")
@click.option(
    "--priority",
    default="normal",
    type=click.Choice(["normal", "urgent"]),
    help="Queue priority (default: normal).",
)
@click.option("--topic", default=None, help="Topic you want to discuss.")
@click.pass_context
def raise_hand(ctx: click.Context, priority: str, topic: str | None) -> None:
    """Raise your hand to request a speaking turn."""
    use_json: bool = ctx.obj["use_json"]
    session = _require_session()
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(
            client.raise_hand(session["meeting_id"], priority=priority, topic=topic)
        )
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@turn.command("status")
@click.pass_context
def turn_status(ctx: click.Context) -> None:
    """Show the current speaker queue."""
    use_json: bool = ctx.obj["use_json"]
    session = _require_session()
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.get_turn_status(session["meeting_id"]))
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@turn.command("finish")
@click.pass_context
def finish_turn(ctx: click.Context) -> None:
    """Mark your speaking turn as finished."""
    use_json: bool = ctx.obj["use_json"]
    session = _require_session()
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.finish_turn(session["meeting_id"]))
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@turn.command("cancel")
@click.pass_context
def cancel_turn(ctx: click.Context) -> None:
    """Cancel your raised hand."""
    use_json: bool = ctx.obj["use_json"]
    session = _require_session()
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.cancel_hand(session["meeting_id"]))
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))
