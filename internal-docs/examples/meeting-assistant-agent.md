# Convene AI Meeting Assistant Agent

Example agents built with the Claude Agent SDK that join Convene AI meetings, monitor transcripts, and take automated actions. Includes multiple agent templates for different use cases.

## How It Works

Each agent uses the **hosted Convene MCP Server** as its interface to the meeting platform. The MCP server authenticates via your API key and provides tools for joining meetings, reading transcripts, and creating tasks. The agent's **system prompt** determines its behavior.

## Architecture

```
Claude Agent SDK Agent
    │
    │  Streamable HTTP + API Key (https://convene.spark-b0f2.local/mcp)
    ▼
Convene MCP Server (hosted)
    │
    │  Authenticated API calls          WebSocket (transcripts)
    ▼                                    ▼
API Server                           Agent Gateway
```

## Setup

### 1. Prerequisites
- Python 3.12+
- A Convene account and agent API key
- An Anthropic API key

### 2. Register an Agent and Get an API Key

In the Convene web UI at [https://convene.spark-b0f2.local](https://convene.spark-b0f2.local):
1. Go to Dashboard → **Create Agent**
2. Enter a name and system prompt
3. Configure **capabilities** (listen, transcribe, text_only, voice, etc.) — these control what the agent can do
4. Click the agent to view its detail page
5. Generate an API key (copy it — shown only once!)

> **Note:** Capabilities are set in the UI when creating the agent. The API key is what you use in your code to connect.

Or via the **Convene CLI**:
```bash
convene login --api-url https://convene.spark-b0f2.local
convene agents create "Meeting Assistant" --prompt "You are a helpful meeting assistant."
convene keys generate <AGENT_ID>
```

### 3. Run the Agent

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export CONVENE_API_KEY=cvn_...   # From step 2

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

For Claude Desktop or Claude Code, add the Convene MCP server to your settings:

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

Set `CONVENE_API_KEY=cvn_...` in your environment, then open Claude Code and say "Join the meeting on Convene".

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
