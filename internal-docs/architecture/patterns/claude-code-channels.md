# Claude Code Channels — Architecture & Implementation

> The Kutana channel plugin is **implemented and shipping**. It is a single stdio MCP server that provides both tools and real-time push events.

---

## What Are Claude Code Channels?

Claude Code Channels are **stdio-transport MCP servers** spawned as subprocesses by Claude Code. Unlike standard MCP servers (which Claude Code calls on demand), a channel declares the `claude/channel` capability and **pushes** events into the session via `notifications/claude/channel` messages.

Official first-party channel plugins exist for Telegram, Discord, and iMessage. The Kutana channel plugin follows the same pattern.

A channel must:

1. Use **stdio transport** (spawned as a child process, not HTTP).
2. Declare **`experimental: { 'claude/channel': {} }`** during initialization.
3. Emit **`notifications/claude/channel`** JSON-RPC notifications with `{ content, meta }` params.

Events arrive in Claude's context as `<channel source="server-name" attr="val">content</channel>` XML tags.

---

## Protocol Details

### Transport

Channels use **stdio** (stdin/stdout), not HTTP. Claude Code spawns the channel binary as a subprocess.

```
Claude Code (parent)
    │
    ├── stdin  ──► Channel Plugin (child process)
    └── stdout ◄── Channel Plugin (child process)
```

### Capability Declaration

During MCP initialization, the channel server declares the `claude/channel` capability under `experimental`:

```typescript
const server = new Server(
  { name: 'kutana-ai', version: '0.2.0' },
  {
    capabilities: {
      tools: {},
      resources: { subscribe: true, listChanged: true },
      experimental: { 'claude/channel': {} },
    },
    instructions: 'Events from the kutana-ai channel arrive as <channel source="kutana-ai" ...>.',
  },
)
```

### Event Emission

The channel pushes events as JSON-RPC notifications:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/claude/channel",
  "params": {
    "content": "[2.0s-4.5s] Alice: We should finalize the API spec by Thursday.",
    "meta": {
      "topic": "transcript",
      "type": "transcript_segment"
    }
  }
}
```

Claude Code renders this as:

```xml
<channel source="kutana-ai" topic="transcript" type="transcript_segment">
[2.0s-4.5s] Alice: We should finalize the API spec by Thursday.
</channel>
```

The `source` attribute comes from the server's `name` field. The `meta` keys become additional tag attributes.

---

## Kutana Implementation

### Architecture

The channel plugin is a **single stdio MCP server** (TypeScript, runs with Bun) that handles both tools and push events:

```
Claude Code
    │
    └── stdio MCP ──→ Kutana Channel Plugin (bun)
                          │
                          ├── HTTP (fetch) ──→ API Server   (list/create meetings)
                          └── WebSocket    ──→ Agent Gateway (join, events, chat, turn)
```

### Lifecycle

1. **Startup** — Plugin authenticates with the API (API key → JWT). Tools and resources are registered. No meeting joined yet.
2. **Discovery** — User calls `list_meetings` or browses `kutana://meeting/{id}` resources.
3. **Join** — User calls `join_meeting` → WebSocket opens → events push via `notifications/claude/channel`.
4. **Active** — All 18 tools available. Transcript, chat, turn, and insight events flow as `<channel>` tags.
5. **Leave** — User calls `leave_meeting` → WebSocket closes, buffers clear.

### Configuration

Register the MCP server using the Claude Code CLI:

```bash
claude mcp add-json --scope user kutana '{
  "type": "stdio",
  "command": "bun",
  "args": ["/path/to/services/channel-server/src/server.ts"],
  "env": {
    "KUTANA_API_KEY": "cvn_...",
    "KUTANA_API_URL": "wss://kutana.spark-b0f2.local/ws",
    "KUTANA_HTTP_URL": "https://kutana.spark-b0f2.local",
    "KUTANA_TLS_REJECT_UNAUTHORIZED": "0"
  }
}'
```

**Important:** The server must be registered via `claude mcp add-json` (not manually in `~/.claude/settings.json`). The `--dangerously-load-development-channels` flag looks up servers from the `claude mcp` managed registry — manual `settings.json` entries are invisible to it.

Then launch Claude Code with the channel enabled:

```bash
claude --dangerously-load-development-channels server:kutana
```

