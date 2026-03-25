# Convene AI Agent Platform

## Overview

Convene AI supports three tiers of agent access, all connecting through the same gateway + MCP server backend.

## Three-Tier Agent Architecture

### Tier 1: Arbitrary Agents
Any agent that can speak MCP Streamable HTTP or connect via raw gateway WebSocket. No Convene-specific SDK required.

**Connection:** Direct WebSocket with JWT, or MCP with Bearer token.

### Tier 2: Platform-Specific Integrations
Pre-built integrations for specific agent platforms:
- **Any MCP client** — Streamable HTTP with Bearer token auth — see [Connecting via MCP](/docs/agent-platform/connecting/mcp-quickstart)
- **OpenClaw** — Plugin + skill (`@convene/openclaw-plugin`) — see [OpenClaw](/docs/openclaw/plugin-guide)
- **Claude Code** — Skill (`.claude/skills/convene-meeting/SKILL.md`) — see [Claude Code Channel](/docs/agent-platform/connecting/claude-code-channel)
- **Convene CLI** — Python CLI wrapping REST API + gateway WebSocket — see [CLI](/docs/agent-platform/connecting/cli)

### Tier 3: Convene Managed Agents
Pre-configured agents available in the web UI. Select an agent, assign it to a meeting, and Convene runs it as a managed service — no code required.

- **Free tier**: User provides their own Anthropic API key
- **Premium tier**: Convene provides the API key (billed), free trial available
- **Activation flow**: Select agent → assign to meeting → Convene spawns and manages it

## Convene Managed Agents

| Agent | Description | Category |
|-------|-------------|----------|
| Meeting Summarizer | Produces minutes every 5 min | summarization |
| Action Item Tracker | Focuses on tasks and assignments | productivity |
| Decision Logger | Captures decisions with context | documentation |
| Code Discussion Tracker | Extracts code-related topics | engineering |

## Authentication

All agents authenticate via API key + OAuth 2.1 token exchange. See [MCP Auth](/docs/agent-platform/connecting/mcp-auth) for the full flow.

## See Also

- [MCP Auth](/docs/agent-platform/connecting/mcp-auth) — OAuth 2.1 authorization flow
- [Connecting via MCP](/docs/agent-platform/connecting/mcp-quickstart) — Connect any MCP-compatible agent
- [Claude Code Channel](/docs/agent-platform/connecting/claude-code-channel) — Use Claude Code as a meeting participant
- [OpenClaw](/docs/openclaw/plugin-guide) — Connect via OpenClaw channels
- [CLI](/docs/agent-platform/connecting/cli) — Terminal-based access
