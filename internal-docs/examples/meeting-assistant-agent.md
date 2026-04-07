# Kutana AI Meeting Assistant Agent

Example agents built with the Claude Agent SDK that join Kutana AI meetings, monitor transcripts, and take automated actions. Includes multiple agent templates for different use cases.

## How It Works

Each agent uses the **hosted Kutana MCP Server** as its interface to the meeting platform. The MCP server authenticates via your API key and provides tools for joining meetings, reading transcripts, and creating tasks. The agent's **system prompt** determines its behavior.

## Architecture

```
Claude Agent SDK Agent
    │
    │  Streamable HTTP + API Key (https://kutana.spark-b0f2.local/mcp)
    ▼
Kutana MCP Server (hosted)
    │
    │  Authenticated API calls          WebSocket (transcripts)
    ▼                                    ▼
API Server                           Agent Gateway
```

## Setup

### 1. Prerequisites
- Python 3.12+
- A Kutana account and agent API key
- An Anthropic API key

### 2. Register an Agent and Get an API Key

In the Kutana web UI at [https://kutana.spark-b0f2.local](https://kutana.spark-b0f2.local):
1. Go to Dashboard → **Create Agent**
2. Enter a name and system prompt
3. Configure **capabilities** (listen, transcribe, text_only, voice, etc.) — these control what the agent can do
4. Click the agent to view its detail page
5. Generate an API key (copy it — shown only once!)

> **Note:** Capabilities are set in the UI when creating the agent. The API key is what you use in your code to connect.

Or via the **Kutana CLI**:
```bash
kutana login --api-url https://kutana.spark-b0f2.local
kutana agents create "Meeting Assistant" --prompt "You are a helpful meeting assistant."
kutana keys generate <AGENT_ID>
```

### 3. Run the Agent

```bash
export ANTHROPIC_API_KEY=sk-ant-...
export KUTANA_API_KEY=cvn_...   # From step 2

cd internal-docs/examples/meeting-assistant-agent
uv run python agent.py
```

## Agent Templates

### Meeting Assistant (default)
Joins meetings, monitors transcripts, extracts action items, and creates tasks. Uses turn management (`kutana_raise_hand`, `kutana_mark_finished_speaking`) and chat (`kutana_send_chat_message`) to interact with participants.

```bash
uv run python agent.py
```

### Meeting Summarizer
Produces meeting minutes every 5 minutes and a final summary when the meeting ends. Shares summaries via `kutana_send_chat_message` and can present verbally using `kutana_raise_hand`.

```bash
uv run python agent.py --template summarizer
```

### Action Item Tracker
Focuses exclusively on identifying and tracking tasks, assignments, and deadlines. Confirms action items via chat and raises hand to clarify assignments.

```bash
uv run python agent.py --template action-tracker
```

### Decision Logger
Captures decisions made during meetings — who decided, what was decided, and any context. Posts decision confirmations to chat and raises hand to ask for clarification.

```bash
uv run python agent.py --template decision-logger
```

## Customization

The agent's behavior is entirely driven by its system prompt. Edit the templates in `agent.py` or provide a custom prompt:

```bash
uv run python agent.py --system-prompt "You are a code review discussion tracker..."
```

## MCP Server Configuration

For Claude Desktop or Claude Code, add the Kutana MCP server to your settings:

```json
{
  "mcpServers": {
    "kutana": {
      "type": "streamableHttp",
      "url": "https://kutana.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer ${KUTANA_API_KEY}"
      }
    }
  }
}
```

Set `KUTANA_API_KEY=cvn_...` in your environment, then open Claude Code and say "Join the meeting on Kutana".

## Other Integration Options

### Kutana CLI
Manage agents, meetings, and API keys from the terminal:
```bash
uv run kutana --help
```
See `services/cli/` for the CLI source.

### OpenClaw Plugin
For OpenClaw-based agents, install the Kutana plugin:
```bash
openclaw plugins install @kutana/openclaw-plugin
```
See `integrations/openclaw-plugin/` for details.
