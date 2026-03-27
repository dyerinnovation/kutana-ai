# Convene AI Meeting Assistant Agent

Example agents built with the Claude Agent SDK that join Convene AI meetings, monitor transcripts, and take automated actions. Includes multiple agent templates for different use cases.

## How It Works

Each agent uses the **Convene MCP Server** as its interface to the meeting platform. The MCP server authenticates via **OAuth 2.1 Bearer tokens** (JWT) and provides tools for joining meetings, reading transcripts, and creating tasks. The agent's **system prompt** determines its behavior.

## Architecture

```
Claude Agent SDK Agent
    │
    │  Streamable HTTP + Bearer Token (http://localhost:3001/mcp)
    ▼
MCP Server (Docker container)
    │
    │  JWT-authenticated API calls       WebSocket (transcripts)
    ▼                                    ▼
API Server                           Agent Gateway
```

## Authentication (OAuth 2.1)

Agents authenticate using a two-step token exchange:

1. **API key** (long-lived) → generated in the Convene dashboard
2. **MCP token** (short-lived JWT) → exchanged via `POST /api/v1/token/mcp`

```bash
# Exchange API key for MCP token
MCP_TOKEN=$(curl -s http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: cvn_..." \
  | jq -r '.token')
```

The MCP token includes:
- `sub`: user ID (scoped to the API key owner)
- `agent_config_id`: the agent's config
- `type`: "mcp" (validated by the MCP server)
- `scopes`: ["meetings:read", "meetings:join", "tasks:write"]

## Setup

### 1. Prerequisites
- Python 3.12+
- Docker (for the MCP server)
- A running Convene AI instance (API server + Agent Gateway)
- An Anthropic API key

### 2. Register an Agent

Via the Convene web UI:
1. Log in at http://localhost:5173
2. Go to Dashboard → "Create Agent"
3. Enter a name and system prompt
4. Click the agent to view its detail page
5. Generate an API key (copy it — shown only once!)

Or via the **Convene CLI** (recommended):
```bash
# Login
convene login --api-url http://localhost:8000

# Create agent
convene agents create "Meeting Assistant" --prompt "You are a helpful meeting assistant."

# Generate API key (copy the agent ID from the output above)
convene keys generate <AGENT_ID>

# Exchange for MCP token
MCP_TOKEN=$(curl -s http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: cvn_..." \
  | jq -r '.token')
```

Or via the API directly:
```bash
# Register + login
TOKEN=$(curl -s http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"password123","name":"User"}' \
  | jq -r '.token')

# Create agent
AGENT_ID=$(curl -s http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Meeting Assistant","system_prompt":"...","capabilities":["listen","transcribe"]}' \
  | jq -r '.id')

# Generate API key
API_KEY=$(curl -s -X POST "http://localhost:8000/api/v1/agents/$AGENT_ID/keys" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"agent-key"}' \
  | jq -r '.raw_key')

# Exchange for MCP token
MCP_TOKEN=$(curl -s http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $API_KEY" \
  | jq -r '.token')
```

### 3. Start the MCP Server (Docker)

```bash
# Set the JWT secret (must match API server)
export MCP_JWT_SECRET=change-me-in-production

# Start the MCP server container
docker compose up mcp-server -d
```

The MCP server will be available at `http://localhost:3001/mcp`.

### 4. Run the Agent

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export MCP_SERVER_URL=http://localhost:3001
export MCP_BEARER_TOKEN=$MCP_TOKEN   # From step 2

cd internal-docs/examples/meeting-assistant-agent
uv run python agent.py
```

## Agent Templates

### Meeting Assistant (default)
Joins meetings, monitors transcripts, extracts action items, and creates tasks.

```bash
uv run python agent.py
```

### Meeting Summarizer
Produces meeting minutes every 5 minutes and a final summary when the meeting ends.

```bash
uv run python agent.py --template summarizer
```

### Action Item Tracker
Focuses exclusively on identifying and tracking tasks, assignments, and deadlines.

```bash
uv run python agent.py --template action-tracker
```

### Decision Logger
Captures decisions made during meetings — who decided, what was decided, and any context.

```bash
uv run python agent.py --template decision-logger
```

## Customization

The agent's behavior is entirely driven by its system prompt. Edit the templates in `agent.py` or provide a custom prompt:

```bash
uv run python agent.py --system-prompt "You are a code review discussion tracker..."
```

## MCP Server Configuration

For Claude Desktop or Claude Code, configure as a remote MCP server with Bearer auth:

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

The MCP server validates the JWT on every request — no server-side API key configuration needed.

## Other Integration Options

### Convene CLI
Manage agents, meetings, and API keys from the terminal:
```bash
uv run convene --help
```
See `services/cli/` for the CLI source.

### OpenClaw Plugin
For OpenClaw-based agents, install the Convene plugin:
```bash
openclaw plugins install @convene/openclaw-plugin
```
See `integrations/openclaw-plugin/` for details.
