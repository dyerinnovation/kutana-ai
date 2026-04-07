"""Task management commands for the Kutana CLI."""

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
def tasks() -> None:
    """List and create meeting tasks."""


@tasks.command("list")
@click.argument("meeting_id", required=False, default=None)
@click.pass_context
def list_tasks(ctx: click.Context, meeting_id: str | None) -> None:
    """List tasks, optionally filtered by meeting ID.

    If MEETING_ID is provided, only tasks for that meeting are shown.
    Otherwise, all tasks are listed.
    """
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.list_tasks(meeting_id=meeting_id))
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@tasks.command("create")
@click.option("--meeting-id", required=True, help="Meeting UUID this task belongs to.")
@click.option("--title", "description", required=True, help="Task description.")
@click.option("--assignee", "assignee_id", default=None, help="Assignee UUID (optional).")
@click.option(
    "--priority",
    default="medium",
    type=click.Choice(["low", "medium", "high", "critical"]),
    help="Task priority (default: medium).",
)
@click.option("--due-date", default=None, help="Due date in YYYY-MM-DD format (optional).")
@click.pass_context
def create_task(
    ctx: click.Context,
    meeting_id: str,
    description: str,
    assignee_id: str | None,
    priority: str,
    due_date: str | None,
) -> None:
    """Create a new task."""
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(
            client.create_task(
                meeting_id,
                description,
                priority=priority,
                assignee_id=assignee_id,
                due_date=due_date,
            )
        )
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@tasks.command("get")
@click.argument("task_id")
@click.pass_context
def get_task(ctx: click.Context, task_id: str) -> None:
    """Get details for a specific task."""
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.get_task(task_id))
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))


@tasks.command("update-status")
@click.argument("task_id")
@click.option(
    "--status",
    "new_status",
    required=True,
    type=click.Choice(["pending", "in_progress", "completed", "cancelled"]),
    help="New task status.",
)
@click.pass_context
def update_task_status(ctx: click.Context, task_id: str, new_status: str) -> None:
    """Update a task's status."""
    use_json: bool = ctx.obj["use_json"]
    client = _get_client(ctx)
    try:
        data: dict[str, Any] = asyncio.run(client.update_task_status(task_id, new_status))
        output(data, use_json=use_json)
    except Exception as exc:
        print_error(str(exc))
