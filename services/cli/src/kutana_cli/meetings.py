"""Meeting management commands for the Kutana CLI."""

from __future__ import annotations

import asyncio
from typing import Any

import click

from kutana_cli.client import KutanaClient
from kutana_cli.output import output, print_error


def _get_client(ctx: click.Context) -> KutanaClient:
    """Build a KutanaClient from the CLI context.

    Args:
        ctx: Click context with ``config`` and ``api_url``.

    Returns:
        Configured KutanaClient instance.
    """
    config: dict[str, Any] = ctx.obj["config"]
    api_key = config.get("api_key", "")
    if not api_key:
        print_error("Not authenticated. Run: kutana auth login --url URL --api-key KEY")
    return KutanaClient(ctx.obj["api_url"], api_key)


@click.group()
def meetings() -> None:
    """Create, list, and inspect meetings."""


@meetings.command("list")
@click.pass_context
def list_meetings(ctx: click.Context) -> None:
    """List meetings you own or are invited to."""
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.list_meetings())
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@meetings.command("create")
@click.option("--title", required=True, help="Meeting title.")
@click.option("--scheduled-at", default=None, help="ISO 8601 datetime (defaults to now).")
@click.option("--platform", default="kutana", help="Platform name (default: kutana).")
@click.pass_context
def create_meeting(
    ctx: click.Context,
    title: str,
    scheduled_at: str | None,
    platform: str,
) -> None:
    """Create a new meeting."""
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(
            client.create_meeting(title, scheduled_at=scheduled_at, platform=platform)
        )
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@meetings.command("get")
@click.argument("meeting_id")
@click.pass_context
def get_meeting(ctx: click.Context, meeting_id: str) -> None:
    """Get details for a specific meeting."""
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.get_meeting(meeting_id))
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@meetings.command("start")
@click.argument("meeting_id")
@click.pass_context
def start_meeting(ctx: click.Context, meeting_id: str) -> None:
    """Start a meeting (scheduled -> active)."""
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.start_meeting(meeting_id))
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@meetings.command("end")
@click.argument("meeting_id")
@click.pass_context
def end_meeting(ctx: click.Context, meeting_id: str) -> None:
    """End a meeting (active -> completed)."""
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.end_meeting(meeting_id))
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@meetings.command("summary")
@click.argument("meeting_id")
@click.pass_context
def get_summary(ctx: click.Context, meeting_id: str) -> None:
    """Get or generate a meeting summary."""
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.get_summary(meeting_id))
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))
