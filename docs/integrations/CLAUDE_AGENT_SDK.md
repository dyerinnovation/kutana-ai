# Claude Agent SDK Integration Guide

## Overview

Build Claude Agent SDK agents that participate in Convene AI meetings. Agents connect via the MCP server using OAuth 2.1 Bearer token authentication.

## Quick Start

### 1. Install Dependencies

```bash
cd examples/meeting-assistant-agent
uv sync
```

### 2. Get Credentials

```bash
# Register and get user JWT
TOKEN=$(curl -s http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"agent@example.com","password":"pass123","name":"Agent User"}' \
  | jq -r '.token')

# Create agent
AGENT_ID=$(curl -s http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"My Agent","system_prompt":"...","capabilities":["listen","transcribe"]}' \
  | jq -r '.id')

# Generate API key
API_KEY=$(curl -s -X POST "http://localhost:8000/api/v1/agents/$AGENT_ID/keys" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name":"sdk-key"}' \
  | jq -r '.raw_key')

# Exchange for MCP token
export MCP_BEARER_TOKEN=$(curl -s http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $API_KEY" \
  | jq -r '.token')
```

### 3. Run

```bash
export ANTHROPIC_API_KEY=sk-ant-...
uv run python agent.py
```

## Agent Templates

| Template | Command | Description |
|----------|---------|-------------|
| Assistant | `python agent.py` | Full-featured meeting assistant |
| Summarizer | `python agent.py --template summarizer` | Periodic meeting minutes |
| Action Tracker | `python agent.py --template action-tracker` | Task extraction |
| Decision Logger | `python agent.py --template decision-logger` | Decision capture |

## Custom Agents

```python
from claude_agent_sdk import Agent, AgentConfig, MCPServerConfig

convene_mcp = MCPServerConfig(
    name="convene",
    url="http://localhost:3001/mcp",
    headers={"Authorization": f"Bearer {mcp_token}"},
)

config = AgentConfig(
    model="claude-sonnet-4-6",
    system_prompt="Your custom meeting agent prompt...",
    mcp_servers=[convene_mcp],
)

agent = Agent(config)
result = await agent.run("Join the active meeting and monitor for action items.")
```

## Available MCP Tools

| Tool | Parameters | Description |
|------|-----------|-------------|
| `list_meetings` | — | List all meetings |
| `create_meeting` | title, platform | Create a meeting |
| `start_meeting` | meeting_id | Start a scheduled meeting |
| `end_meeting` | meeting_id | End an active meeting |
| `join_meeting` | meeting_id | Join via gateway |
| `join_or_create_meeting` | title | Join or create meeting |
| `leave_meeting` | — | Leave current meeting |
| `get_transcript` | last_n | Get recent transcript |
| `get_tasks` | meeting_id | List tasks |
| `create_task` | meeting_id, description, priority | Create task |
| `get_participants` | — | List participants |

## See Also

- [MCP Auth Flow](../technical/MCP_AUTH.md) — Token exchange details
- [Agent Platform Architecture](../technical/AGENT_PLATFORM.md) — Three-tier architecture
- [Example Code](../../examples/meeting-assistant-agent/) — Full working example
