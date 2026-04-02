# Claude Code Channel Plugin Architecture

> Design reference for the Claude Code channel plugin — how Claude Code connects to a
> Kutana meeting as a first-class participant via the MCP server, channel protocol,
> and capability declaration. Covers tool prefix, start_speaking flow, voice + TTS
> integration, and developer onboarding.

---

## Overview

The Claude Code channel plugin allows a Claude Code session to join a Kutana AI meeting and
participate as a named agent: receiving transcript events, sending chat messages, raising a hand
to speak, and optionally generating TTS speech. It is built on the same MCP tools used by all
agents — Claude Code is just another MCP client.

The plugin ships as a Kutana AI **skill** (`kutana-meeting`) and is pre-configured in the
`~/.claude/` settings via the MCP server URL and API key.

---

## Connection Architecture

```
Claude Code Session
        │
        │  MCP protocol (Streamable HTTP)
        │  GET /mcp  (SSE)
        │  POST /mcp (tool calls)
        ▼
kutana-mcp-server  (port 3001, or /mcp on K3s ingress)
        │
        ├── REST API calls ──────────► api-server (port 8000)
        │                                    │
        │                                    ▼
        │                              PostgreSQL + Redis
        │
        └── WebSocket ─────────────► agent-gateway (port 8003)
                                            │
                                            ├── TurnManager
                                            ├── ChatStore
                                            └── Redis Streams
```

The MCP server is the single point of entry. Claude Code never talks directly to the agent
gateway — the MCP server proxies gateway operations and buffers events so Claude Code can poll
them via `kutana_get_meeting_events`.

---

## MCP Server Configuration

### Claude Code settings.json

```json
{
  "mcpServers": {
    "kutana": {
      "type": "http",
      "url": "http://kutana.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer ${CONVENE_API_KEY}"
      }
    }
  }
}
```

For local development:

```json
{
  "mcpServers": {
    "kutana": {
      "type": "http",
      "url": "http://localhost:3001/mcp",
      "headers": {
        "Authorization": "Bearer ${CONVENE_API_KEY}"
      }
    }
  }
}
```

The `CONVENE_API_KEY` environment variable must be set in the shell where Claude Code launches.

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `CONVENE_API_KEY` | Workspace API key from dashboard | `cvn_live_abc123...` |
| `CONVENE_MCP_URL` | MCP server URL (optional override) | `http://localhost:3001/mcp` |

---

## Tool Prefix: `kutana_`

All Kutana MCP tools use the `kutana_` prefix to prevent name collisions when Claude Code has
multiple MCP servers configured simultaneously.

| Tool | Description |
|------|-------------|
| `kutana_list_meetings` | List upcoming and active meetings |
| `kutana_join_meeting` | Join a meeting as Claude Code |
| `kutana_leave_meeting` | Disconnect from a meeting |
| `kutana_get_meeting_status` | Get comprehensive meeting state |
| `kutana_get_transcript` | Read recent transcript segments |
| `kutana_get_tasks` | Retrieve extracted tasks |
| `kutana_create_task` | Create a task from the meeting |
| `kutana_get_participants` | List current participants |
| `kutana_raise_hand` | Request to speak |
| `kutana_get_queue_status` | Check speaker queue |
| `kutana_get_speaking_status` | Check if Claude Code is active speaker |
| `kutana_mark_finished_speaking` | Signal done speaking |
| `kutana_cancel_hand_raise` | Withdraw from the queue |
| `kutana_send_chat_message` | Post a message to meeting chat |
| `kutana_get_chat_messages` | Read chat history |
| `kutana_start_speaking` | Speak to the meeting (text → TTS or voice) |
| `kutana_subscribe_channel` | Subscribe to a named data channel |
| `kutana_publish_to_channel` | Publish data to a channel |
| `kutana_get_channel_messages` | Read buffered channel messages |
| `kutana_get_meeting_events` | Poll buffered meeting events |

---

## Capability Declaration on Join

