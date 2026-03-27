"""Channel adapter ABC and registry for Convene Feeds.

Adapters abstract the difference between MCP servers and Claude Code channel
plugins so ``FeedRunner`` does not need to know which type a feed uses.
Adapters are bidirectional — the same instance is used whether the agent is
pulling context in or pushing data out.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from convene_core.models.feed import FeedDirection

if TYPE_CHECKING:
    from convene_core.database.models import FeedORM


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
    (push results) — there is no separate inbound/outbound adapter.
    The agent's system prompt determines which direction(s) to execute.
    """

    @abstractmethod
    def mcp_servers(self) -> list[MCPServerConfig]:
        """MCP servers to attach to the agent (empty for channel-only feeds).

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
    """Bidirectional adapter via an MCP server (Slack, Notion, GitHub, etc.).

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


class ClaudeCodeChannelAdapter(ChannelAdapter):
    """Bidirectional adapter via a Claude Code channel plugin.

    Used for Discord, Telegram, iMessage, and similar channel-based
    integrations where the Claude Code channel plugin provides the
    transport.

    Attributes:
        _channel_name: Channel identifier (e.g. "discord-general").
        _platform: Platform name for prompt generation.
    """

    def __init__(self, channel_name: str, platform: str) -> None:
        """Initialise the channel adapter.

        Args:
            channel_name: Channel identifier.
            platform: Platform name (discord, telegram, etc.).
        """
        self._channel_name = channel_name
        self._platform = platform

    def mcp_servers(self) -> list[MCPServerConfig]:
        """Return empty list — channels are injected via Claude Code config.

        Returns:
            Empty list.
        """
        return []

    def system_prompt_suffix(self, direction: FeedDirection) -> str:
        """Generate channel-specific prompt suffix.

        Args:
            direction: The feed direction.

        Returns:
            Prompt suffix string.
        """
        if direction == FeedDirection.INBOUND:
            return (
                f"Use the read_messages tool to fetch context from the "
                f"'{self._channel_name}' {self._platform} channel."
            )
        return (
            f"Use the send_message tool to post to the '{self._channel_name}' "
            f"{self._platform} channel."
        )


# ---------------------------------------------------------------------------
# Adapter registry
# ---------------------------------------------------------------------------

ADAPTER_REGISTRY: dict[str, type[ChannelAdapter]] = {
    "slack": MCPChannelAdapter,
    "notion": MCPChannelAdapter,
    "github": MCPChannelAdapter,
    "discord": ClaudeCodeChannelAdapter,
    "telegram": ClaudeCodeChannelAdapter,
    "imessage": ClaudeCodeChannelAdapter,
}


def build_adapter(feed: FeedORM, decrypted_token: str | None = None) -> ChannelAdapter:
    """Build the appropriate ChannelAdapter for a feed.

    Args:
        feed: The feed ORM row with platform and delivery config.
        decrypted_token: The decrypted MCP auth token (required for MCP feeds).

    Returns:
        An instantiated ChannelAdapter subclass.

    Raises:
        ValueError: If the platform is not in the registry.
        ValueError: If an MCP feed is missing required fields.
    """
    cls = ADAPTER_REGISTRY.get(feed.platform)
    if cls is None:
        msg = f"Unknown platform '{feed.platform}'. Supported: {list(ADAPTER_REGISTRY.keys())}"
        raise ValueError(msg)

    if issubclass(cls, MCPChannelAdapter):
        if not feed.mcp_server_url:
            msg = f"Feed '{feed.name}' (platform={feed.platform}) requires mcp_server_url"
            raise ValueError(msg)
        if not decrypted_token:
            msg = f"Feed '{feed.name}' (platform={feed.platform}) requires a decrypted auth token"
            raise ValueError(msg)
        return cls(feed.mcp_server_url, decrypted_token, feed.platform)

    if not feed.channel_name:
        msg = f"Feed '{feed.name}' (platform={feed.platform}) requires channel_name"
        raise ValueError(msg)
    return cls(feed.channel_name, feed.platform)
