"""Convene Feeds — channel adapters and registry."""

from __future__ import annotations

from convene_core.feeds.adapters import (
    ADAPTER_REGISTRY,
    ChannelAdapter,
    ClaudeCodeChannelAdapter,
    MCPChannelAdapter,
    MCPServerConfig,
    StdioMCPServerConfig,
    build_adapter,
)

__all__ = [
    "ADAPTER_REGISTRY",
    "ChannelAdapter",
    "ClaudeCodeChannelAdapter",
    "MCPChannelAdapter",
    "MCPServerConfig",
    "StdioMCPServerConfig",
    "build_adapter",
]
