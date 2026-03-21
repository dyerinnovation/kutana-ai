# Convene AI Agent Platform Architecture

## Overview

Convene AI supports three tiers of agent access, all connecting through the same gateway + MCP server backend.

## Access Matrix

### Human Access

| Channel | Transport | Status |
|---------|-----------|--------|
| Web UI (browser) | WebSocket to gateway (mic audio) + REST API | Implemented |
| iPhone app | Future — same WebSocket/REST, native audio capture | Deferred |

### Agent Access

| Channel | Transport | How It Connects |
|---------|-----------|-----------------|
| CLI (`convene` CLI) | REST API + WebSocket | `convene login`, `convene meeting join <id>` |
| MCP (Streamable HTTP) | HTTP to MCP server | Any MCP client → `http://mcp:3001/mcp` with Bearer token |
| Claude Code skill | MCP (via configured remote server) | `/convene` skill uses MCP server |
| OpenClaw skill | MCP or direct API | OpenClaw plugin registers native tools |
| Claude Agent SDK | MCP | `MCPServerConfig(url=...)` in agent config |
| Arbitrary agents | MCP or direct WebSocket | Any platform that speaks MCP or raw gateway WebSocket |

## Three-Tier Agent Architecture

### Tier 1: Arbitrary Agents
Any agent that can speak MCP Streamable HTTP or connect via raw gateway WebSocket. No Convene-specific SDK required.

**Connection:** Direct WebSocket with JWT, or MCP with Bearer token.

### Tier 2: Platform-Specific Integrations
Pre-built integrations for specific agent platforms:
- **Claude Agent SDK** — `MCPServerConfig` with Bearer token auth
- **OpenClaw** — Plugin + skill (`@convene/openclaw-plugin`)
- **Claude Code** — Skill (`.claude/skills/convene-meeting/SKILL.md`)
- **Convene CLI** — Python CLI wrapping REST API + gateway WebSocket

### Tier 3: Prebuilt Agents (Hosted by Convene)
Agent templates in the web UI. User selects a template, assigns it to a meeting, and Convene runs it server-side.

- **Free tier**: User provides their own Anthropic API key
- **Premium tier**: Convene provides the API key (billed), free trial available
- **Activation flow**: Select template → assign to meeting → Convene spawns agent → joins via MCP

## Authentication Flow

All access paths use the same OAuth 2.1 token exchange:

```
API Key (long-lived, per agent)
    │
    │  POST /api/v1/token/mcp (or /token/gateway)
    ▼
JWT Token (short-lived, scoped)
    │
    │  Authorization: Bearer <token>
    ▼
MCP Server / Agent Gateway
```

JWT claims:
- `sub`: user_id (owner of the API key)
- `agent_config_id`: the agent configuration
- `type`: "mcp" or "gateway"
- `scopes`: ["meetings:read", "meetings:join", "tasks:write"]

## API Key Security

- Stored as SHA-256 hashes (never plaintext)
- Key prefix (first 8 chars) shown for identification
- Optional expiration (`expires_at`)
- Rate limiting per key (Redis-based)
- Audit logging on creation, usage, and revocation
- User-provided Anthropic API keys encrypted at rest (Fernet)

## Prebuilt Agent Templates

| Template | Description | Category |
|----------|-------------|----------|
| Meeting Summarizer | Produces minutes every 5 min | summarization |
| Action Item Tracker | Focuses on tasks and assignments | productivity |
| Decision Logger | Captures decisions with context | documentation |
| Code Discussion Tracker | Extracts code-related topics | engineering |
