"""Feed agent builder and execution for Convene Feeds.

The FeedAgent is a short-lived Claude Haiku agent instantiated per-run.
It receives access to the Convene MCP server (to read meeting data or
inject context) and the delivery/source MCP or channel connection.

Uses the Anthropic API with a tool-use loop to drive MCP-backed tools.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

import anthropic
import httpx

if TYPE_CHECKING:
    from uuid import UUID

    from convene_core.database.models import FeedORM
    from convene_core.feeds.adapters import ChannelAdapter

logger = logging.getLogger(__name__)

_MCP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)
_RUN_TIMEOUT_SECONDS = 60
_MAX_AGENT_TURNS = 10
_JSONRPC_ID_COUNTER = 0

# ---------------------------------------------------------------------------
# System prompt templates
# ---------------------------------------------------------------------------

_OUTBOUND_PROMPT = """You are a Convene delivery agent. Your job is to push meeting data to {platform}.

Meeting ID: {meeting_id}
Deliver: {data_types}

Steps:
1. Use convene_get_summary / convene_get_tasks / convene_get_transcript as needed.
2. Format the data appropriately for {platform}.
3. Deliver it using the {delivery_mechanism} tools available to you.
4. Confirm delivery and stop.

Do not include raw transcript unless explicitly requested.
Be concise — this is a notification, not a report.

{adapter_suffix}"""

_INBOUND_PROMPT = """You are a Convene context agent. Your job is to pull relevant context from {platform} \
and inject it into the meeting before it starts.

Meeting ID: {meeting_id}
Context to pull: {context_types}

Steps:
1. Use the {platform} tools to fetch the relevant context (linked thread, issue, doc, etc.).
2. Summarize or structure the context as appropriate.
3. Use convene_set_context(meeting_id, context) to inject it into the meeting.
4. Confirm injection and stop.

Be concise — participants will see this as a context sidebar, not a full document.

{adapter_suffix}"""


def _next_jsonrpc_id() -> int:
    """Generate a monotonically increasing JSON-RPC request ID."""
    global _JSONRPC_ID_COUNTER
    _JSONRPC_ID_COUNTER += 1
    return _JSONRPC_ID_COUNTER


def _build_system_prompt(
    feed: FeedORM,
    meeting_id: UUID,
    direction: str,
    adapter: ChannelAdapter,
) -> str:
    """Build the system prompt for a feed agent run.

    Args:
        feed: The feed ORM row.
        meeting_id: Meeting being processed.
        direction: Run direction ("inbound" or "outbound").
        adapter: The channel adapter for this feed.

    Returns:
        The complete system prompt string.
    """
    from convene_core.models.feed import FeedDirection

    feed_direction = FeedDirection(direction)
    adapter_suffix = adapter.system_prompt_suffix(feed_direction)

    delivery_mechanism = "MCP"

    if direction == "inbound":
        return _INBOUND_PROMPT.format(
            platform=feed.platform,
            meeting_id=str(meeting_id),
            context_types=", ".join(feed.context_types) if feed.context_types else "all available",
            adapter_suffix=adapter_suffix,
        )

    return _OUTBOUND_PROMPT.format(
        platform=feed.platform,
        meeting_id=str(meeting_id),
        data_types=", ".join(feed.data_types) if feed.data_types else "summary",
        delivery_mechanism=delivery_mechanism,
        adapter_suffix=adapter_suffix,
    )


def build_feed_agent(
    feed: FeedORM,
    meeting_id: UUID,
    direction: str,
    adapter: ChannelAdapter,
    convene_mcp_url: str,
    convene_mcp_token: str,
) -> dict[str, Any]:
    """Build the configuration for a feed agent run.

    Returns a configuration dict that can be passed to the Claude SDK
    or an equivalent agent runner.

    Args:
        feed: The feed ORM row.
        meeting_id: Meeting to process.
        direction: Run direction.
        adapter: Channel adapter for the feed's platform.
        convene_mcp_url: URL of the Convene MCP server.
        convene_mcp_token: Bearer token for the Convene MCP server.

    Returns:
        A dict with agent configuration including system_prompt,
        mcp_servers, model, and metadata.
    """
    system_prompt = _build_system_prompt(feed, meeting_id, direction, adapter)

    # Collect MCP servers: Convene MCP + external platform MCP (if any)
    mcp_servers = [
        {"url": convene_mcp_url, "token": convene_mcp_token},
    ]
    for server_config in adapter.mcp_servers():
        mcp_servers.append({"url": server_config.url, "token": server_config.token})

    return {
        "model": "claude-haiku-4-20250414",
        "system_prompt": system_prompt,
        "mcp_servers": mcp_servers,
        "max_tokens": 4096,
        "metadata": {
            "feed_id": str(feed.id),
            "feed_name": feed.name,
            "meeting_id": str(meeting_id),
            "direction": direction,
            "platform": feed.platform,
        },
    }


# ---------------------------------------------------------------------------
# MCP tool discovery and invocation via Streamable HTTP
# ---------------------------------------------------------------------------


async def _mcp_list_tools(
    client: httpx.AsyncClient,
    url: str,
    token: str,
) -> list[dict[str, Any]]:
    """List tools from an MCP server via JSON-RPC.

    Args:
        client: httpx async client.
        url: MCP server URL.
        token: Bearer token for auth.

    Returns:
        List of MCP tool definitions.

    Raises:
        RuntimeError: If the MCP server returns an error or is unreachable.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": _next_jsonrpc_id(),
        "method": "tools/list",
        "params": {},
    }
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        msg = f"MCP tools/list error from {url}: {body['error']}"
        raise RuntimeError(msg)
    return body.get("result", {}).get("tools", [])


