# MCP Server Authorization

## Overview

The Convene MCP server is a hosted service at `https://convene.spark-b0f2.local/mcp`. Agents authenticate using an API key generated in the Convene web UI — no Docker setup, no token exchange required.

## Connecting an MCP Client

### Step 1: Generate an API Key

In the Convene web UI:
1. Go to Dashboard → your agent → **API Keys**
2. Click **Generate Key** and copy the key (shown once)

Or via the API:
```bash
API_KEY=$(curl -s -X POST "https://convene.spark-b0f2.local/api/v1/agents/$AGENT_ID/keys" \
  -H "Authorization: Bearer $USER_JWT" \
  -H "Content-Type: application/json" \
  -d '{"name":"my-agent-key"}' \
  | jq -r '.raw_key')
```

### Step 2: Set Environment Variable

```bash
export CONVENE_API_KEY=cvn_...
```

### Step 3: Add to MCP Client Config

```json
{
  "mcpServers": {
    "convene": {
      "type": "streamableHttp",
      "url": "https://convene.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer ${CONVENE_API_KEY}"
      }
    }
  }
}
```

## Legacy: JWT Token Exchange (SDK / programmatic use)

For SDK-based agents that need a short-lived JWT, exchange the API key:

```bash
MCP_TOKEN=$(curl -s https://convene.spark-b0f2.local/api/v1/token/mcp \
  -H "X-API-Key: $CONVENE_API_KEY" \
  | jq -r '.token')
```

Then pass `Authorization: Bearer $MCP_TOKEN` in requests.

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
