# Convene AI Meeting Assistant Agent

An example agent built with the Claude Agent SDK that joins Convene AI meetings, monitors transcripts, extracts action items, and creates tasks automatically.

## How It Works

The agent uses the **Convene MCP Server** as its interface to the meeting platform. The MCP server runs as a Docker container serving Streamable HTTP and provides tools for joining meetings, reading transcripts, and creating tasks. The agent's **system prompt** determines its behavior — change the prompt to make it summarize, track decisions, generate reports, or anything else.

## Architecture

```
Claude Agent SDK Agent
    │
    │  Streamable HTTP (http://localhost:3001/mcp)
    ▼
MCP Server (Docker container)
    │
    │  HTTP (API key → gateway JWT)     WebSocket (transcripts)
    ▼                                   ▼
API Server                          Agent Gateway
```

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
6. Note the agent config ID from the URL

Or via the API:
```bash
# Register
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
```

### 3. Start the MCP Server (Docker)

```bash
# Set the API key and agent config ID
export MCP_API_KEY=cvn_...           # From step 2
export MCP_AGENT_CONFIG_ID=<uuid>    # From step 2

# Start the MCP server container
docker compose up mcp-server -d
```

The MCP server will be available at `http://localhost:3001/mcp`.

### 4. Run the Agent

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export MCP_SERVER_URL=http://localhost:3001   # Default

cd examples/meeting-assistant-agent
uv run python agent.py
```

The agent will:
1. List available meetings
2. Join the most recent active meeting
3. Monitor transcript segments
4. Extract action items and decisions
5. Create tasks in Convene for each action item
6. Provide periodic summaries

## Customization

The agent's behavior is entirely driven by its system prompt. Edit the `system_prompt` in `agent.py` to change what the agent does. Some ideas:

- **Decision tracker**: Focus on capturing decisions and who made them
- **Summarizer**: Produce meeting minutes every 5 minutes
- **Action item extractor**: Only create tasks, ignore everything else
- **Meeting facilitator**: Track agenda items and time spent on each

## MCP Server Configuration

The MCP server runs as a Streamable HTTP service in Docker. For Claude Desktop or Claude Code, configure it as a remote MCP server:

```json
{
  "mcpServers": {
    "convene": {
      "url": "http://localhost:3001/mcp"
    }
  }
}
```

The server-side environment variables (`MCP_API_KEY`, `MCP_AGENT_CONFIG_ID`) are configured on the Docker container, not on the client.
