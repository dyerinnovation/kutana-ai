"""Channel adapter ABC and registry for Convene Feeds.

Supports two transport modes:
- **HTTP MCP** (``MCPChannelAdapter``): connects to a remote MCP endpoint
  via Streamable HTTP JSON-RPC (Slack, Notion, GitHub).
- **Stdio MCP** (``ClaudeCodeChannelAdapter``): spawns an official Claude
  channel plugin as a subprocess and communicates over stdio (Discord,
  Telegram, iMessage).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from convene_core.models.feed import FeedDirection

if TYPE_CHECKING:
    from convene_core.database.models import FeedORM


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration for connecting to an external MCP server over HTTP.

    Attributes:
        url: The MCP server URL.
        token: Bearer token for authentication.
    """

    url: str
    token: str


@dataclass(frozen=True)
class StdioMCPServerConfig:
    """Configuration for spawning an MCP server as a stdio subprocess.

    Attributes:
        command: Executable to run (e.g. "bun").
        args: Arguments to pass (e.g. ["server.ts"]).
        env: Extra environment variables for the subprocess.
    """

    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)


class ChannelAdapter(ABC):
    """Configures a FeedAgent's channel connection.

    The same adapter handles both inbound (pull context) and outbound
    (push results) -- the agent's system prompt determines direction.
    """

    @abstractmethod
    def mcp_servers(self) -> list[MCPServerConfig | StdioMCPServerConfig]:
        """MCP servers to attach to the agent.

        Returns:
            List of MCP server configs (HTTP or stdio).
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
    """Bidirectional adapter via an HTTP MCP server (Slack, Notion, GitHub).

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

    def mcp_servers(self) -> list[MCPServerConfig | StdioMCPServerConfig]:
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
    """Adapter for official Claude channel plugins (Discord, Telegram, iMessage).

    Spawns the official plugin as a stdio MCP subprocess. The plugin
    provides its own tools (reply, fetch_messages, etc.) natively.

    Attributes:
        _platform: Platform name (discord, telegram, imessage).
        _channel_name: Channel or guild-channel name.
        _bot_token: Platform bot/API token passed via env to the subprocess.
    """

    # Map platform name → plugin directory under /app/plugins/
    _PLUGIN_DIR = "/app/plugins"

    def __init__(self, platform: str, channel_name: str, bot_token: str) -> None:
        """Initialise the Claude Code channel adapter.

        Args:
            platform: Platform name (discord, telegram, imessage).
            channel_name: Channel name for prompt context.
            bot_token: Bot token passed as env var to the subprocess.
        """
        self._platform = platform
        self._channel_name = channel_name
        self._bot_token = bot_token

    def mcp_servers(self) -> list[MCPServerConfig | StdioMCPServerConfig]:
        """Return a stdio MCP server config for the channel plugin.

        Returns:
            Single-element list with the stdio subprocess config.
        """
        # Token env var name follows the official plugin convention
        token_env_key = f"{self._platform.upper()}_BOT_TOKEN"
        return [
            StdioMCPServerConfig(
                command="bun",
                args=[f"{self._PLUGIN_DIR}/{self._platform}/server.ts"],
                env={token_env_key: self._bot_token},
            )
        ]

    def system_prompt_suffix(self, direction: FeedDirection) -> str:
        """Generate channel-specific prompt suffix.

        Args:
            direction: The feed direction.

        Returns:
            Prompt suffix string with channel tool instructions.
        """
        if direction == FeedDirection.INBOUND:
            return (
                f"Use the fetch_messages tool to pull context from the "
                f"'{self._channel_name}' {self._platform} channel."
            )
        if direction == FeedDirection.OUTBOUND:
            return (
                f"Use the reply tool to post to the "
                f"'{self._channel_name}' {self._platform} channel."
            )
        return (
            f"Use fetch_messages to pull context from and reply to post to "
            f"the '{self._channel_name}' {self._platform} channel."
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
        decrypted_token: The decrypted auth token (required for MCP feeds,
            used as bot token for channel feeds).

    Returns:
        An instantiated ChannelAdapter.

    Raises:
        ValueError: If the platform is not in the registry.
        ValueError: If required fields are missing for the adapter type.
    """
    cls = ADAPTER_REGISTRY.get(feed.platform)
    if cls is None:
        msg = f"Unknown platform '{feed.platform}'. Supported: {list(ADAPTER_REGISTRY.keys())}"
        raise ValueError(msg)

    if issubclass(cls, ClaudeCodeChannelAdapter):
        channel_name = feed.channel_name
        if not channel_name:
            msg = f"Feed '{feed.name}' (platform={feed.platform}) requires channel_name"
            raise ValueError(msg)
        if not decrypted_token:
            msg = f"Feed '{feed.name}' (platform={feed.platform}) requires a bot token"
            raise ValueError(msg)
        return ClaudeCodeChannelAdapter(feed.platform, channel_name, decrypted_token)

    # MCPChannelAdapter path
    server_url = feed.mcp_server_url
    if not server_url:
        msg = f"Feed '{feed.name}' (platform={feed.platform}) requires mcp_server_url"
        raise ValueError(msg)
    if not decrypted_token:
        msg = f"Feed '{feed.name}' (platform={feed.platform}) requires a decrypted auth token"
        raise ValueError(msg)

    return MCPChannelAdapter(server_url, decrypted_token, feed.platform)
