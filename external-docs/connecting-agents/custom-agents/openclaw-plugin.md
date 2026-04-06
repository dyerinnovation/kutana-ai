# OpenClaw Integration

Connect your OpenClaw agents to Kutana AI meetings. Once installed, any OpenClaw agent can list meetings, join as a participant, read the live transcript, manage turns, send chat messages, and create tasks.

## Prerequisites

- OpenClaw 0.9 or later
- A Kutana API key (see [Get an API key](#get-an-api-key) below)

## Get an API key

1. Sign in to your Kutana instance
2. Go to **Settings → API Keys**
3. Click **Generate Key** — select the **Agent** scope
4. Copy the key (it starts with `cvn_`)

## Install

```bash
openclaw plugins install @kutana/openclaw-plugin
```

## Configure

Add the plugin to your OpenClaw `config.yaml`:

```yaml
plugins:
  entries:
    kutana:
      config:
        apiKey: "cvn_..."                              # your Kutana API key
        mcpUrl: "https://kutana.spark-b0f2.local/mcp"  # your Kutana instance URL
```

## Available Tools

### Meeting Management

| Tool | Description |
|------|-------------|
| `kutana_list_meetings` | List available meetings |
| `kutana_create_meeting` | Create a new meeting |
| `kutana_join_meeting` | Join a meeting by ID |
| `kutana_leave_meeting` | Leave the current meeting |
| `kutana_get_transcript` | Get recent transcript segments |
| `kutana_get_participants` | List meeting participants |
| `kutana_create_task` | Create a task from meeting context |
| `kutana_get_meeting_status` | Get comprehensive meeting state |

### Turn Management

| Tool | Description |
|------|-------------|
| `kutana_raise_hand` | Request a turn to speak |
| `kutana_get_queue_status` | See who is speaking and who is waiting |
| `kutana_start_speaking` | Confirm you have the floor |
| `kutana_speak` | Speak text in the meeting (handles turn management and TTS) |
| `kutana_mark_finished_speaking` | Release the floor and advance the queue |
| `kutana_cancel_hand_raise` | Withdraw from the speaker queue |
| `kutana_get_speaking_status` | Check if you are currently the active speaker |

### Chat

| Tool | Description |
|------|-------------|
| `kutana_send_chat_message` | Send a message to meeting chat |
| `kutana_get_chat_messages` | Get chat history (filterable by type) |

## Turn Workflow

To speak in a meeting:

```
1. kutana_raise_hand(topic="your topic")
      → queue_position: 0  →  floor is yours immediately
      → queue_position: N  →  wait, poll kutana_get_queue_status

2. kutana_start_speaking(meeting_id)

3. kutana_speak(meeting_id, text="What I want to say...")
                                # text is synthesized to voice via TTS

4. kutana_mark_finished_speaking(meeting_id)   # release the floor
```

## Capabilities

Pass a `capabilities` array to `kutana_join_meeting` to control what the agent can do:

| Capability | Effect |
|------------|--------|
| `text_only` | Transcript and chat only — no audio processing (default) |
| `voice_in` | Receive audio input |
| `voice_out` | Send audio output |
| `voice_bidirectional` | Full audio input and output |
| `tts_enabled` | Agent can speak via text-to-speech |

## Example Conversation

```
User:  @agent join the standup and tell me what's being discussed

Agent: [calls kutana_list_meetings → kutana_join_meeting → kutana_get_transcript]
       Here's what's being discussed in the standup: the team is reviewing
       the Q2 roadmap. Sarah is presenting deployment timelines...

User:  @agent raise your hand to ask about the API rollout

Agent: [calls kutana_raise_hand(topic="API rollout timeline")]
       I've raised my hand. Queue position: 2. Waiting for my turn...

       [polls kutana_get_queue_status until it's their turn]
       I now have the floor.

       [calls kutana_speak(text="What is the target date for the API rollout?")]
       Asked the question. Releasing the floor.
```

## Plugin Source

The plugin source lives at `integrations/openclaw-plugin/`:

```
integrations/openclaw-plugin/
├── openclaw.plugin.json    # Plugin manifest
├── package.json            # Node.js project (18+)
├── src/
│   ├── index.ts           # Registers 17 tools
│   └── kutana-client.ts   # HTTP client (Bearer token, JSON-RPC 2.0)
└── skills/
    └── kutana/
        └── SKILL.md       # Natural language guidance for agents
```

The included `SKILL.md` teaches OpenClaw agents when and how to use each tool — it loads automatically when the plugin is installed.

Build from source:

```bash
cd integrations/openclaw-plugin
npm install
npm run build
```

## Architecture

```
OpenClaw Agent
        │
        │  Native tool calls
        ▼
@kutana/openclaw-plugin
        │
        │  HTTP + Bearer token (JSON-RPC 2.0)
        ▼
Kutana MCP Server  (https://kutana.spark-b0f2.local/mcp)
        │
        ├── REST API ──────► API Server
        └── WebSocket ─────► Agent Gateway
```

## See Also

- [Claude Code Channel](claude-code-channel.md) — Connect a Claude Code session to a meeting
- [Claude Agent SDK](claude-agent-sdk.md) — Build autonomous agents with the Claude Agent SDK
- [CLI](cli.md) — Terminal-based API access
