"""Embedded MCP stdio server for the Kutana CLI.

Starts a lightweight MCP server over stdio transport, exposing Kutana API
tools for AI agent integration.  Auth uses the same config as the CLI
(``~/.kutana/config.json``).
"""

from __future__ import annotations

import json
from typing import Any

import click

from kutana_cli.config import get_api_url

ALL_GROUPS = frozenset({"meetings", "tasks", "chat", "transcript", "turns"})


def _resolve_groups(tools_arg: str) -> set[str]:
    """Parse the ``--tools`` flag into a set of tool group names."""
    if tools_arg == "all":
        return set(ALL_GROUPS)
    groups = {g.strip() for g in tools_arg.split(",")}
    unknown = groups - ALL_GROUPS
    if unknown:
        raise click.BadParameter(
            f"Unknown tool groups: {', '.join(sorted(unknown))}. "
            f"Valid: {', '.join(sorted(ALL_GROUPS))}"
        )
    return groups


def _build_server(groups: set[str], config: dict[str, Any]) -> Any:
    """Build a FastMCP server with tools filtered by *groups*."""
    from mcp.server.fastmcp import FastMCP

    from kutana_cli.client import KutanaClient

    api_url = get_api_url(config)
    api_key: str = config.get("api_key", "")
    if not api_key:
        raise click.ClickException(
            "No API key configured. Run 'kutana auth login --api-key <key>' first."
        )

    client = KutanaClient(api_url, api_key)
    server = FastMCP("kutana", description="Kutana AI meeting tools via CLI")

    # ------------------------------------------------------------------
    # meetings
    # ------------------------------------------------------------------
    if "meetings" in groups:

        @server.tool()
        async def kutana_list_meetings() -> str:
            """List meetings the authenticated agent has access to.

            Returns JSON with ``items`` array and ``total`` count.
            """
            return json.dumps(await client.list_meetings())

        @server.tool()
        async def kutana_create_meeting(
            title: str,
            platform: str = "kutana",
            scheduled_at: str | None = None,
        ) -> str:
            """Create a new meeting.

            Args:
                title: Human-readable meeting title (max 200 chars).
                platform: Meeting platform (default ``kutana``).
                scheduled_at: ISO 8601 datetime string. Defaults to now.
            """
            return json.dumps(
                await client.create_meeting(title, platform=platform, scheduled_at=scheduled_at)
            )

        @server.tool()
        async def kutana_get_meeting(meeting_id: str) -> str:
            """Get a single meeting by ID.

            Args:
                meeting_id: Meeting UUID.
            """
            return json.dumps(await client.get_meeting(meeting_id))

        @server.tool()
        async def kutana_start_meeting(meeting_id: str) -> str:
            """Start a meeting (scheduled -> active).

            Args:
                meeting_id: Meeting UUID.
            """
            return json.dumps(await client.start_meeting(meeting_id))

        @server.tool()
        async def kutana_end_meeting(meeting_id: str) -> str:
            """End a meeting (active -> completed).

            Args:
                meeting_id: Meeting UUID.
            """
            return json.dumps(await client.end_meeting(meeting_id))

        @server.tool()
        async def kutana_get_summary(meeting_id: str) -> str:
            """Get or generate a meeting summary.

            Args:
                meeting_id: Meeting UUID.

            Returns JSON summary with title, duration, key points, decisions.
            """
            return json.dumps(await client.get_summary(meeting_id))

    # ------------------------------------------------------------------
    # tasks
    # ------------------------------------------------------------------
    if "tasks" in groups:

        @server.tool()
        async def kutana_list_tasks(meeting_id: str | None = None) -> str:
            """List tasks, optionally filtered by meeting.

            Args:
                meeting_id: Optional meeting UUID to filter tasks.
            """
            return json.dumps(await client.list_tasks(meeting_id))

        @server.tool()
        async def kutana_create_task(
            meeting_id: str,
            description: str,
            priority: str = "medium",
            assignee_id: str | None = None,
            due_date: str | None = None,
        ) -> str:
            """Create a task / action item for a meeting.

            Args:
                meeting_id: Meeting UUID.
                description: Task description (max 200 chars).
                priority: Priority level (low, medium, high, critical).
                assignee_id: Optional assignee UUID.
                due_date: Optional due date (YYYY-MM-DD).
            """
            return json.dumps(
                await client.create_task(
                    meeting_id,
                    description,
                    priority=priority,
                    assignee_id=assignee_id,
                    due_date=due_date,
                )
            )

        @server.tool()
        async def kutana_get_task(task_id: str) -> str:
            """Get a single task by ID.

            Args:
                task_id: Task UUID.
            """
            return json.dumps(await client.get_task(task_id))

        @server.tool()
        async def kutana_update_task_status(task_id: str, status: str) -> str:
            """Update a task's status.

            Args:
                task_id: Task UUID.
                status: New status (pending, in_progress, completed, cancelled).
            """
            return json.dumps(await client.update_task_status(task_id, status))

    # ------------------------------------------------------------------
    # chat
    # ------------------------------------------------------------------
    if "chat" in groups:

        @server.tool()
        async def kutana_send_chat_message(
            meeting_id: str,
            content: str,
            message_type: str = "text",
        ) -> str:
            """Post a message to a meeting's chat channel.

            Args:
                meeting_id: Meeting UUID.
                content: Message content (max 2000 chars).
                message_type: Type (text, question, action_item, decision).
            """
            return json.dumps(
                await client.request(
                    "POST",
                    f"/v1/meetings/{meeting_id}/chat",
                    json_body={"content": content, "message_type": message_type},
                )
            )

        @server.tool()
        async def kutana_get_chat_messages(
            meeting_id: str,
            limit: int = 50,
            message_type: str | None = None,
            since: str | None = None,
        ) -> str:
            """Retrieve chat history for a meeting.

            Args:
                meeting_id: Meeting UUID.
                limit: Max messages to return (default 50, max 200).
                message_type: Optional filter (text, question, action_item, decision).
                since: Optional ISO 8601 datetime — return messages after this time.
            """
            params: dict[str, str] = {"limit": str(limit)}
            if message_type:
                params["message_type"] = message_type
            if since:
                params["since"] = since
            return json.dumps(
                await client.request(
                    "GET",
                    f"/v1/meetings/{meeting_id}/chat",
                    params=params,
                )
            )

    # ------------------------------------------------------------------
    # transcript
    # ------------------------------------------------------------------
    if "transcript" in groups:

        @server.tool()
        async def kutana_get_transcript(
            meeting_id: str,
            last_n: int = 50,
        ) -> str:
            """Get transcript segments for a meeting.

            Args:
                meeting_id: Meeting UUID.
                last_n: Number of recent segments to return (default 50, max 500).
            """
            return json.dumps(
                await client.request(
                    "GET",
                    f"/v1/meetings/{meeting_id}/transcript",
                    params={"last_n": str(last_n)},
                )
            )

    # ------------------------------------------------------------------
    # turns
    # ------------------------------------------------------------------
    if "turns" in groups:

        @server.tool()
        async def kutana_raise_hand(
            meeting_id: str,
            priority: str = "normal",
            topic: str | None = None,
        ) -> str:
            """Raise hand to request a turn to speak.

            Args:
                meeting_id: Meeting UUID.
                priority: Priority (normal, urgent).
                topic: Optional topic description (max 200 chars).
            """
            body: dict[str, Any] = {"priority": priority}
            if topic:
                body["topic"] = topic
            return json.dumps(
                await client.request(
                    "POST",
                    f"/v1/meetings/{meeting_id}/turns/raise-hand",
                    json_body=body,
                )
            )

        @server.tool()
        async def kutana_get_queue_status(meeting_id: str) -> str:
            """Get the current speaker queue status.

            Args:
                meeting_id: Meeting UUID.

            Returns JSON with current_speaker, queue entries, your_position.
            """
            return json.dumps(
                await client.request(
                    "GET",
                    f"/v1/meetings/{meeting_id}/turns/queue",
                )
            )

        @server.tool()
        async def kutana_cancel_hand_raise(
            meeting_id: str,
            hand_raise_id: str | None = None,
        ) -> str:
            """Withdraw from the speaker queue (lower hand).

            Args:
                meeting_id: Meeting UUID.
                hand_raise_id: Optional specific hand raise to cancel.
            """
            params: dict[str, str] | None = None
            if hand_raise_id:
                params = {"hand_raise_id": hand_raise_id}
            return json.dumps(
                await client.request(
                    "DELETE",
                    f"/v1/meetings/{meeting_id}/turns/raise-hand",
                    params=params,
                )
            )

        @server.tool()
        async def kutana_get_speaking_status(meeting_id: str) -> str:
            """Check current speaking status in a meeting.

            Args:
                meeting_id: Meeting UUID.

            Returns JSON with is_speaking, is_in_queue, queue_position,
            current_speaker, meeting_phase.
            """
            return json.dumps(
                await client.request(
                    "GET",
                    f"/v1/meetings/{meeting_id}/turns/status",
                )
            )

    return server


@click.command("mcp")
@click.option(
    "--tools",
    default="all",
    help="Comma-separated tool groups to expose (meetings,tasks,chat,transcript,turns) or 'all'.",
)
@click.pass_context
def mcp(ctx: click.Context, tools: str) -> None:
    """Start the embedded MCP server (stdio transport).

    Exposes Kutana API tools via MCP stdio for AI agent integration.
    Auth uses the same config as the CLI (~/.kutana/config.json).

    Available tool groups: meetings, tasks, chat, transcript, turns.
    """
    groups = _resolve_groups(tools)
    config: dict[str, Any] = ctx.obj["config"]
    server = _build_server(groups, config)
    server.run(transport="stdio")
