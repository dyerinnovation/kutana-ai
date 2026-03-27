# Connecting via MCP

Connect any MCP-compatible agent to Convene AI. Agents authenticate with a Bearer token and get access to 20+ tools for joining meetings, reading transcripts, managing tasks, speaking via TTS, and coordinating with other agents.

## Prerequisites

- A Convene API key — see [Get an API key](#get-an-api-key)
- An MCP client (Claude Agent SDK, Claude Code, Claude Desktop, or any MCP-compatible framework)

## Get an API key

1. Sign in to your Convene instance
2. Go to **Settings → API Keys**
3. Click **Generate Key** — select the **Agent** scope
4. Copy the key — it starts with `cvn_`

## Connection details

| Parameter | Value |
|-----------|-------|
| Transport | Streamable HTTP |
| MCP URL | `http://convene.spark-b0f2.local/mcp` |
| Auth header | `Authorization: Bearer <your-api-key>` |

If your Convene instance is at a different address, set `CONVENE_MCP_URL` to override the default.

## Quick start: Python agent

The following example uses the Claude Agent SDK. The same MCP connection parameters work with any framework that supports Streamable HTTP MCP.

```bash
pip install claude-agent-sdk
export CONVENE_API_KEY="cvn_..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

```python
import asyncio
import os
from claude_agent_sdk import Agent, AgentConfig, MCPServerConfig

convene_mcp = MCPServerConfig(
    name="convene",
    url=os.environ.get("CONVENE_MCP_URL", "http://convene.spark-b0f2.local/mcp"),
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
    await agent.run(
        "List available meetings, join the most recent active one, "
        "and start monitoring for action items."
    )

asyncio.run(main())
```

## Quick start: Claude Code

See [Claude Code Channel](/docs/connecting-agents/custom-agents/claude-code-channel) for step-by-step setup.

## Quick start: Any MCP client

Configure your MCP client with:

```json
{
  "mcpServers": {
    "convene": {
      "type": "http",
      "url": "http://convene.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer <your-api-key>"
      }
    }
  }
}
```

The Convene MCP server accepts any client that speaks the MCP Streamable HTTP protocol.

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

- [MCP Authentication](/docs/connecting-agents/custom-agents/mcp-auth) — OAuth 2.1 token exchange details
- [Claude Code Channel](/docs/connecting-agents/custom-agents/claude-code-channel) — Claude Code as a meeting participant
- [OpenClaw Plugin](/docs/connecting-agents/custom-agents/openclaw-plugin) — Connect via OpenClaw channels
- [Convene CLI](/docs/connecting-agents/custom-agents/cli) — Terminal-based access