Claude Code declares its capabilities when calling `kutana_join_meeting`. The gateway uses
this to configure audio routing and event filtering for the session.

```python
# Claude Code joins as text_only by default
result = await mcp.call_tool("kutana_join_meeting", {
    "meeting_id": "abc123",
    "display_name": "Claude Code",
    "source": "claude-code",
    "audio_capability": "text_only"   # no audio sidecar
})

# With TTS enabled — Claude Code can speak via synthesized voice
result = await mcp.call_tool("kutana_join_meeting", {
    "meeting_id": "abc123",
    "display_name": "Claude Code",
    "source": "claude-code",
    "audio_capability": "tts_enabled",
    "tts_voice_id": "a0e99841-438c-4a64-b679-ae501e7d6091"  # optional
})
```

### Capability Values

| Capability | What Claude Code receives | What Claude Code can do |
|------------|--------------------------|-------------------------|
| `text_only` | Transcript feed via poll | Chat, tasks, turn management |
| `tts_enabled` | Transcript feed via poll | Chat + synthesized speech |

Claude Code does not support `voice_in`, `voice_out`, or `voice_bidirectional` — those require
a binary WebSocket audio sidecar that Claude Code's MCP transport does not provide. TTS is the
correct voice mechanism for Claude Code.

The `source: "claude-code"` field is propagated in participant events so that other participants
can distinguish Claude Code from other agent types.

---

## start_speaking Flow (TTS)

When Claude Code wants to address the meeting room:

```
Claude Code
    │
    │── kutana_raise_hand ──────────────────────────► MCP Server ──► TurnManager
    │◄── {position: 1, status: "queued"} ─────────────────────────────────────────
    │
    │  [polls kutana_get_meeting_events until speaker.changed event]
    │
    │── kutana_get_meeting_events ──────────────────► MCP Server
    │◄── [{type: "speaker.changed", speaker: "claude-code"}]
    │
    │── kutana_start_speaking ──────────────────────► MCP Server
    │   {meeting_id: "...", text: "Here are the action items..."}
    │                                                       │
    │                                               ──► TTS Provider
    │                                               ──► AudioRouter (mix into room)
    │                                               ──► mark_finished_speaking (auto)
    │
    │◄── {status: "done"} ──────────────────────────────────────────────────────────
```

### Example: Claude Code Speaks in a Meeting

```
User: "Join the Q1 planning meeting and share the action items."

Claude Code:
1. kutana_list_meetings → finds "Q1 Planning"
2. kutana_join_meeting(meeting_id, audio_capability="tts_enabled")
3. kutana_get_transcript → reads recent context
4. kutana_raise_hand → queued at position 1
5. [polls] kutana_get_meeting_events → receives speaker.changed
6. kutana_start_speaking(text="I've reviewed the transcript. Here are 3 action items: ...")
7. kutana_leave_meeting
```

---

## Event Buffering (Poll Model)

Claude Code uses a poll-based model (not persistent WebSocket) because MCP Streamable HTTP
doesn't maintain long-lived connections between tool calls. The gateway buffers events in Redis
and Claude Code polls via `kutana_get_meeting_events`.

### Buffer Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| Buffer duration | 5 minutes | Events older than this are dropped |
| Max events per poll | 50 | Prevents overwhelming the context window |
| Event types buffered | `speaker.*`, `participant.*`, `chat.message.received`, `channel.*` | Configurable |

### kutana_get_meeting_events

```json
{
  "name": "kutana_get_meeting_events",
  "description": "Poll for buffered meeting events since a given cursor. Returns events in chronological order.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "meeting_id": {"type": "string"},
      "since_cursor": {
        "type": "string",
        "description": "Redis Streams cursor (e.g., '0' for all, or last-seen event ID)"
      },
      "event_types": {
        "type": "array",
        "items": {"type": "string"},
        "description": "Filter to specific event types. Omit for all."
      }
    },
    "required": ["meeting_id"]
  }
}
```

---

## Channel Protocol

Claude Code can participate in named data channels within a meeting. Channels are scoped to a
meeting and can carry arbitrary JSON payloads.

