# OpenClaw Integration

Connect your OpenClaw agents to Convene AI meetings. Once installed, any OpenClaw agent can list meetings, join as a participant, read the live transcript, manage turns, send chat messages, and create tasks — from any channel OpenClaw supports (Slack, WhatsApp, Discord, and more).

## Prerequisites

- OpenClaw 0.9 or later
- A Convene API key (see [Get an API key](#get-an-api-key) below)

## Get an API key

1. Sign in to your Convene instance
2. Go to **Settings → API Keys**
3. Click **Generate Key** — select the **Agent** scope
4. Copy the key (it starts with `cvn_`)

## Install

```bash
openclaw plugins install @convene/openclaw-plugin
```

## Configure

Add the plugin to your OpenClaw `config.yaml`:

```yaml
plugins:
  entries:
    convene:
      config:
        apiKey: "cvn_..."                              # your Convene API key
        mcpUrl: "http://convene.spark-b0f2.local/mcp" # your Convene instance URL
```

## Available Tools

### Meeting Management

| Tool | Description |
|------|-------------|
| `convene_list_meetings` | List available meetings |
| `convene_create_meeting` | Create a new meeting |
| `convene_join_meeting` | Join a meeting by ID |
| `convene_leave_meeting` | Leave the current meeting |
| `convene_get_transcript` | Get recent transcript segments |
| `convene_get_participants` | List meeting participants |
| `convene_create_task` | Create a task from meeting context |

### Turn Management

| Tool | Description |
|------|-------------|
| `convene_raise_hand` | Request a turn to speak |
| `convene_get_queue_status` | See who is speaking and who is waiting |
| `convene_start_speaking` | Confirm you have the floor |
| `convene_mark_finished_speaking` | Release the floor and advance the queue |
| `convene_cancel_hand_raise` | Withdraw from the speaker queue |

### Chat

| Tool | Description |
|------|-------------|
| `convene_send_chat_message` | Send a message to meeting chat |
| `convene_get_chat_messages` | Get chat history (filterable by type) |

## Turn Workflow

To speak in a meeting:

```
1. convene_raise_hand(topic="your topic")
      → queue_position: 0  →  floor is yours immediately
      → queue_position: N  →  wait for speaker.changed event

2. convene_get_queue_status()   # poll until it's your turn

3. convene_start_speaking(text="What I want to say...")
                                # text is synthesized to voice via TTS

4. convene_mark_finished_speaking()   # release the floor
```

## Capabilities

Pass a `capabilities` array to `convene_join_meeting` to control what the agent can do:

| Capability | Effect |
|------------|--------|
| `text_only` | Transcript and chat only — no audio processing (default) |
| `tts_enabled` | Agent can speak via text-to-speech |

## Example Conversation

In Slack:

```
User:  @agent join the standup and tell me what's being discussed

Agent: [calls convene_list_meetings → convene_join_meeting → convene_get_transcript]
       Here's what's being discussed in the standup: the team is reviewing
       the Q2 roadmap. Sarah is presenting deployment timelines...

User:  @agent raise your hand to ask about the API rollout

Agent: [calls convene_raise_hand(topic="API rollout timeline")]
       I've raised my hand. Queue position: 2. Waiting for my turn...

       [polls convene_get_queue_status until it's their turn]
       I now have the floor.

       [calls convene_start_speaking(text="What is the target date for the API rollout?")]
       Asked the question. Releasing the floor.
```

## Plugin Source

The plugin source lives at `integrations/openclaw-plugin/`:

```
integrations/openclaw-plugin/
├── openclaw.plugin.json    # Plugin manifest
├── package.json            # Node.js project (18+)
├── src/
│   ├── index.ts           # Registers 13 tools
│   └── convene-client.ts  # HTTP client (Bearer token, JSON-RPC 2.0)
└── skills/
    └── convene/
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
OpenClaw Agent (Slack / WhatsApp / Discord / ...)
        │
        │  Native tool calls
        ▼
@convene/openclaw-plugin
        │
        │  HTTP + Bearer token (JSON-RPC 2.0)
        ▼
Convene MCP Server  (http://convene.spark-b0f2.local/mcp)
        │
        ├── REST API ──────► API Server
        └── WebSocket ─────► Agent Gateway
```

## See Also

- [Claude Code Channel](claude-code-channel.md) — Connect a Claude Code session to a meeting
- [Claude Agent SDK](claude-agent-sdk.md) — Build autonomous agents with the Claude Agent SDK
- [CLI](cli.md) — Terminal-based API access