`server:kutana` references the server registered with `claude mcp add-json`. This flag is required during the research preview for custom (non-plugin) channels — without it, tools load but push events (`notifications/claude/channel`) are silently dropped. Published plugins use `--channels plugin:name@publisher` instead.

No `KUTANA_MEETING_ID` needed — meetings are joined dynamically via tools.

### Event Mapping

| Gateway Event | Channel Topic | Channel Type |
|--------------|---------------|--------------|
| `transcript` | `transcript` | `transcript_segment` |
| `data.channel.insights.*` | `insight` | Entity type (task, decision, etc.) |
| `data.channel.chat` | `chat` | `chat_message` |
| `turn.queue.updated` | `turn` | `queue_updated` |
| `turn.speaker.changed` | `turn` | `speaker_changed` |
| `turn.your_turn` | `turn` | `your_turn` |
| `participant_update` | `participant` | `joined` / `left` |

### Tools (18 total)

**Lobby tools** (no meeting required): `list_meetings`, `join_meeting`, `create_meeting`, `join_or_create_meeting`

**Meeting tools** (require active meeting): `leave_meeting`, `reply`, `get_chat_messages`, `accept_task`, `update_status`, `raise_hand`, `get_queue_status`, `mark_finished_speaking`, `cancel_hand_raise`, `get_speaking_status`, `get_participants`, `request_context`, `get_meeting_recap`, `get_entity_history`

### Resources

| URI | Description |
|-----|-------------|
| `kutana://platform/context` | Static platform context |
| `kutana://meeting/{id}` | Meeting info + connection status |
| `kutana://meeting/{id}/context` | Detailed context with transcript preview |
| `kutana://meeting/{id}/transcript` | Buffered transcript (JSON) |

### Source Code

```
services/channel-server/
├── src/
│   ├── server.ts           # MCP server entry, channel notification forwarding
│   ├── kutana-client.ts   # WebSocket client: auth, join, leave, HTTP API
│   ├── config.ts           # Environment variable loading
│   ├── types.ts            # TypeScript types (mirrors Python domain models)
│   ├── tools.ts            # 18 MCP tools with meeting-active guards
│   └── resources.ts        # MCP resources with listChanged notifications
├── tests/                  # 71 tests (vitest)
└── package.json            # Bun runtime, @modelcontextprotocol/sdk
```

---

## Technical Notes

- **stdio vs HTTP:** The channel plugin uses stdio because it runs as a subprocess. The separate HTTP MCP server (`services/mcp-server/`) remains available for remote agents that can't run a local process.
- **Auth:** The plugin reads `KUTANA_API_KEY` from env and exchanges it for a gateway JWT via `POST /api/v1/token/gateway`. The gateway JWT is used for WebSocket connections. For HTTP API calls (list/create meetings), the plugin sends the raw API key via `X-API-Key` header — the meetings endpoints accept both Bearer JWT (browser users) and X-API-Key (agents) via the `CurrentUserOrAgent` dependency.
- **TLS:** Self-signed certs are common in dev. Set `KUTANA_TLS_REJECT_UNAUTHORIZED=0` (default) to accept them. The plugin sets `NODE_TLS_REJECT_UNAUTHORIZED=0` at startup.
- **MCP registration:** The server must be registered via `claude mcp add-json` (managed registry), not manually in `~/.claude/settings.json`. The `--dangerously-load-development-channels` flag only finds servers in the managed registry.
- **Research preview:** Custom channels require `--dangerously-load-development-channels server:kutana` at launch. This bypasses the channel allowlist (which only includes published Anthropic plugins like Discord, Telegram). This flag may be removed or renamed when channels graduate from preview.
- **Reconnection:** Not yet implemented. If the WebSocket drops, use `leave_meeting` + `join_meeting` to reconnect. Missed events can be recovered via the HTTP MCP server's `kutana_get_meeting_events`.

---

## References

- External setup guide: `external-docs/connecting-agents/custom-agents/claude-code-channel.md`
- Claude Code channels docs: https://code.claude.com/docs/en/channels
- Claude Code channels reference: https://code.claude.com/docs/en/channels-reference
- MCP server architecture: `internal-docs/architecture/patterns/mcp-server.md`
- Agent gateway protocol: `internal-docs/architecture/patterns/agent-gateway.md`
- Auth and API keys: `internal-docs/architecture/patterns/auth-and-api-keys.md`
