"""Feed agent builder and execution for Convene Feeds.

The FeedAgent is a short-lived Claude Haiku agent instantiated per-run.
It receives access to the Convene MCP server (to read meeting data or
inject context) and the delivery/source MCP or channel connection.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from uuid import UUID

    from convene_core.database.models import FeedORM
    from convene_core.feeds.adapters import ChannelAdapter

logger = logging.getLogger(__name__)

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

    delivery_mechanism = "MCP" if feed.delivery_type == "mcp" else "channel"

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
    or an equivalent agent runner. Phase 1 returns the config; the actual
    Claude SDK integration happens when the Anthropic agent SDK is wired in.

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


async def run_feed(
    feed: FeedORM,
    meeting_id: UUID,
    direction: str,
    adapter: ChannelAdapter,
    convene_mcp_url: str,
    convene_mcp_token: str,
) -> dict[str, Any]:
    """Execute a feed agent run.

    Phase 1 builds the agent config and logs it. Full Claude SDK agent
    execution will be wired in Phase 2 when the Anthropic agent SDK
    client is integrated.

    Args:
        feed: The feed ORM row.
        meeting_id: Meeting to process.
        direction: Run direction.
        adapter: Channel adapter for the feed's platform.
        convene_mcp_url: URL of the Convene MCP server.
        convene_mcp_token: Bearer token for the Convene MCP server.

    Returns:
        A dict with execution results.
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
        "Feed agent configured: feed=%s meeting=%s direction=%s platform=%s",
        feed.name,
        meeting_id,
        direction,
        feed.platform,
    )

    # TODO(Phase 2): Replace with actual Claude SDK agent execution
    # agent = Agent(
    #     model=config["model"],
    #     system_prompt=config["system_prompt"],
    #     mcp_servers=config["mcp_servers"],
    # )
    # result = await agent.run()

    return {
        "status": "configured",
        "config": config,
        "message": "Agent config built. Full execution pending Claude SDK integration.",
    }
