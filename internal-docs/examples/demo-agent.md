# Kutana AI Demo Agent

A minimal Claude-powered agent that joins a Kutana AI meeting via WebSocket,
receives live transcript segments and entity extraction events, and uses Claude
Sonnet with tool use to respond intelligently.

## Setup

```bash
pip install anthropic httpx websockets
```

## Usage

```bash
export ANTHROPIC_API_KEY=your-anthropic-key
export CONVENE_API_KEY=your-agent-api-key   # cvn_... from dashboard
export CONVENE_API_URL=http://localhost:8000

python agent.py --meeting-id <meeting_id>
```

If your agent gateway runs on a different host/port:

```bash
export CONVENE_GATEWAY_URL=ws://localhost:8003
python agent.py --meeting-id <meeting_id>
```

## Getting a CONVENE_API_KEY

1. Register a user and create an agent via the API or dashboard.
2. Generate an API key for the agent:

```bash
# Get a user JWT
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpass"}' | jq -r '.token')

# Create an agent
AGENT_ID=$(curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Agent","system_prompt":"Meeting monitor","capabilities":["listen","transcribe","extract_tasks"]}' \
  | jq -r '.id')

# Generate an API key
export CONVENE_API_KEY=$(curl -s -X POST "http://localhost:8000/api/v1/agents/$AGENT_ID/keys" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"demo-key"}' | jq -r '.raw_key')
```

## What the Agent Does

- Connects to the Kutana AI agent gateway via WebSocket
- Joins the specified meeting with `listen`, `transcribe`, and `extract_tasks` capabilities
- Receives live transcript segments and prints them to stdout
- Receives entity extraction events (tasks, decisions, key points, etc.)
- Every 15 seconds, runs a Claude Sonnet agent turn to analyze recent events
- Claude can use three tools:
  - **`accept_task`** — acknowledge a task or action item
  - **`reply`** — send a text message to the meeting channel
  - **`get_meeting_recap`** — retrieve transcript and extracted entities so far

## See Also

- [`examples/meeting-assistant-agent/`](../meeting-assistant-agent/) — higher-level MCP-based agent
- [`docs/integrations/CLAUDE_AGENT_SDK.md`](../../docs/integrations/CLAUDE_AGENT_SDK.md) — full SDK guide
