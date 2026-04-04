"""Managed agent spawner and runner.

Spawns Claude SDK agents from agent templates when users activate them
on a meeting.  Each agent connects to the Kutana MCP server, joins the
meeting, and runs a continuous participation loop until the meeting ends
or the session is deactivated.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any
from uuid import UUID

import anthropic
import httpx

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MAX_CONCURRENT_AGENTS = 5
_POLL_INTERVAL_S = 5.0
_AGENT_TURN_LIMIT = 200  # Max agentic turns per session
_MCP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_PARTICIPATION_INTERVAL_S = 30.0  # How often the agent checks in


# ---------------------------------------------------------------------------
# MCP helpers (reuse pattern from feed_agent.py)
# ---------------------------------------------------------------------------

_jsonrpc_id = 0


def _next_id() -> int:
    global _jsonrpc_id
    _jsonrpc_id += 1
    return _jsonrpc_id


async def _mcp_list_tools(
    client: httpx.AsyncClient,
    url: str,
    token: str,
) -> list[dict[str, Any]]:
    """Discover tools from an MCP server via JSON-RPC."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"jsonrpc": "2.0", "id": _next_id(), "method": "tools/list", "params": {}}
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    result = resp.json().get("result", {})
    return result.get("tools", [])


async def _mcp_call_tool(
    client: httpx.AsyncClient,
    url: str,
    token: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    """Call an MCP tool via JSON-RPC."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": _next_id(),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    result = resp.json().get("result", {})
    return result.get("content", [])


def _mcp_tool_to_anthropic(mcp_tool: dict[str, Any]) -> dict[str, Any]:
    """Convert an MCP tool definition to Anthropic tool format."""
    return {
        "name": mcp_tool["name"],
        "description": mcp_tool.get("description", ""),
        "input_schema": mcp_tool.get("inputSchema", {}),
    }


def _extract_text(content: list[dict[str, Any]]) -> str:
    """Extract text from MCP content blocks."""
    parts = []
    for block in content:
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(parts) if parts else json.dumps(content)


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------


def _build_system_prompt(
    template_prompt: str,
    agent_name: str,
    meeting_title: str | None = None,
) -> str:
    """Build the full system prompt for a managed agent.

    Wraps the template's prompt with Kutana-specific instructions for
    meeting participation.

    Args:
        template_prompt: The raw system prompt from the agent template.
        agent_name: Display name of the agent.
        meeting_title: Optional meeting title for context.
    """
    meeting_context = f"Meeting: {meeting_title}\n" if meeting_title else ""

    return f"""{template_prompt}

---
MEETING PARTICIPATION INSTRUCTIONS:

{meeting_context}You are "{agent_name}", a Kutana managed agent participating in a live meeting.

You have access to Kutana MCP tools. You are ALREADY joined to the meeting.

Your participation loop:
1. Check the transcript for new content using get_entity_history or request_context
2. Perform your role (take notes, extract tasks, facilitate, summarize)
3. Share insights with participants via the reply tool (chat messages)
4. When you have gathered enough context, use get_meeting_recap to compile findings
5. Continue monitoring until told to stop

Guidelines:
- Be concise in chat messages — short, actionable updates
- Don't repeat information participants already know
- Focus on your specific role (notetaking, technical capture, facilitation, or summarization)
- Use reply to share findings in chat, not speak (save voice for important moments)
- When the meeting ends or you receive a stop signal, provide a final summary via reply
"""


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


async def run_managed_agent(
    session_id: UUID,
    template_name: str,
    system_prompt: str,
    meeting_id: UUID,
    meeting_title: str | None,
    kutana_mcp_url: str,
    kutana_mcp_token: str,
    anthropic_api_key: str | None = None,
) -> dict[str, Any]:
    """Run a managed agent session.

    Connects to the Kutana MCP server, joins the meeting, and runs a
    continuous participation loop.

    Args:
        session_id: The hosted agent session ID.
        template_name: Name of the agent template.
        system_prompt: Raw system prompt from the template.
        meeting_id: Meeting to join.
        meeting_title: Meeting title for context.
        kutana_mcp_url: Kutana MCP server URL.
        kutana_mcp_token: Bearer token for MCP.
        anthropic_api_key: Optional user-provided API key.

    Returns:
        Dict with execution results.
    """
    full_prompt = _build_system_prompt(
        template_prompt=system_prompt,
        agent_name=template_name,
        meeting_title=meeting_title,
    )

    # Use user's API key if provided, otherwise use the service default
    client_kwargs: dict[str, Any] = {}
    if anthropic_api_key:
        client_kwargs["api_key"] = anthropic_api_key

    client = anthropic.AsyncAnthropic(**client_kwargs)

    logger.info(
        "Managed agent starting: name=%s session=%s meeting=%s",
        template_name,
        session_id,
        meeting_id,
    )

    async with httpx.AsyncClient(timeout=_MCP_TIMEOUT) as http:
        # Discover MCP tools
        try:
            mcp_tools = await _mcp_list_tools(http, kutana_mcp_url, kutana_mcp_token)
        except Exception:
            logger.exception("Failed to discover MCP tools from %s", kutana_mcp_url)
            raise RuntimeError(f"MCP server unreachable: {kutana_mcp_url}") from None

        tools = [_mcp_tool_to_anthropic(t) for t in mcp_tools]
        logger.info("Discovered %d MCP tools for managed agent %s", len(tools), template_name)

        # Initial message: instruct the agent to join the meeting
        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": (
                    f"Join meeting {meeting_id} and begin your role as {template_name}. "
                    f"Use join_meeting with meeting_id=\"{meeting_id}\". "
                    "Once joined, start monitoring the transcript and performing your duties. "
                    "After each check-in, wait for the next prompt to continue monitoring."
                ),
            },
        ]

        final_text = ""
        turn = 0

        # Phase 1: Join and initial participation (agentic loop)
        for turn in range(_AGENT_TURN_LIMIT):
            try:
                response = await client.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=4096,
                    system=full_prompt,
                    tools=tools,  # type: ignore[arg-type]
                    messages=messages,
                )
            except Exception:
                logger.exception(
                    "Managed agent Claude API error: session=%s turn=%d",
                    session_id,
                    turn,
                )
                break

            # Build assistant message
            assistant_content: list[dict[str, Any]] = []
            tool_use_blocks: list[dict[str, Any]] = []

            for block in response.content:
                if block.type == "text":
                    final_text = block.text
                    assistant_content.append({"type": "text", "text": block.text})
                elif block.type == "tool_use":
                    tool_block = {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                    assistant_content.append(tool_block)
                    tool_use_blocks.append(tool_block)

            messages.append({"role": "assistant", "content": assistant_content})

            # If model finished and no tool calls, pause then prompt to continue
            if response.stop_reason == "end_turn" and not tool_use_blocks:
                # Wait before next check-in
                await asyncio.sleep(_PARTICIPATION_INTERVAL_S)
                messages.append({
                    "role": "user",
                    "content": (
                        "Continue monitoring the meeting. Check for new transcript segments, "
                        "extract any new insights, and share updates with participants if needed. "
                        "If the meeting appears to have ended (no new transcript), "
                        "provide a final summary and stop."
                    ),
                })
                continue

            if not tool_use_blocks:
                break

            # Handle tool calls
            tool_results: list[dict[str, Any]] = []
            for tool_block in tool_use_blocks:
                tool_name = tool_block["name"]
                tool_input = tool_block["input"]
                tool_id = tool_block["id"]

                try:
                    result_content = await _mcp_call_tool(
                        http, kutana_mcp_url, kutana_mcp_token,
                        tool_name, tool_input,
                    )
                    result_text = _extract_text(result_content)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": result_text,
                    })
                except Exception:
                    logger.exception("MCP tool call '%s' failed", tool_name)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": f"Error calling tool '{tool_name}': execution failed",
                        "is_error": True,
                    })

            messages.append({"role": "user", "content": tool_results})

    logger.info(
        "Managed agent completed: name=%s session=%s turns=%d",
        template_name,
        session_id,
        turn + 1,
    )

    return {
        "status": "completed",
        "final_text": final_text,
        "turns": turn + 1,
    }


# ---------------------------------------------------------------------------
# Session consumer — polls DB for active sessions and spawns agents
# ---------------------------------------------------------------------------


class ManagedAgentRunner:
    """Polls for active hosted agent sessions and runs them.

    Similar to FeedRunner but for managed agents. Polls the database
    for sessions with status="pending", spawns agent tasks, and
    manages their lifecycle.

    Attributes:
        _session_factory: SQLAlchemy async session factory.
        _kutana_mcp_url: URL of the Kutana MCP server.
        _kutana_mcp_token: Bearer token for Kutana MCP.
        _active_agents: Currently running agent tasks.
        _semaphore: Limits concurrent agents.
        _stop: Flag to signal shutdown.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        kutana_mcp_url: str = "http://localhost:3001/mcp",
        kutana_mcp_token: str = "",
    ) -> None:
        """Initialise the managed agent runner.

        Args:
            session_factory: SQLAlchemy async session factory.
            kutana_mcp_url: URL of the Kutana MCP server.
            kutana_mcp_token: Bearer token for Kutana MCP.
        """
        self._session_factory = session_factory
        self._kutana_mcp_url = kutana_mcp_url
        self._kutana_mcp_token = kutana_mcp_token
        self._active_agents: dict[UUID, asyncio.Task[None]] = {}
        self._semaphore = asyncio.Semaphore(_MAX_CONCURRENT_AGENTS)
        self._stop = False

    async def start(self) -> None:
        """Poll for pending sessions and spawn agents."""
        logger.info("ManagedAgentRunner started (max_concurrent=%d)", _MAX_CONCURRENT_AGENTS)

        while not self._stop:
            try:
                await self._poll_and_spawn()
                await self._check_completed()
            except Exception:
                logger.exception("Error in ManagedAgentRunner poll loop")
            await asyncio.sleep(_POLL_INTERVAL_S)

    async def stop(self) -> None:
        """Stop the runner and cancel all active agents."""
        self._stop = True
        for session_id, task in list(self._active_agents.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            logger.info("Cancelled managed agent session %s", session_id)
        self._active_agents.clear()
        logger.info("ManagedAgentRunner stopped")

    async def _poll_and_spawn(self) -> None:
        """Check for pending sessions and spawn agent tasks."""
        from kutana_core.database.models import HostedAgentSessionORM, AgentTemplateORM, MeetingORM
        from sqlalchemy import select

        async with self._session_factory() as db:
            # Find sessions that are "active" but not yet running
            result = await db.execute(
                select(HostedAgentSessionORM)
                .where(HostedAgentSessionORM.status == "active")
            )
            sessions = result.scalars().all()

            for session in sessions:
                if session.id in self._active_agents:
                    continue  # Already running

                # Load template and meeting
                template_result = await db.execute(
                    select(AgentTemplateORM).where(AgentTemplateORM.id == session.template_id)
                )
                template = template_result.scalar_one_or_none()
                if not template:
                    logger.warning("Template %s not found for session %s", session.template_id, session.id)
                    session.status = "failed"
                    await db.commit()
                    continue

                meeting_result = await db.execute(
                    select(MeetingORM).where(MeetingORM.id == session.meeting_id)
                )
                meeting = meeting_result.scalar_one_or_none()
                meeting_title = meeting.title if meeting else None

                # Spawn agent task
                task = asyncio.create_task(
                    self._run_session(
                        session_id=session.id,
                        template_name=template.name,
                        system_prompt=template.system_prompt,
                        meeting_id=session.meeting_id,
                        meeting_title=meeting_title,
                        anthropic_api_key=session.anthropic_api_key_encrypted,
                    ),
                    name=f"managed-agent-{session.id}",
                )
                self._active_agents[session.id] = task
                logger.info(
                    "Spawned managed agent: name=%s session=%s meeting=%s",
                    template.name,
                    session.id,
                    session.meeting_id,
                )

    async def _run_session(
        self,
        session_id: UUID,
        template_name: str,
        system_prompt: str,
        meeting_id: UUID,
        meeting_title: str | None,
        anthropic_api_key: str | None,
    ) -> None:
        """Run a single managed agent session with lifecycle management.

        Args:
            session_id: The hosted agent session ID.
            template_name: Agent template name.
            system_prompt: Template system prompt.
            meeting_id: Meeting to join.
            meeting_title: Meeting title.
            anthropic_api_key: Optional user API key.
        """
        async with self._semaphore:
            try:
                # Update status to running
                await self._update_status(session_id, "running")

                result = await run_managed_agent(
                    session_id=session_id,
                    template_name=template_name,
                    system_prompt=system_prompt,
                    meeting_id=meeting_id,
                    meeting_title=meeting_title,
                    kutana_mcp_url=self._kutana_mcp_url,
                    kutana_mcp_token=self._kutana_mcp_token,
                    anthropic_api_key=anthropic_api_key,
                )

                logger.info(
                    "Managed agent session completed: session=%s turns=%d",
                    session_id,
                    result.get("turns", 0),
                )
                await self._update_status(session_id, "completed")

            except asyncio.CancelledError:
                logger.info("Managed agent session cancelled: %s", session_id)
                await self._update_status(session_id, "stopped")
                raise
            except Exception:
                logger.exception("Managed agent session failed: %s", session_id)
                await self._update_status(session_id, "failed")

    async def _update_status(self, session_id: UUID, status: str) -> None:
        """Update the session status in the database.

        Args:
            session_id: The session to update.
            status: New status string.
        """
        from datetime import datetime, timezone

        from kutana_core.database.models import HostedAgentSessionORM
        from sqlalchemy import select

        try:
            async with self._session_factory() as db:
                result = await db.execute(
                    select(HostedAgentSessionORM)
                    .where(HostedAgentSessionORM.id == session_id)
                )
                session = result.scalar_one_or_none()
                if session:
                    session.status = status
                    if status in ("completed", "stopped", "failed"):
                        session.ended_at = datetime.now(tz=timezone.utc)
                    await db.commit()
        except Exception:
            logger.warning("Failed to update session %s status to %s", session_id, status)

    async def _check_completed(self) -> None:
        """Clean up completed agent tasks."""
        completed = [
            sid for sid, task in self._active_agents.items()
            if task.done()
        ]
        for sid in completed:
            task = self._active_agents.pop(sid)
            if task.exception():
                logger.warning(
                    "Managed agent task %s ended with exception: %s",
                    sid,
                    task.exception(),
                )
