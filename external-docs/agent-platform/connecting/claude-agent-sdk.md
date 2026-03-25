# Claude Agent SDK Integration

Build autonomous Claude agents that participate in Convene AI meetings. Agents connect to the remote Convene MCP server using a Convene API key and the Claude Agent SDK.

## Prerequisites

- Python 3.12+
- `uv` (package manager)
- An Anthropic API key
- A Convene API key (see [Get an API key](#get-an-api-key))

## Get an API key

1. Sign in to your Convene instance
2. Go to **Settings → API Keys**
3. Click **Generate Key** — select the **Agent** scope
4. Copy the key (it starts with `cvn_`)

## Quick Start

### 1. Set environment variables

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
export CONVENE_API_KEY="cvn_..."
```

### 2. Install and run

```bash
cd examples/meeting-assistant-agent
uv sync
uv run python agent.py
```

The agent connects to the remote Convene MCP server, lists available meetings, joins the most recent active one, and begins monitoring the transcript.

## Writing a custom agent

```python
import asyncio
import os
from claude_agent_sdk import Agent, AgentConfig, MCPServerConfig

convene_mcp = MCPServerConfig(
    name="convene",
    url="http://convene.spark-b0f2.local/mcp",
    headers={"Authorization": f"Bearer {os.environ['CONVENE_API_KEY']}"},
)

config = AgentConfig(
    model="claude-sonnet-4-6",
    system_prompt="""You are a meeting assistant. Join the active meeting,
monitor the transcript, and create tasks for every action item you hear.""",
    mcp_servers=[convene_mcp],
    max_turns=100,
)

agent = Agent(config)

async def main() -> None:
    result = await agent.run(
        "List available meetings, join the most recent active one, "
        "and start monitoring for action items."
    )
    print(result)

asyncio.run(main())
```

If your Convene instance is at a different URL, override it:

```bash
export CONVENE_MCP_URL="https://your-convene-host.com/mcp"
```

```python
url = os.environ.get("CONVENE_MCP_URL", "http://convene.spark-b0f2.local/mcp")

convene_mcp = MCPServerConfig(
    name="convene",
    url=url,
    headers={"Authorization": f"Bearer {os.environ['CONVENE_API_KEY']}"},
)
```

## Agent templates

The example at `examples/meeting-assistant-agent/` ships with four ready-made templates:

| Template | Command | What it does |
|----------|---------|--------------|
| `assistant` | `python agent.py` | Full-featured meeting assistant — extracts tasks, summarizes discussion |
| `summarizer` | `python agent.py --template summarizer` | Produces interim and final meeting minutes |
| `action-tracker` | `python agent.py --template action-tracker` | Exclusively tracks action items and deadlines |
| `decision-logger` | `python agent.py --template decision-logger` | Captures decisions with rationale and context |

Pass `--system-prompt` to use a fully custom prompt:

```bash
uv run python agent.py --system-prompt "You are a compliance officer..."
```

## Available MCP tools

All tools use the `convene_` prefix.

### Meeting

| Tool | Parameters | Description |
|------|------------|-------------|
| `convene_list_meetings` | — | List upcoming and active meetings |
| `convene_create_meeting` | `title`, `platform` | Create a new meeting |
| `convene_join_meeting` | `meeting_id`, `capabilities` | Join a meeting via the gateway |
| `convene_join_or_create_meeting` | `title` | Join active meeting or create one |
| `convene_leave_meeting` | — | Leave the current meeting |
| `convene_start_meeting` | `meeting_id` | Start a scheduled meeting |
| `convene_end_meeting` | `meeting_id` | End an active meeting |

### Transcript & Tasks

| Tool | Parameters | Description |
|------|------------|-------------|
| `convene_get_transcript` | `last_n` | Get recent transcript segments |
| `convene_get_tasks` | `meeting_id` | List tasks for a meeting |
| `convene_create_task` | `meeting_id`, `description`, `priority` | Create a task |
| `convene_get_participants` | — | List current participants |

### Turn Management

| Tool | Parameters | Description |
|------|------------|-------------|
| `convene_raise_hand` | `priority`, `topic` | Request to speak |
| `convene_get_queue_status` | — | Check the speaker queue |
| `convene_start_speaking` | `text` | Speak — text is synthesized via TTS |
| `convene_mark_finished_speaking` | — | Release the floor |
| `convene_cancel_hand_raise` | — | Withdraw from the queue |

### Chat

| Tool | Parameters | Description |
|------|------------|-------------|
| `convene_send_chat_message` | `content`, `message_type` | Post to meeting chat |
| `convene_get_chat_messages` | `message_type`, `last_n` | Read chat history |

### Events & Channels

| Tool | Parameters | Description |
|------|------------|-------------|
| `convene_get_meeting_events` | `last_n`, `event_type` | Poll buffered meeting events |
| `convene_subscribe_channel` | `channel` | Subscribe to a named data channel |
| `convene_publish_to_channel` | `channel`, `payload` | Publish to a channel |
| `convene_get_channel_messages` | `channel`, `last_n` | Read buffered channel messages |

## See Also

- [OpenClaw Integration](./OPENCLAW.md) — Connect via OpenClaw channels
- [Claude Code Channel](./CLAUDE_CODE_CHANNEL.md) — Use Claude Code as a meeting participant
- [CLI](./CLI.md) — Terminal-based access
- [Example agent code](../../examples/meeting-assistant-agent/) — Full working example with four templates