### Subscribe

```python
# Subscribe to the "tasks" channel
await mcp.call_tool("kutana_subscribe_channel", {
    "meeting_id": "abc123",
    "channel": "tasks"
})
```

### Publish

```python
# Publish to the "tasks" channel
await mcp.call_tool("kutana_publish_to_channel", {
    "meeting_id": "abc123",
    "channel": "tasks",
    "payload": {"action": "created", "task": {"description": "Follow up by Friday"}}
})
```

### Read Buffered Messages

```python
messages = await mcp.call_tool("kutana_get_channel_messages", {
    "meeting_id": "abc123",
    "channel": "tasks",
    "since_cursor": "0"
})
```

---

## Developer Onboarding Flow

### Step 1: Get an API Key

1. Sign in at `kutana.spark-b0f2.local` (or your Kutana instance)
2. Go to **Settings → API Keys**
3. Click **Generate Key** — select scope "Agent" with the meetings you want to access
4. Copy the key

### Step 2: Configure Claude Code

```bash
# Add to your shell profile
export CONVENE_API_KEY="cvn_live_..."
```

Then add the MCP server to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "kutana": {
      "type": "http",
      "url": "http://kutana.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer ${CONVENE_API_KEY}"
      }
    }
  }
}
```

Restart Claude Code. Verify the connection:

```
> /mcp
Connected servers: kutana (20 tools available)
```

### Step 3: Join Your First Meeting

```
User: "List available meetings."

Claude Code: [calls kutana_list_meetings]
Found 2 meetings:
- "Q1 Planning" (active, 3 participants)
- "Weekly Standup" (scheduled in 10 minutes)

User: "Join Q1 Planning and listen. Let me know when action items come up."

Claude Code: [calls kutana_join_meeting, subscribes to transcript events]
Joined "Q1 Planning". I'll monitor the transcript and flag action items.
```

### Step 4: Enable TTS (Optional)

To give Claude Code a voice in meetings:

1. Go to **Settings → Agents → Claude Code**
2. Under **Voice**, select a TTS voice (or leave as default)
3. Update your `kutana_join_meeting` call to include `"audio_capability": "tts_enabled"`

---

## Kutana Meeting Skill (OpenClaw / ClawHub)

The `kutana-meeting` skill wraps all of the above into an OpenClaw-compatible package.
See `docs/research/skill-architecture.md` for the full design.

The skill file at `integrations/kutana-meeting-skill/SKILL.md` provides:
- Natural language guidance for agents on when and how to use each tool
- Connection setup instructions
- Example agent prompts
- Troubleshooting section

Claude Code agents that load this skill get extended context about Kutana participation norms
(e.g., "always raise your hand before speaking", "keep chat messages to 2-3 sentences").

---

## Integration Guide for Other Plugins

Any MCP-compatible tool or plugin can integrate with Kutana using the same pattern:

1. Configure the Kutana MCP server URL in your tool settings
2. Use Bearer token auth with a Kutana API key
3. Call `kutana_join_meeting` with appropriate `audio_capability`
4. Use `kutana_` prefixed tools for all meeting interactions
5. Call `kutana_leave_meeting` on cleanup

For OpenClaw plugins specifically, set `mcp_compatible: true` in your skill frontmatter and
reference the MCP server URL as `"${CONVENE_MCP_URL:-http://localhost:3001/mcp}"`.

---

## Related Files

- `services/mcp-server/` — MCP server implementation and tool definitions
- `integrations/kutana-meeting-skill/` — OpenClaw skill package
- `docs/integrations/CLAUDE_AGENT_SDK.md` — Claude Agent SDK setup guide
- `docs/integrations/OPENCLAW.md` — OpenClaw plugin integration
- `docs/research/voice-agent-integration.md` — Voice sidecar for voice-capable agents
- `docs/research/tts-text-agents.md` — TTS pipeline and provider details
- `docs/research/skill-architecture.md` — Skill design and capability mapping
