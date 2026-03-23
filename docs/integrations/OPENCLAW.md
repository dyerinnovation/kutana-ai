# OpenClaw Integration Guide

## Overview

The Convene AI OpenClaw plugin (`@convene/openclaw-plugin`) gives OpenClaw agents native access to Convene meeting tools. Install the plugin and agents can join meetings, read transcripts, manage turns, chat, and create tasks from any OpenClaw channel (Slack, WhatsApp, etc.).

## Installation

```bash
openclaw plugins install @convene/openclaw-plugin
```

## Configuration

In your OpenClaw `config.yaml`:

```yaml
plugins:
  entries:
    convene:
      config:
        apiKey: "cvn_..."          # Convene API key
        mcpUrl: "https://convene.spark-b0f2.local/mcp"  # MCP server URL
```

## Available Tools

### Meeting Management

| Tool | Description |
|------|-------------|
| `convene_list_meetings` | List available meetings |
| `convene_join_meeting` | Join a meeting by ID (optional: `capabilities` array) |
| `convene_get_transcript` | Get recent transcript segments |
| `convene_create_task` | Create a task from meeting context |
| `convene_get_participants` | List meeting participants |
| `convene_create_meeting` | Create a new meeting |

### Turn Management

| Tool | Description |
|------|-------------|
| `convene_raise_hand` | Request a turn to speak (enters queue) |
| `convene_start_speaking` | Confirm you have the floor and are speaking |
| `convene_mark_finished_speaking` | Release the floor, advance queue |
| `convene_get_queue_status` | See who is speaking and who is waiting |
| `convene_cancel_hand_raise` | Withdraw from the speaker queue |

### Chat

| Tool | Description |
|------|-------------|
| `convene_send_chat_message` | Send a message to meeting chat |
| `convene_get_chat_messages` | Get chat history with optional type filter |

## Turn Workflow

```
convene_raise_hand(meeting_id, topic="...")
  → queue_position=0: floor is yours immediately
  → queue_position>0: wait for turn_your_turn event

convene_start_speaking(meeting_id)        → confirm you have the floor
[speak or send messages]
convene_mark_finished_speaking(meeting_id) → release floor
```

## Capabilities

Pass `capabilities` to `convene_join_meeting` to control what the agent can do:

| Capability | Effect |
|---|---|
| `listen` | Receive transcript (default) |
| `transcribe` | Buffer transcript segments (default) |
| `text_only` | No audio processing |
| `voice` | Full audio input/output |
| `tts_enabled` | Text-to-speech output |

## Skill

The plugin includes a SKILL.md that teaches agents when and how to use the tools:

```
skills/convene/SKILL.md
```

The skill is automatically available to OpenClaw agents when the plugin is installed.

## Architecture

```
OpenClaw Agent (Slack/WhatsApp/etc.)
    │
    │  Native tool calls
    ▼
@convene/openclaw-plugin
    │
    │  HTTP + Bearer token
    ▼
Convene MCP Server (https://convene.spark-b0f2.local/mcp)
    │
    │  API calls + WebSocket
    ▼
Convene API Server + Agent Gateway
```

## Example Usage

In Slack:
```
User: @agent join the standup meeting and tell me what's being discussed
Agent: [calls convene_list_meetings, convene_join_meeting, convene_get_transcript]
Agent: Here's what's being discussed in the standup...

User: @agent raise your hand to ask about the deployment timeline
Agent: [calls convene_raise_hand with topic="deployment timeline"]
Agent: I've raised my hand. Queue position: 2. Waiting for my turn...
Agent: [receives turn_your_turn event, calls convene_start_speaking]
Agent: I now have the floor...
```

## Development

The plugin source is at `integrations/openclaw-plugin/`:

```
integrations/openclaw-plugin/
├── openclaw.plugin.json    # Plugin manifest
├── package.json            # Node.js project
├── src/
│   ├── index.ts           # Plugin entry, registers 13 tools
│   └── convene-client.ts  # HTTP client for MCP/API
└── skills/
    └── convene/
        └── SKILL.md       # Agent instructions
```

Build and test:
```bash
cd integrations/openclaw-plugin
npm install
npm run build
npm test
```
