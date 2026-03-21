# MCP Server OAuth 2.1 Authorization

## Overview

The Convene MCP server uses OAuth 2.1 Bearer token authentication per the [MCP authorization spec](https://modelcontextprotocol.io/docs/tutorials/security/authorization).

## Token Exchange Flow

```
1. User registers agent + generates API key (dashboard or API)
2. API key exchanged for MCP access token (JWT)
3. MCP client includes Bearer token on every request
4. MCP server validates JWT, scopes downstream calls
```

### Step 1: Generate API Key

```bash
# Via API
API_KEY=$(curl -s -X POST "http://localhost:8000/api/v1/agents/$AGENT_ID/keys" \
  -H "Authorization: Bearer $USER_JWT" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-agent-key"}' \
  | jq -r '.raw_key')
```

### Step 2: Exchange for MCP Token

```bash
MCP_TOKEN=$(curl -s http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $API_KEY" \
  | jq -r '.token')
```

### Step 3: Use in MCP Client

```json
{
  "mcpServers": {
    "convene": {
      "url": "http://localhost:3001/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_TOKEN>"
      }
    }
  }
}
```

## JWT Claims

```json
{
  "sub": "<user_id>",
  "agent_config_id": "<agent_config_id>",
  "type": "mcp",
  "scopes": ["meetings:read", "meetings:join", "tasks:write"],
  "iat": 1709827200,
  "exp": 1709830800
}
```

## Security Properties

| Property | Implementation |
|----------|---------------|
| No token passthrough | MCP server validates `type: "mcp"` claim |
| Scope minimization | Minimal scopes, elevation possible later |
| Stateless sessions | `stateless_http=True` — no session hijacking surface |
| Short-lived tokens | Default 1h expiry |
| Key hashing | API keys stored as SHA-256 hashes |

## Endpoints

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/api/v1/token/mcp` | POST | X-API-Key | Exchange API key for MCP JWT |
| `/api/v1/token/gateway` | POST | X-API-Key | Exchange API key for gateway JWT |
| `/api/v1/token/meeting` | POST | Bearer JWT | Get meeting JWT for human participants |

## Configuration

### MCP Server
```
MCP_JWT_SECRET=<shared-secret>  # Must match API server's JWT_SECRET
```

### API Server
```
JWT_SECRET=<shared-secret>
AGENT_GATEWAY_JWT_SECRET=<gateway-secret>
```
