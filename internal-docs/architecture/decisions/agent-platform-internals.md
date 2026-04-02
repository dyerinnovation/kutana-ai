# Agent Platform — Internal Implementation Details

This document covers implementation-level details for the agent platform. For the user-facing overview see `external-docs/agent-platform/overview.md`.

## Access Matrix

### Human Access

| Channel | Transport | Status |
|---------|-----------|--------|
| Web UI (browser) | WebSocket to gateway (mic audio) + REST API | Implemented |
| iPhone app | Future — same WebSocket/REST, native audio capture | Deferred |

### Agent Access

| Channel | Transport | How It Connects |
|---------|-----------|-----------------|
| CLI (`kutana` CLI) | REST API + WebSocket | `kutana login`, `kutana meeting join <id>` |
| MCP (Streamable HTTP) | HTTP to MCP server | Any MCP client → `http://mcp:3001/mcp` with Bearer token |
| Claude Code skill | MCP (via configured remote server) | `/kutana` skill uses MCP server |
| OpenClaw skill | MCP or direct API | OpenClaw plugin registers native tools |
| Claude Agent SDK | MCP | `MCPServerConfig(url=...)` in agent config |
| Arbitrary agents | MCP or direct WebSocket | Any platform that speaks MCP or raw gateway WebSocket |

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

## See Also

- `internal-docs/architecture/patterns/auth-and-api-keys.md` — JWT/API key implementation
- `external-docs/agent-platform/connecting/mcp-auth.md` — OAuth 2.1 flow (user-facing)
