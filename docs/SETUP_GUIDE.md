# Developer Onboarding Guide

Get up and running with Kutana agent development in under 10 minutes. This guide covers API key setup, connecting your first agent, and joining a meeting.

## Checklist

- [ ] Get a Kutana API key
- [ ] Set environment variables
- [ ] Choose a connection method
- [ ] Join your first meeting
- [ ] Send your first chat message
- [ ] (Optional) Enable TTS

## 1. Get a Kutana API Key

1. Sign in to your Kutana instance (e.g., `https://dev.kutana.ai`)
2. Go to **Settings > API Keys**
3. Click **Generate Key** — select **Agent** scope
4. Copy the key (starts with `cvn_`, shown once)

## 2. Set Environment Variables

```bash
# Required
export KUTANA_API_KEY="cvn_your_key_here"

# Required for Claude Agent SDK agents
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional: override MCP server URL
# export KUTANA_MCP_URL="https://dev.kutana.ai/mcp"
```

Add these to your shell profile (`~/.zshrc` or `~/.bashrc`) for persistence.

## 3. Choose a Connection Method

| Method | Best for | Setup time |
|--------|----------|------------|
| [Claude Code Channel](integrations/CLAUDE_CODE_CHANNEL.md) | Interactive Claude Code sessions | 5 min |
| [MCP (Streamable HTTP)](/docs/connecting-agents/custom-agents/mcp-quickstart) | Any MCP-compatible agent | 3 min |
| [Claude Agent SDK](/docs/connecting-agents/custom-agents/claude-agent-sdk) | Autonomous Python agents | 5 min |
| [CLI](/docs/connecting-agents/custom-agents/cli) | Shell scripts, piping, automation | 2 min |

### Quick: MCP config for any client

```json
{
  "mcpServers": {
    "kutana": {
      "type": "http",
      "url": "http://dev.kutana.ai/mcp",
      "headers": {
        "Authorization": "Bearer cvn_your_key_here"
      }
    }
  }
}
```

### Quick: Python agent

```bash
pip install claude-agent-sdk
```

```python
import asyncio
import os
from claude_agent_sdk import Agent, AgentConfig, MCPServerConfig

kutana_mcp = MCPServerConfig(
    name="kutana",
    url=os.environ.get("KUTANA_MCP_URL", "http://dev.kutana.ai/mcp"),
    headers={"Authorization": f"Bearer {os.environ['KUTANA_API_KEY']}"},
)

agent = Agent(
    config=AgentConfig(
        model="claude-sonnet-4-6",
        system_prompt="You are a meeting assistant.",
        mcp_servers=[kutana_mcp],
    ),
)

asyncio.run(agent.run("List meetings and join the most recent active one."))
```

## 4. Join Your First Meeting

Once connected, your agent can:

```python
# List available meetings
kutana_list_meetings()

# Join by ID
kutana_join_meeting(meeting_id="abc-123")

# Or find/create by title
kutana_join_or_create_meeting(title="Test Meeting")
```

## 5. Send Your First Chat Message

```python
kutana_send_chat_message(content="Hello from my agent!")
```

## 6. Enable TTS (Optional)

Join with TTS capability to speak aloud in meetings:

```python
kutana_join_meeting(
    meeting_id="abc-123",
    capabilities=["tts_enabled"]
)

# Speak via TTS
kutana_speak(text="Hello everyone, I'm your meeting assistant.")
```

See the [TTS Agent Quickstart](integrations/TTS_AGENT_QUICKSTART.md) for the full guide.

## Available Tools

All tools use the `kutana_` prefix. Key tools:

| Tool | Description |
|------|-------------|
| `kutana_list_meetings` | List meetings |
| `kutana_join_meeting` | Join a meeting |
| `kutana_leave_meeting` | Leave current meeting |
| `kutana_send_chat_message` | Send a chat message |
| `kutana_speak` | Speak via TTS |
| `kutana_get_transcript` | Read recent transcript |
| `kutana_raise_hand` | Request to speak |
| `kutana_create_task` | Create an action item |

See the [full tool reference](/docs/connecting-agents/custom-agents/mcp-quickstart#available-mcp-tools) for all 27+ tools.

## Example Agents

Ready-made agents in `internal-docs/examples/meeting-assistant-agent/`:

| Template | What it does |
|----------|--------------|
| `assistant` | Full meeting assistant — tasks, summaries, chat |
| `summarizer` | Meeting minutes and interim summaries |
| `action-tracker` | Action item detection and recording |
| `decision-logger` | Decision capture with rationale |

```bash
cd internal-docs/examples/meeting-assistant-agent
uv sync
uv run python agent.py --template assistant
```

## Next Steps

- [Claude Code Channel](integrations/CLAUDE_CODE_CHANNEL.md) — Interactive meeting participation
- [Voice Agent Quickstart](integrations/VOICE_AGENT_QUICKSTART.md) — Raw audio streaming
- [TTS Agent Quickstart](integrations/TTS_AGENT_QUICKSTART.md) — Text-to-speech agents
- [MCP Authentication](/docs/connecting-agents/custom-agents/mcp-auth) — Auth details
