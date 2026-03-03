"""MCP Server configuration settings."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class MCPServerSettings(BaseSettings):
    """Settings for the Convene MCP server.

    Loaded from environment variables. The MCP_API_KEY and
    MCP_AGENT_CONFIG_ID are configured by the user when they
    set up the MCP server in their Claude Desktop config.

    Attributes:
        mcp_api_key: API key for authenticating with the Convene API.
        mcp_agent_config_id: UUID of the agent configuration.
        api_base_url: Base URL of the Convene API server.
        gateway_ws_url: WebSocket URL of the agent gateway.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mcp_api_key: str = ""
    mcp_agent_config_id: str = ""
    api_base_url: str = "http://localhost:8000"
    gateway_ws_url: str = "ws://localhost:8003"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 3001
