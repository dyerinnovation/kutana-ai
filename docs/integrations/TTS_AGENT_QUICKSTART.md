# TTS Agent Quickstart

Build an AI agent that speaks in Kutana meetings using text-to-speech. The agent joins a meeting, listens to the transcript, and speaks its responses aloud.

## How TTS Works

1. Agent joins with the `tts_enabled` capability
2. Agent calls `kutana_speak(text)` to deliver spoken content
3. The gateway synthesizes audio via the configured TTS provider
4. Audio is broadcast to all participants in real time
5. Each TTS agent gets a distinct voice from the voice pool

## Prerequisites

- A Kutana API key (`cvn_...`) with **Agent** scope
- An Anthropic API key for the Claude Agent SDK
- Python 3.12+

## Quick Start

```bash
pip install claude-agent-sdk
export KUTANA_API_KEY="cvn_..."
export ANTHROPIC_API_KEY="sk-ant-..."
```

```python
import asyncio
import os
from claude_agent_sdk import Agent, AgentConfig, MCPServerConfig

async def main():
    agent = Agent(
        config=AgentConfig(
            model="claude-sonnet-4-6",
            mcp_servers=[
                MCPServerConfig(
                    url="http://dev.kutana.ai/mcp",
                    headers={"Authorization": f"Bearer {os.environ['KUTANA_API_KEY']}"},
                ),
            ],
        ),
    )

    result = await agent.run(
        "List available meetings. Join the first active meeting with "
        "capabilities=['tts_enabled']. Listen to the transcript, then "
        "use kutana_speak to greet the participants and summarize what "
        "has been discussed so far."
    )
    print(result)

asyncio.run(main())
```

## Key Tools

| Tool | Description |
|------|-------------|
| `kutana_join_meeting(meeting_id, capabilities=["tts_enabled"])` | Join with TTS capability |
| `kutana_join_meeting(meeting_id, capabilities=["tts_enabled"], tts_voice_id="...")` | Join with a specific voice |
| `kutana_speak(text)` | Speak text aloud (handles turn management automatically) |
| `kutana_get_transcript(last_n=50)` | Read recent transcript |
| `kutana_raise_hand(topic="...")` | Request to speak (manual turn management) |
| `kutana_mark_finished_speaking()` | Release the floor |

## Speaking Modes

### Automatic (recommended)

`kutana_speak` handles the full lifecycle: raise hand, wait for turn, start speaking, synthesize, mark finished.

```
kutana_speak(text="I think we should prioritize the API redesign.")
```

### Manual

For finer control:

1. `kutana_raise_hand(topic="API priorities")`
2. Wait for `turn.your_turn` event
3. `kutana_speak(text="...")` (one or more times)
4. `kutana_mark_finished_speaking()`

## Voice Selection

By default, each agent gets a voice from the pool. To use a specific voice:

```python
kutana_join_meeting(
    meeting_id="...",
    capabilities=["tts_enabled"],
    tts_voice_id="a0e99841-438c-4a64-b679-ae501e7d6091"
)
```

## Capabilities Reference

| Capability | Effect |
|------------|--------|
| `text_only` | Default. Receive transcript, send/receive chat. No audio. |
| `tts_enabled` | `kutana_speak` text is synthesized and broadcast as audio. |
| `voice` | Bidirectional raw PCM16 audio via the sidecar WebSocket (advanced). |

## Character Budget

Each TTS session has a per-session character budget (default: 100,000 characters). If exhausted, `kutana_speak` returns an error. The budget resets on rejoin.

## See Also

- [Voice Agent Quickstart](./VOICE_AGENT_QUICKSTART.md) — Raw audio agents (advanced)
- [Claude Code Channel](./CLAUDE_CODE_CHANNEL.md) — Claude Code as a meeting participant
- [MCP Quickstart](/docs/connecting-agents/custom-agents/mcp-quickstart) — General MCP setup
