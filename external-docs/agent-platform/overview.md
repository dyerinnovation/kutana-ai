# Convene AI Agent Platform

## Overview

Convene AI supports three tiers of agent access, all connecting through the same gateway + MCP server backend.

## Three-Tier Agent Architecture

### Tier 1: Arbitrary Agents
Any agent that can speak MCP Streamable HTTP or connect via raw gateway WebSocket. No Convene-specific SDK required.

**Connection:** Direct WebSocket with JWT, or MCP with Bearer token.

### Tier 2: Platform-Specific Integrations
Pre-built integrations for specific agent platforms:
- **Claude Agent SDK** — `MCPServerConfig` with Bearer token auth — see [Claude Agent SDK](connecting/claude-agent-sdk.md)
- **OpenClaw** — Plugin + skill (`@convene/openclaw-plugin`) — see [OpenClaw](../openclaw/plugin-guide.md)
- **Claude Code** — Skill (`.claude/skills/convene-meeting/SKILL.md`) — see [Claude Code Channel](connecting/claude-code-channel.md)
- **Convene CLI** — Python CLI wrapping REST API + gateway WebSocket — see [CLI](connecting/cli.md)

### Tier 3: Prebuilt Agents (Hosted by Convene)
Agent templates in the web UI. User selects a template, assigns it to a meeting, and Convene runs it server-side.

- **Free tier**: User provides their own Anthropic API key
- **Premium tier**: Convene provides the API key (billed), free trial available
- **Activation flow**: Select template → assign to meeting → Convene spawns agent → joins via MCP

## Prebuilt Agent Templates

| Template | Description | Category |
|----------|-------------|----------|
| Meeting Summarizer | Produces minutes every 5 min | summarization |
| Action Item Tracker | Focuses on tasks and assignments | productivity |
| Decision Logger | Captures decisions with context | documentation |
| Code Discussion Tracker | Extracts code-related topics | engineering |

## Authentication

All agents authenticate via API key + OAuth 2.1 token exchange. See [MCP Auth](connecting/mcp-auth.md) for the full flow.

## See Also

- [MCP Auth](connecting/mcp-auth.md) — OAuth 2.1 authorization flow
- [Claude Agent SDK](connecting/claude-agent-sdk.md) — Build autonomous agents
- [Claude Code Channel](connecting/claude-code-channel.md) — Use Claude Code as a meeting participant
- [OpenClaw](../openclaw/plugin-guide.md) — Connect via OpenClaw channels
- [CLI](connecting/cli.md) — Terminal-based access
