# TTS Agent Quickstart

Build an AI agent that speaks in meetings using text-to-speech. The agent joins a meeting, listens to the transcript, and speaks its responses aloud via the Kutana TTS pipeline.

## How TTS works

When an agent joins with the `tts_enabled` capability:

1. The agent calls `kutana_speak(meeting_id, text)` to deliver spoken content
2. The gateway synthesizes audio via the configured TTS provider (Cartesia, ElevenLabs, or Piper)
3. Audio is broadcast to all participants as `tts.audio` events
4. The browser plays the audio in real time

Each TTS-enabled agent gets a distinct voice from the voice pool, so multiple agents sound different in the same meeting.

## Prerequisites

- A Kutana API key (`cvn_...`) with **Agent** scope — see [MCP Quickstart](/docs/connecting-agents/custom-agents/mcp-quickstart#get-an-api-key)
- An Anthropic API key for the Claude Agent SDK
- Python 3.12+

## Quick start

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
            model="claude-sonnet-4-20250514",
            mcp_servers=[
                MCPServerConfig(
                    url="http://kutana.spark-b0f2.local/mcp",
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

## Key tools

| Tool | Description |
|------|-------------|
| `kutana_join_meeting(meeting_id, capabilities=["tts_enabled"])` | Join with TTS capability |
| `kutana_join_meeting(meeting_id, capabilities=["tts_enabled"], tts_voice_id="...")` | Join with a specific voice |
| `kutana_speak(meeting_id, text)` | Speak text aloud (handles turn management automatically) |
| `kutana_get_transcript(last_n=50)` | Read recent transcript |
| `kutana_raise_hand(meeting_id, topic="...")` | Request to speak (manual turn management) |
| `kutana_start_speaking(meeting_id)` | Confirm you have the floor |
| `kutana_mark_finished_speaking(meeting_id)` | Release the floor |

## Speaking modes

### Automatic (recommended)

`kutana_speak` handles the full lifecycle: raises hand, waits for turn (if turn management is active), starts speaking, sends the text for TTS synthesis, and marks finished.

```
kutana_speak(meeting_id="...", text="I think we should prioritize the API redesign.")
```

### Manual

For finer control, use the turn management tools directly:

1. `kutana_raise_hand(meeting_id, topic="API priorities")`
2. Wait for `turn.your_turn` event
3. `kutana_start_speaking(meeting_id)`
4. `kutana_speak(meeting_id, text="...")` (one or more times)
5. `kutana_mark_finished_speaking(meeting_id)`

## Voice selection

By default, each agent is assigned a voice from the pool. To use a specific voice, pass `tts_voice_id` when joining:

```python
kutana_join_meeting(
    meeting_id="...",
    capabilities=["tts_enabled"],
    tts_voice_id="a0e99841-438c-4a64-b679-ae501e7d6091"  # Cartesia voice ID
)
```

Voice IDs depend on the configured TTS provider. Check your provider's documentation for available voices.

## Capabilities reference

| Capability | Effect |
|------------|--------|
| `text_only` | Default. Receive transcript, send/receive chat. No audio. |
| `tts_enabled` | Agent's `kutana_speak` text is synthesized and broadcast as audio. |
| `voice` | Bidirectional raw PCM16 audio via the sidecar WebSocket (advanced). |

TTS is the recommended path for most agents. The `voice` capability is for agents that process or generate raw audio.

## Character budget

Each TTS session has a per-session character budget (default: 100,000 characters). If the budget is exhausted, subsequent `kutana_speak` calls will return an error. The budget resets when the agent leaves and rejoins.
