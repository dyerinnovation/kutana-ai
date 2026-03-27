# Claude Code Channels — Spec & Convene Integration Plan

> Claude Code Channels (shipped March 20, 2026) are MCP servers that push events into a running Claude Code session. They complement the existing pull-based MCP server by enabling real-time, event-driven interaction.

---

## What Are Claude Code Channels?

Claude Code Channels are **stdio-transport MCP servers** spawned as subprocesses by Claude Code. Unlike standard MCP servers (which Claude Code calls on demand), a channel declares the `claude/channel` capability and **pushes** events into the session via `notifications/claude/channel` messages.

Official first-party channel plugins exist for Telegram, Discord, and iMessage. Any MCP server can become a channel by:

1. Using **stdio transport** (spawned as a child process, not HTTP).
2. Declaring the **`claude/channel` capability** during initialization.
3. Emitting **`notifications/claude/channel`** JSON-RPC notifications whenever an event occurs.

When Claude Code receives a channel notification, it treats the payload as new context — similar to a user message — and can respond, call tools, or take action autonomously.

---

## Protocol Details

### Transport

Channels use **stdio** (stdin/stdout), not HTTP. Claude Code spawns the channel binary as a subprocess and communicates over JSON-RPC 2.0 on stdio.

```
Claude Code (parent)
    │
    ├── stdin  ──► Channel Plugin (child process)
    └── stdout ◄── Channel Plugin (child process)
```

### Capability Declaration

During MCP initialization, the channel server includes `claude/channel` in its capabilities response:

```json
{
  "capabilities": {
    "claude/channel": {}
  }
}
```

### Event Emission

The channel pushes events as JSON-RPC notifications (no `id` field, no response expected):

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/claude/channel",
  "params": {
    "channel": "convene",
    "event": "transcript.segment",
    "data": {
      "speaker": "Alice",
      "text": "We should finalize the API spec by Thursday.",
      "timestamp": "2026-03-26T14:32:01Z"
    }
  }
}
```

Claude Code receives this as inline context and can act on it — e.g., call `convene_create_task` via the MCP server.

---

## Convene Integration Architecture

### Current State: MCP Server (Pull Model)

Claude Code connects to `http://convene.spark-b0f2.local/mcp` over MCP Streamable HTTP. It calls tools on demand (`convene_get_transcript`, `convene_get_meeting_events`, etc.) and polls for new events.

```
Claude Code
    │
    │  MCP Streamable HTTP (pull)
    │  POST /mcp
    ▼
Convene MCP Server ──► Agent Gateway ──► Redis Streams
```

**Limitation:** Claude Code must explicitly poll. Events are buffered in Redis for up to 5 minutes, but there is no push notification when something happens.

### Future State: Channel Plugin (Push Model)

A local **Convene Channel Plugin** runs as a stdio subprocess alongside Claude Code. It maintains a persistent WebSocket to the agent gateway and pushes meeting events into the Claude Code session in real time.

```
Claude Code
    │
    ├── MCP HTTP (pull) ──► Convene MCP Server ──► tools, transcripts, tasks
    │
    └── stdio (push) ◄── Convene Channel Plugin
                              │
                              └── WebSocket ──► Agent Gateway ──► Redis Streams
```

**Benefits:**
- **Instant awareness:** Claude Code learns about new transcript segments, speaker changes, chat messages, and task updates the moment they happen.
- **No polling overhead:** Eliminates the need for periodic `convene_get_meeting_events` calls.
- **Autonomous action:** Claude Code can react to events without being prompted — e.g., automatically flag action items as they are spoken.

### How They Work Together

| Concern | MCP Server (HTTP) | Channel Plugin (stdio) |
|---------|-------------------|----------------------|
| Transport | Streamable HTTP | stdio (subprocess) |
| Direction | Pull (Claude calls tools) | Push (plugin emits events) |
| Auth | Bearer token (JWT) | Local process — inherits env |
| Use case | Tool calls, data queries | Real-time event stream |
| Status | **Shipping today** | **Planned (Phase 2)** |

