# MCP Authentication Flow

## Purpose
Verify the full API key → MCP JWT → Bearer auth chain: token exchange, JWT claims, scoped access, and rejection of invalid credentials.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed
- `$TOKEN`, `$AGENT_ID`, `$API_KEY` exported
- API server (8000) and MCP server (3001) running

## Step 1: Exchange API Key for MCP Token

```bash
MCP_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $API_KEY")

echo "$MCP_RESPONSE" | jq .
```

Expected response (200):
```json
{
  "token": "eyJ...",
  "agent_config_id": "<uuid>",
  "scopes": ["meetings:read", "meetings:join", "tasks:write"]
}
```

Save the token:
```bash
export MCP_TOKEN=$(echo "$MCP_RESPONSE" | jq -r '.token')
echo "MCP_TOKEN=$MCP_TOKEN"
```

## Step 2: Decode and Verify JWT Claims

```bash
# Decode the JWT payload (base64)
echo "$MCP_TOKEN" | cut -d. -f2 | base64 -d 2>/dev/null | jq .
```

Expected claims:
```json
{
  "sub": "<user-uuid>",
  "agent_config_id": "<agent-uuid>",
  "type": "mcp",
  "scopes": ["meetings:read", "meetings:join", "tasks:write"],
  "exp": 1741...
}
```

Verify:
- `type` is `"mcp"`
- `sub` matches your user ID
- `agent_config_id` matches `$AGENT_ID`
- `scopes` includes the expected permissions
- `exp` is a future timestamp

## Step 3: Exchange API Key for Gateway Token

```bash
GW_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/token/gateway \
  -H "X-API-Key: $API_KEY")

echo "$GW_RESPONSE" | jq .
```

Expected response (200):
```json
{
  "token": "eyJ...",
  "agent_config_id": "<uuid>",
  "name": "test-agent"
}
```

Save the token:
```bash
export GATEWAY_TOKEN=$(echo "$GW_RESPONSE" | jq -r '.token')
echo "GATEWAY_TOKEN=$GATEWAY_TOKEN"
```

## Step 4: Use MCP Token to Call MCP Tools

```bash
# List meetings via MCP server using Bearer auth
curl -s -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "list_meetings",
      "arguments": {}
    },
    "id": 1
  }' | jq .
```

Expected: 200 with JSON-RPC response containing meeting list.

## Step 5: Verify 401 Without Token

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {"name": "list_meetings", "arguments": {}},
    "id": 1
  }'
```

Expected: `401`

## Step 6: Verify 401 With Invalid Token

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid.token.here" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {"name": "list_meetings", "arguments": {}},
    "id": 1
  }'
```

Expected: `401`

## Step 7: Verify 401 With Revoked API Key

```bash
# Get the key ID
KEY_ID=$(curl -s http://localhost:8000/api/v1/agents/$AGENT_ID/keys \
  -H "Authorization: Bearer $TOKEN" | jq -r '.items[0].id')

# Revoke the key
curl -s -X DELETE http://localhost:8000/api/v1/agents/$AGENT_ID/keys/$KEY_ID \
  -H "Authorization: Bearer $TOKEN" -w "\nHTTP Status: %{http_code}\n"
```

Expected: HTTP Status `204`

```bash
# Try to exchange revoked key for MCP token
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $API_KEY"
```

Expected: `401`

## Step 8: Generate Fresh API Key (for subsequent tests)

```bash
export API_KEY=$(curl -s -X POST http://localhost:8000/api/v1/agents/$AGENT_ID/keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "post-revoke-key"}' | jq -r '.raw_key')

echo "New API_KEY=$API_KEY"
```

## Verification Checklist

- [ ] POST `/token/mcp` with valid API key returns JWT with correct scopes
- [ ] JWT payload contains `type: "mcp"`, valid `sub`, valid `agent_config_id`
- [ ] POST `/token/gateway` with valid API key returns token with agent name
- [ ] MCP tool call with valid Bearer token succeeds
- [ ] MCP tool call without token returns 401
- [ ] MCP tool call with invalid token returns 401
- [ ] Revoked API key cannot be exchanged for token (401)
- [ ] Fresh API key works after revocation

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| 401 on token exchange | Verify `$API_KEY` starts with `cvn_`. Re-generate if needed |
| JWT decode fails | Add padding: `echo "$MCP_TOKEN" \| cut -d. -f2 \| tr -d '\n' \| base64 -d` |
| MCP server 404 | Verify MCP server is running on port 3001. Check `/mcp` path |
| Gateway token missing `name` | Verify agent was created with a name field |
| Scopes empty | Check token exchange endpoint — scopes are hardcoded in `token.py` |

## Cleanup

```bash
# Fresh API key was generated in Step 8
# Re-export MCP_TOKEN for use in subsequent test docs:
export MCP_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $API_KEY" | jq -r '.token')
```
