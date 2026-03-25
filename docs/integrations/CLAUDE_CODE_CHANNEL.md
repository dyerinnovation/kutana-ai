# Claude Code Channel

Connect a Claude Code session to a Convene AI meeting as a first-class participant. Claude Code joins via the MCP server, receives the live transcript, can raise its hand to speak (with TTS), post chat messages, create tasks, and coordinate with other agents over named data channels.

Claude Code is just another MCP client — it uses the same tools as every other agent.

## Prerequisites

- Claude Code (latest version)
- A Convene API key (see [Get an API key](#get-an-api-key))

## Get an API key

1. Sign in to your Convene instance
2. Go to **Settings → API Keys**
3. Click **Generate Key** — select the **Agent** scope
4. Copy the key (it starts with `cvn_`)

## Configure Claude Code

### 1. Set the environment variable

Add to your shell profile (`~/.zshrc`, `~/.bashrc`, etc.):

```bash
export CONVENE_API_KEY="cvn_..."
```

Reload your shell or open a new terminal, then verify:

```bash
echo $CONVENE_API_KEY
```

### 2. Add the MCP server to Claude Code

Edit `~/.claude/settings.json` and add the `convene` entry under `mcpServers`:

```json
{
  "mcpServers": {
    "convene": {
      "type": "http",
      "url": "http://convene.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer ${CONVENE_API_KEY}"
      }
    }
  }
}
```

### 3. Verify the connection

Restart Claude Code, then run:

```
/mcp
```

You should see `convene` listed with 20+ tools available.

## Join your first meeting

```
You:          List available meetings.

Claude Code:  [calls convene_list_meetings]
              Found 2 meetings:
              • "Q1 Planning" — active, 4 participants
              • "Weekly Standup" — scheduled in 15 minutes

You:          Join Q1 Planning and monitor for action items.

Claude Code:  [calls convene_join_meeting]
              Joined "Q1 Planning". I'll monitor the transcript and flag
              action items as they come up.
```

## Available Tools

All tools use the `convene_` prefix to avoid collisions when multiple MCP servers are active.

### Meeting

| Tool | Description |
|------|-------------|
| `convene_list_meetings` | List upcoming and active meetings |
| `convene_create_meeting` | Create a new meeting |
| `convene_join_meeting` | Join a meeting as Claude Code |
| `convene_leave_meeting` | Disconnect from a meeting |
| `convene_start_meeting` | Start a scheduled meeting |
| `convene_end_meeting` | End an active meeting |
| `convene_join_or_create_meeting` | Join an active meeting or create one |

### Transcript & Tasks

| Tool | Description |
|------|-------------|
| `convene_get_transcript` | Read recent transcript segments |
| `convene_get_tasks` | List tasks for a meeting |
| `convene_create_task` | Create a task from meeting context |
| `convene_get_participants` | List current participants |

### Turn Management

| Tool | Description |
|------|-------------|
| `convene_raise_hand` | Request to speak (enters speaker queue) |
| `convene_get_queue_status` | Check who is speaking and what's queued |
| `convene_start_speaking` | Speak to the room — text is synthesized via TTS |
| `convene_mark_finished_speaking` | Release the floor |
| `convene_cancel_hand_raise` | Withdraw from the queue |

### Chat

| Tool | Description |
|------|-------------|
| `convene_send_chat_message` | Post a message to meeting chat |
| `convene_get_chat_messages` | Read chat history |

### Events & Channels

| Tool | Description |
|------|-------------|
| `convene_get_meeting_events` | Poll buffered meeting events (turns, participants, chat) |
| `convene_subscribe_channel` | Subscribe to a named data channel |
| `convene_publish_to_channel` | Publish a payload to a channel |
| `convene_get_channel_messages` | Read buffered channel messages |

## Capabilities

Declare capabilities when calling `convene_join_meeting`:

| Capability | What Claude Code receives | What Claude Code can do |
|------------|--------------------------|-------------------------|
| `text_only` | Transcript via poll | Chat, tasks, turn queue (default) |
| `tts_enabled` | Transcript via poll | Chat + synthesized speech |

Claude Code does not support `voice_in` or `voice_out` — those require a persistent audio sidecar that MCP Streamable HTTP doesn't provide. Use `tts_enabled` when you want Claude Code to speak.

```
convene_join_meeting(meeting_id="abc123", audio_capability="tts_enabled")
```

## Speaking in a meeting (TTS)

When Claude Code wants to address the room:

```
1.  convene_raise_hand(topic="action item summary")
        → returns queue position

2.  convene_get_meeting_events(event_types=["speaker.changed"])
        → poll until Claude Code becomes the active speaker

3.  convene_start_speaking(text="Here are the three action items I noted...")
        → text is routed to the TTS provider and mixed into the room audio
        → floor is released automatically when done
```

Full example:

```
You:          Join the Q1 Planning meeting and share the action items you've found.

Claude Code:
  1. convene_list_meetings → finds "Q1 Planning"
  2. convene_join_meeting(audio_capability="tts_enabled")
  3. convene_get_transcript → reads recent context
  4. convene_raise_hand(topic="action item summary")
  5. [polls] convene_get_meeting_events → receives speaker.changed
  6. convene_start_speaking(text="I've reviewed the last 10 minutes. Here are
     the action items: (1) Alex to finalize the API spec by Thursday,
     (2) Sarah to schedule the infrastructure review...")
  7. convene_leave_meeting
```

## Event polling

Claude Code uses a poll model — MCP Streamable HTTP doesn't maintain long-lived connections between tool calls. The MCP server buffers events in Redis; poll them with `convene_get_meeting_events`.

| Parameter | Default | Notes |
|-----------|---------|-------|
| Buffer window | 5 minutes | Events older than this are dropped |
| Max per poll | 50 events | Prevents context overflow |
| Event types | `speaker.*`, `participant.*`, `chat.message.received`, `channel.*` | Filterable |

Pass `event_types` to filter:

```
convene_get_meeting_events(event_types=["speaker.changed", "participant.joined"])
```

## Channel protocol

Named data channels let multiple agents coordinate within a meeting. Any agent can subscribe, publish, and read from a channel scoped to the meeting.

```
# Subscribe
convene_subscribe_channel(channel="tasks")

# Publish structured data
convene_publish_to_channel(channel="tasks", payload={
    "action": "created",
    "task": {"description": "Follow up with Alex by Friday", "priority": "high"}
})

# Read buffered messages
convene_get_channel_messages(channel="tasks", last_n=20)
```

Use channels to coordinate between a Claude Code session and autonomous agents — for example, a Claude Code session publishes extracted tasks and a background agent picks them up and assigns owners.

## Architecture

```
Claude Code Session
        │
        │  MCP Streamable HTTP
        │  POST /mcp  (tool calls)
        ▼
Convene MCP Server  (http://convene.spark-b0f2.local/mcp)
        │
        ├── REST API ───────────► API Server + PostgreSQL
        └── WebSocket ──────────► Agent Gateway + Redis Streams
```

The MCP server is the single point of entry. Claude Code never talks directly to the agent gateway — the MCP server proxies gateway operations and buffers events so Claude Code can poll them.

## See Also

- [OpenClaw Integration](./OPENCLAW.md) — Connect via OpenClaw channels
- [Claude Agent SDK](./CLAUDE_AGENT_SDK.md) — Build autonomous Python agents
- [CLI](./CLI.md) — Terminal-based access
