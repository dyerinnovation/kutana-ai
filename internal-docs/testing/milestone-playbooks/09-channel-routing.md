# Channel Routing

## Purpose
Verify multi-agent channel routing: two agents subscribe/publish to named channels within the same meeting, with channel isolation ensuring unsubscribed channels are not received.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed
- [03-mcp-auth-flow.md](./03-mcp-auth-flow.md) verified
- `$TOKEN` exported
- API server (8000), gateway (8003), MCP server (3001) running
- Redis running (required for event relay)

## Step 1: Create Two Agents with API Keys

```bash
# Agent A — publisher
AGENT_A_ID=$(curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "agent-a-publisher",
    "system_prompt": "You publish tasks to channels.",
    "capabilities": ["listen", "transcribe"]
  }' | jq -r '.id')

API_KEY_A=$(curl -s -X POST http://localhost:8000/api/v1/agents/$AGENT_A_ID/keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "agent-a-key"}' | jq -r '.raw_key')

echo "AGENT_A_ID=$AGENT_A_ID"
echo "API_KEY_A=$API_KEY_A"

# Agent B — subscriber
AGENT_B_ID=$(curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "agent-b-subscriber",
    "system_prompt": "You subscribe to task channels.",
    "capabilities": ["listen", "transcribe"]
  }' | jq -r '.id')

API_KEY_B=$(curl -s -X POST http://localhost:8000/api/v1/agents/$AGENT_B_ID/keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "agent-b-key"}' | jq -r '.raw_key')

echo "AGENT_B_ID=$AGENT_B_ID"
echo "API_KEY_B=$API_KEY_B"
```

## Step 2: Get MCP Tokens for Both Agents

```bash
MCP_TOKEN_A=$(curl -s -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $API_KEY_A" | jq -r '.token')

MCP_TOKEN_B=$(curl -s -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $API_KEY_B" | jq -r '.token')

echo "MCP_TOKEN_A set: ${MCP_TOKEN_A:0:20}..."
echo "MCP_TOKEN_B set: ${MCP_TOKEN_B:0:20}..."
```

## Step 3: Create and Start a Meeting

```bash
export MEETING_ID=$(curl -s -X POST http://localhost:8000/api/v1/meetings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "Channel Routing Test",
    "platform": "kutana",
    "scheduled_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"
  }' | jq -r '.id')

curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/start \
  -H "Authorization: Bearer $TOKEN" > /dev/null

echo "MEETING_ID=$MEETING_ID"
```

## Step 4: Both Agents Join the Meeting

```bash
# Agent A joins
curl -s -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MCP_TOKEN_A" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "join_meeting",
      "arguments": {"meeting_id": "'"$MEETING_ID"'"}
    },
    "id": 1
  }' | jq .
```

Expected: Join confirmation with `room_name` and `granted_capabilities`.

```bash
# Agent B joins
curl -s -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MCP_TOKEN_B" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "join_meeting",
      "arguments": {"meeting_id": "'"$MEETING_ID"'"}
    },
    "id": 2
  }' | jq .
```

## Step 5: Agent B Subscribes to "tasks" Channel

```bash
curl -s -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MCP_TOKEN_B" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "subscribe_channel",
      "arguments": {"channel": "tasks"}
    },
    "id": 3
  }' | jq .
```

Expected:
```json
{
  "result": {
    "status": "subscribed",
    "channel": "tasks",
    "subscribed_channels": ["tasks"]
  }
}
```

## Step 6: Agent A Publishes to "tasks" Channel

```bash
curl -s -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MCP_TOKEN_A" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "publish_to_channel",
      "arguments": {
        "channel": "tasks",
        "payload": {
          "action": "new_task",
          "description": "Review Q1 metrics",
          "assigned_to": "agent-b",
          "priority": "high"
        }
      }
    },
    "id": 4
  }' | jq .
```

Expected:
```json
{
  "result": {
    "status": "published",
    "channel": "tasks"
  }
}
```

## Step 7: Verify Agent B Receives the Message

Agent B should receive the published message via the event relay. To verify, check the gateway logs for `data.channel.tasks` event delivery to Agent B.

```bash
# Check Redis stream for the channel event
docker exec -it $(docker compose ps -q redis) redis-cli \
  XRANGE kutana:events - + COUNT 5 | tail -20
```

Look for an event with `event_type: "data.channel.tasks"` and the payload matching what Agent A published.

## Step 8: Test Channel Isolation

```bash
# Agent A publishes to "decisions" channel (Agent B is NOT subscribed)
curl -s -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MCP_TOKEN_A" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "publish_to_channel",
      "arguments": {
        "channel": "decisions",
        "payload": {
          "decision": "Use PostgreSQL for storage",
          "rationale": "Team consensus"
        }
      }
    },
    "id": 5
  }' | jq .
```

Expected: Published successfully, but Agent B should NOT receive this event (not subscribed to "decisions").

Verify in gateway logs: the `data.channel.decisions` event should not be relayed to Agent B (only to agents subscribed to "decisions" or "*").

## Step 9: Subscribe to Additional Channel

```bash
# Agent B subscribes to "decisions" channel too
curl -s -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $MCP_TOKEN_B" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "subscribe_channel",
      "arguments": {"channel": "decisions"}
    },
    "id": 6
  }' | jq .
```

Expected:
```json
{
  "result": {
    "status": "subscribed",
    "channel": "decisions",
    "subscribed_channels": ["tasks", "decisions"]
  }
}
```

Now publish to "decisions" again — Agent B should receive it.

## Verification Checklist

- [ ] Two agents created with separate API keys and MCP tokens
- [ ] Both agents join the same meeting successfully
- [ ] `subscribe_channel("tasks")` returns subscribed status
- [ ] `publish_to_channel("tasks", {...})` returns published status
- [ ] Agent B receives the tasks channel message (check gateway logs / Redis)
- [ ] Publishing to unsubscribed channel ("decisions") does NOT reach Agent B
- [ ] After subscribing to "decisions", Agent B receives messages on that channel
- [ ] `subscribed_channels` list grows correctly with each subscription

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Join meeting fails | Verify meeting is "active". Check MCP token is valid |
| Subscribe returns error | Verify agent has joined a meeting first |
| Published events not appearing in Redis | Check gateway is running and connected to Redis |
| Agent B doesn't receive events | Check gateway logs for `_should_relay` decisions. Verify channel subscription |
| Redis XRANGE shows nothing | Verify `kutana:events` stream key. Gateway must be running to relay events |
| Both agents get all events | Check `_should_relay` logic — `data.channel.*` events should filter by subscription |

## Cleanup

```bash
curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/end \
  -H "Authorization: Bearer $TOKEN" > /dev/null
```