Both are MCP servers. Claude Code can use them simultaneously — the channel provides awareness, the MCP server provides action.

---

## Implementation Roadmap

### Phase 1: MCP Only (Current)

- Claude Code connects via `http://convene.spark-b0f2.local/mcp`.
- All interaction is pull-based: Claude Code calls tools, polls events.
- Event buffering in Redis (5 min window, 50 events per poll).
- This works today and covers all meeting participation use cases.

### Phase 2: Channel Plugin for Real-Time Push

**Deliverables:**

1. **`convene-channel` CLI binary** (Python, packaged via `uv`):
   - Reads `CONVENE_API_KEY` from environment.
   - Opens a WebSocket to the agent gateway (`wss://convene.spark-b0f2.local/v1/agent/connect`).
   - Joins a specified meeting (passed via CLI arg or env var).
   - Translates gateway WebSocket events into `notifications/claude/channel` on stdout.
   - Handles reconnection, heartbeat, and graceful shutdown.

2. **Claude Code configuration** (`~/.claude/settings.json`):
   ```json
   {
     "mcpServers": {
       "convene": {
         "type": "http",
         "url": "http://convene.spark-b0f2.local/mcp",
         "headers": {
           "Authorization": "Bearer ${CONVENE_API_KEY}"
         }
       },
       "convene-channel": {
         "type": "stdio",
         "command": "convene-channel",
         "args": ["--meeting", "${CONVENE_MEETING_ID}"],
         "env": {
           "CONVENE_API_KEY": "${CONVENE_API_KEY}"
         }
       }
     }
   }
   ```

3. **Event mapping** (gateway WebSocket events to channel notifications):

   | Gateway Event | Channel Notification |
   |--------------|---------------------|
   | `transcript.segment.final` | `transcript.segment` |
   | `speaker.changed` | `speaker.changed` |
   | `speaker.queue.updated` | `speaker.queue.updated` |
   | `chat.message.received` | `chat.message` |
   | `participant.joined` | `participant.joined` |
   | `participant.left` | `participant.left` |
   | `channel.*` | `data_channel.*` |
   | `task.created` | `task.created` |

4. **Tests:**
   - Unit tests for event translation.
   - Integration test: channel plugin connects to gateway, receives event, emits notification on stdout.
   - E2E test: Claude Code receives channel notification, calls MCP tool in response.

### Phase 3: Bi-Directional Channel (Future)

- Channel plugin accepts tool-call-like messages from Claude Code (not just notifications).
- Enables low-latency operations that bypass the HTTP round-trip.
- Requires MCP spec evolution (channels are currently notification-only).

---

## Technical Notes

- **stdio vs HTTP:** Channels must use stdio because they run as subprocesses. The existing MCP server remains HTTP because it is a shared remote service.
- **Auth boundary:** The channel plugin runs locally and inherits the user's env vars (including `CONVENE_API_KEY`). It authenticates to the gateway the same way any agent does.
- **mDNS resolution:** The channel plugin must use `aiohttp` (not `httpx`) for WebSocket connections to `*.local` hostnames. httpx hangs on IPv6/mDNS resolution. See memory note on this issue.
- **Reconnection:** The channel plugin should implement exponential backoff with jitter for WebSocket reconnection. Meeting events missed during disconnection can be recovered via `convene_get_meeting_events` on the MCP server side.
- **Resource usage:** The channel plugin is a lightweight Python process. It holds one WebSocket connection and emits JSON on stdout. Memory footprint should be under 50 MB.

---

## References

- External setup guide: `external-docs/agent-platform/connecting/claude-code-channel.md`
- MCP server architecture: `internal-docs/architecture/patterns/mcp-server.md`
- Agent gateway protocol: `internal-docs/architecture/patterns/agent-gateway.md`
- Auth and API keys: `internal-docs/architecture/patterns/auth-and-api-keys.md`