async def _mcp_call_tool(
    client: httpx.AsyncClient,
    url: str,
    token: str,
    tool_name: str,
    arguments: dict[str, Any],
) -> Any:
    """Call a tool on an MCP server via JSON-RPC.

    Args:
        client: httpx async client.
        url: MCP server URL.
        token: Bearer token for auth.
        tool_name: Name of the tool to call.
        arguments: Tool arguments.

    Returns:
        The tool result content.

    Raises:
        RuntimeError: If the MCP server returns an error.
    """
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {
        "jsonrpc": "2.0",
        "id": _next_jsonrpc_id(),
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    resp = await client.post(url, json=payload, headers=headers)
    resp.raise_for_status()
    body = resp.json()
    if "error" in body:
        msg = f"MCP tools/call error for '{tool_name}': {body['error']}"
        raise RuntimeError(msg)
    return body.get("result", {}).get("content", [])


def _mcp_tool_to_anthropic(
    mcp_tool: dict[str, Any],
) -> dict[str, Any]:
    """Convert an MCP tool definition to Anthropic API tool format.

    Args:
        mcp_tool: MCP tool definition with name, description, inputSchema.

    Returns:
        Anthropic-compatible tool definition.
    """
    return {
        "name": mcp_tool["name"],
        "description": mcp_tool.get("description", ""),
        "input_schema": mcp_tool.get("inputSchema", {"type": "object", "properties": {}}),
    }


def _extract_text_from_mcp_content(content: Any) -> str:
    """Extract text from MCP tool result content.

    Args:
        content: MCP content (list of content blocks or raw value).

    Returns:
        Stringified result.
    """
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
            else:
                parts.append(str(block))
        return "\n".join(parts) if parts else "No content returned."
    return str(content) if content else "No content returned."


# ---------------------------------------------------------------------------
# Agent execution loop
# ---------------------------------------------------------------------------


async def run_feed(
    feed: FeedORM,
    meeting_id: UUID,
    direction: str,
    adapter: ChannelAdapter,
    convene_mcp_url: str,
    convene_mcp_token: str,
) -> dict[str, Any]:
    """Execute a feed agent run using Claude Haiku with MCP tool-use loop.

    Connects to each MCP server, discovers tools, then runs an agentic
    loop with Claude until the model signals end_turn or we hit the turn
    limit.

    Args:
        feed: The feed ORM row.
        meeting_id: Meeting to process.
        direction: Run direction.
        adapter: Channel adapter for the feed's platform.
        convene_mcp_url: URL of the Convene MCP server.
        convene_mcp_token: Bearer token for the Convene MCP server.

    Returns:
        A dict with execution results including the final text response.

    Raises:
        RuntimeError: If MCP servers are unreachable or agent execution fails.
        TimeoutError: If the entire run exceeds the timeout.
    """
    config = build_feed_agent(
        feed=feed,
        meeting_id=meeting_id,
        direction=direction,
        adapter=adapter,
        convene_mcp_url=convene_mcp_url,
        convene_mcp_token=convene_mcp_token,
    )

    logger.info(
        "Feed agent starting: feed=%s meeting=%s direction=%s platform=%s",
        feed.name,
        meeting_id,
        direction,
        feed.platform,
    )

    return await asyncio.wait_for(
        _run_agent_loop(config),
        timeout=_RUN_TIMEOUT_SECONDS,
    )


async def _run_agent_loop(config: dict[str, Any]) -> dict[str, Any]:
    """Run the inner agentic tool-use loop.

    Args:
        config: Agent configuration from build_feed_agent().

    Returns:
        A dict with status and the agent's final text.
    """
    client = anthropic.AsyncAnthropic()

    # --- Discover tools from all MCP servers ---
    all_tools: list[dict[str, Any]] = []
    # Map tool_name -> (mcp_url, mcp_token) for routing calls
    tool_routing: dict[str, tuple[str, str]] = {}

    async with httpx.AsyncClient(timeout=_MCP_TIMEOUT) as http:
        for server in config["mcp_servers"]:
            url = server["url"]
            token = server["token"]
            try:
                mcp_tools = await _mcp_list_tools(http, url, token)
            except Exception:
                logger.exception("Failed to list tools from MCP server %s", url)
                msg = f"MCP server unreachable: {url}"
                raise RuntimeError(msg) from None

            for mcp_tool in mcp_tools:
                anthropic_tool = _mcp_tool_to_anthropic(mcp_tool)
                all_tools.append(anthropic_tool)
                tool_routing[mcp_tool["name"]] = (url, token)

            logger.info(
                "Discovered %d tools from %s",
                len(mcp_tools),
                url,
            )

    if not all_tools:
        logger.warning("No tools discovered from any MCP server")

    # --- Agentic loop ---
    messages: list[dict[str, Any]] = []
    final_text = ""

    async with httpx.AsyncClient(timeout=_MCP_TIMEOUT) as http:
        for turn in range(_MAX_AGENT_TURNS):
            response = await client.messages.create(
                model=config["model"],
                max_tokens=config["max_tokens"],
                system=config["system_prompt"],
                tools=all_tools,  # type: ignore[arg-type]
                messages=messages,
            )

            logger.debug(
                "Agent turn %d: stop_reason=%s content_blocks=%d",
                turn + 1,
                response.stop_reason,
                len(response.content),
            )

            # Build assistant message from response content
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

            # If the model is done, exit
            if response.stop_reason == "end_turn" or not tool_use_blocks:
                break

            # Handle tool calls
            tool_results: list[dict[str, Any]] = []
            for tool_block in tool_use_blocks:
                tool_name = tool_block["name"]
                tool_input = tool_block["input"]
                tool_id = tool_block["id"]

                routing = tool_routing.get(tool_name)
                if routing is None:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"Error: unknown tool '{tool_name}'",
                            "is_error": True,
                        }
                    )
                    continue

                mcp_url, mcp_token = routing
                try:
                    result_content = await _mcp_call_tool(
                        http, mcp_url, mcp_token, tool_name, tool_input
                    )
                    result_text = _extract_text_from_mcp_content(result_content)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": result_text,
                        }
                    )
                except Exception:
                    logger.exception("Tool call '%s' failed", tool_name)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_id,
                            "content": f"Error calling tool '{tool_name}': tool execution failed",
                            "is_error": True,
                        }
                    )

            messages.append({"role": "user", "content": tool_results})

    logger.info(
        "Feed agent completed: turns=%d final_text_len=%d",
        min(turn + 1, _MAX_AGENT_TURNS),
        len(final_text),
    )

    return {
        "status": "completed",
        "final_text": final_text,
        "turns": turn + 1,
    }
