# Claude Code Channel Setup Guide

Connect Claude Code to Kutana meetings as a first-class participant. Claude Code joins via a local channel plugin that pushes real-time events (transcript, chat, speaker changes, extracted insights) directly into your conversation.

## Prerequisites

- **Claude Code** (latest version)
- **Bun** runtime v1.0+ ([bun.sh](https://bun.sh))
- A **Kutana API key** with Agent scope

## Step 1: Get an API Key

1. Sign in to your Kutana instance (e.g., `https://dev.kutana.ai`)
2. Navigate to **Settings > API Keys**
3. Click **Generate Key** — select the **Agent** scope
4. Copy the key immediately (starts with `cvn_`, shown only once)

## Step 2: Install the Channel Plugin

```bash
cd /path/to/kutana-ai/services/channel-server
bun install
```

## Step 3: Register the MCP Server

```bash
claude mcp add-json --scope user kutana '{
  "type": "stdio",
  "command": "bun",
  "args": ["/path/to/kutana-ai/services/channel-server/src/server.ts"],
  "env": {
    "KUTANA_API_KEY": "cvn_your_key_here",
    "KUTANA_URL": "https://dev.kutana.ai",
    "KUTANA_AGENT_NAME": "Claude Code"
  }
}'
```

Replace `/path/to/kutana-ai` with your actual repo path. `--scope user` makes this available across all projects.

## Step 4: Launch with Channel Enabled

```bash
claude --dangerously-load-development-channels server:kutana
```

> **Note:** The `--dangerously-load-development-channels` flag is required during the research preview for custom channels. Published plugins use `--channels plugin:name@publisher` instead.

## Step 5: Verify

Run `/mcp` inside Claude Code. You should see `kutana` listed with tools available.

## Your First Meeting

```
You:          What meetings are available?
Claude Code:  [calls kutana_list_meetings]
              Found 2 meetings:
              - "Daily Standup" (active)
              - "Sprint Planning" (scheduled)

You:          Join the Daily Standup.
Claude Code:  [calls kutana_join_meeting]
              Joined. Receiving real-time transcript and events.
```

Once joined, transcript and chat arrive automatically as `<channel>` tags:

```xml
<channel source="kutana-ai" topic="transcript">
[2.0s-4.5s] Alice: Let's review the API changes.
</channel>
```

Claude reads these and can respond — sending chat messages, raising a hand, claiming tasks, or speaking via TTS.

## Environment Variables

| Variable | Required | Default | Description |
|----------|:--------:|---------|-------------|
| `KUTANA_API_KEY` | Yes | — | Agent API key (`cvn_...`) |
| `KUTANA_URL` | No | — | Base URL (derives HTTP and WebSocket URLs) |
| `KUTANA_API_URL` | No | From `KUTANA_URL` | WebSocket URL override |
| `KUTANA_HTTP_URL` | No | From `KUTANA_URL` | HTTP API URL override |
| `KUTANA_AGENT_NAME` | No | `Claude Code` | Display name in meetings |
| `KUTANA_AGENT_MODE` | No | `both` | Event filter: `transcript`, `insights`, `both`, `selective` |
| `KUTANA_ENTITY_FILTER` | No | — | Entity types for `selective` mode (comma-separated) |
| `KUTANA_TLS_REJECT_UNAUTHORIZED` | No | `0` | Set `1` to enforce TLS cert validation |

## Available Tools

### Meeting Lifecycle

| Tool | Description |
|------|-------------|
| `kutana_list_meetings` | List available meetings |
| `kutana_join_meeting` | Join a meeting — starts receiving real-time events |
| `kutana_create_meeting` | Create a new meeting |
| `kutana_join_or_create_meeting` | Find or create a meeting by title |
| `kutana_leave_meeting` | Leave the current meeting |

### Chat & Speaking

| Tool | Description |
|------|-------------|
| `kutana_reply` | Send a chat message |
| `kutana_speak` | Speak via TTS (text-to-speech) |
| `kutana_get_chat_messages` | Read recent chat history |

### Turn Management

| Tool | Description |
|------|-------------|
| `kutana_raise_hand` | Request a turn to speak |
| `kutana_get_queue_status` | Check the speaker queue |
| `kutana_get_speaking_status` | Check your speaking/queue status |
| `kutana_mark_finished_speaking` | Release the floor |
| `kutana_cancel_hand_raise` | Withdraw from the queue |

### Tasks & Context

| Tool | Description |
|------|-------------|
| `kutana_accept_task` | Claim an extracted task |
| `kutana_update_status` | Push a task status update |
| `kutana_get_participants` | List meeting participants |
| `kutana_request_context` | Search transcript for a topic |
| `kutana_get_meeting_recap` | Get tasks, decisions, key points |
| `kutana_get_entity_history` | Retrieve entities by type |

## Real-Time Events

| Topic | Description |
|-------|-------------|
| `transcript` | Speech-to-text segments |
| `chat` | Chat messages from participants |
| `insight` | Extracted entities (tasks, decisions, questions) |
| `turn` | Speaker queue changes, your-turn notifications |
| `participant` | Join/leave events |
| `meeting_lifecycle` | Meeting state changes |

## Capabilities

Pass a `capabilities` array when joining to control what the agent can do:

```
kutana_join_meeting(meeting_id="...", capabilities=["tts_enabled"])
```

| Capability | Effect |
|------------|--------|
| `text_only` | Default. Receive transcript, send/receive chat. No audio. |
| `tts_enabled` | Agent can speak via `kutana_speak` — text is synthesized and broadcast. |

| `voice` | Bidirectional raw PCM16 audio via the sidecar WebSocket (advanced). |

> **Most agents should use `text_only` or `tts_enabled`.** The `voice` capability is for agents that process or generate raw audio. See the [Voice Agent Quickstart](./VOICE_AGENT_QUICKSTART.md).

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `kutana` not in `/mcp` output | Save settings and restart Claude Code |
| `401 Unauthorized` | Re-export `KUTANA_API_KEY` or regenerate |
| No real-time events | Ensure `--dangerously-load-development-channels server:kutana` flag is set |
| Agent not in participant grid | Check agent-gateway is running (`kubectl logs -n kutana deploy/agent-gateway`) |

## See Also

- [MCP Quickstart](/docs/connecting-agents/custom-agents/mcp-quickstart) — Connect any MCP-compatible agent
- [TTS Agent Quickstart](/docs/integrations/TTS_AGENT_QUICKSTART.md) — Text-to-speech agents
- [Voice Agent Quickstart](/docs/integrations/VOICE_AGENT_QUICKSTART.md) — Raw audio agents
