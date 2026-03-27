"""Channel adapter ABC and registry for Convene Feeds.

All platforms use HTTP MCP servers. The ``MCPChannelAdapter`` connects to
each platform's MCP endpoint and exposes tools to the feed agent.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from convene_core.models.feed import FeedDirection

if TYPE_CHECKING:
    from convene_core.database.models import FeedORM

# Default in-cluster Discord MCP URL
DISCORD_MCP_URL = os.environ.get("DISCORD_MCP_URL", "http://discord-mcp.convene.svc:3002/mcp")


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration for connecting to an external MCP server.

    Attributes:
        url: The MCP server URL.
        token: Bearer token for authentication.
    """

    url: str
    token: str


class ChannelAdapter(ABC):
    """Configures a FeedAgent's channel connection.

    The same adapter handles both inbound (pull context) and outbound
    (push results) -- the agent's system prompt determines direction.
    """

    @abstractmethod
    def mcp_servers(self) -> list[MCPServerConfig]:
        """MCP servers to attach to the agent.

        Returns:
            List of MCP server configs.
        """
        ...

    @abstractmethod
    def system_prompt_suffix(self, direction: FeedDirection) -> str:
        """Platform-specific instructions appended to the base system prompt.

        Args:
            direction: The feed direction for this run.

        Returns:
            A string to append to the system prompt.
        """
        ...


class MCPChannelAdapter(ChannelAdapter):
    """Bidirectional adapter via an MCP server (Slack, Notion, GitHub, Discord, etc.).

    Attributes:
        _server_url: URL of the external MCP server.
        _auth_token: Decrypted auth token.
        _platform: Platform name for prompt generation.
    """

    def __init__(self, server_url: str, auth_token: str, platform: str) -> None:
        """Initialise the MCP channel adapter.

        Args:
            server_url: URL of the external MCP server.
            auth_token: Decrypted bearer token.
            platform: Platform name (slack, notion, etc.).
        """
        self._server_url = server_url
        self._auth_token = auth_token
        self._platform = platform

    def mcp_servers(self) -> list[MCPServerConfig]:
        """Return the external MCP server config.

        Returns:
            Single-element list with the configured MCP server.
        """
        return [MCPServerConfig(url=self._server_url, token=self._auth_token)]

    def system_prompt_suffix(self, direction: FeedDirection) -> str:
        """Generate platform-specific prompt suffix.

        Args:
            direction: The feed direction.

        Returns:
            Prompt suffix string.
        """
        if direction == FeedDirection.INBOUND:
            return f"Use the {self._platform} MCP tools to fetch context and inject it."
        if direction == FeedDirection.OUTBOUND:
            return f"Use the {self._platform} MCP tools to deliver the content."
        return (
            f"Use the {self._platform} MCP tools — pull context at meeting start "
            f"and deliver results when the meeting ends."
        )


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

ADAPTER_REGISTRY: dict[str, type[ChannelAdapter]] = {
    "slack": MCPChannelAdapter,
    "notion": MCPChannelAdapter,
    "github": MCPChannelAdapter,
    "discord": MCPChannelAdapter,
}


def build_adapter(feed: FeedORM, decrypted_token: str | None = None) -> ChannelAdapter:
    """Build the appropriate ChannelAdapter for a feed.

    Args:
        feed: The feed ORM row with platform and delivery config.
        decrypted_token: The decrypted auth token (required for all feeds).

    Returns:
        An instantiated MCPChannelAdapter.

    Raises:
        ValueError: If the platform is not in the registry.
        ValueError: If required fields are missing.
    """
    cls = ADAPTER_REGISTRY.get(feed.platform)
    if cls is None:
        msg = f"Unknown platform '{feed.platform}'. Supported: {list(ADAPTER_REGISTRY.keys())}"
        raise ValueError(msg)

    # For Discord, fall back to the in-cluster MCP URL if not explicitly set
    server_url = feed.mcp_server_url
    if feed.platform == "discord" and not server_url:
        server_url = DISCORD_MCP_URL

    if not server_url:
        msg = f"Feed '{feed.name}' (platform={feed.platform}) requires mcp_server_url"
        raise ValueError(msg)
    if not decrypted_token:
        msg = f"Feed '{feed.name}' (platform={feed.platform}) requires a decrypted auth token"
        raise ValueError(msg)

    return MCPChannelAdapter(server_url, decrypted_token, feed.platform)
