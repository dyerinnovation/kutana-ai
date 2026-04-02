# Phase C: Claude Code Channel Server — Implementation Plan

## Objective
Create `services/channel-server/` — a TypeScript MCP server that bridges Kutana AI's internal
message bus to Claude Code's channel protocol. Claude Code connects to this server as an MCP
client and receives live meeting events (transcript segments, extracted entities) as channel
notifications. It can also take action via MCP tools.

## Directory: `services/channel-server/`

## Architecture

```
services/channel-server/
├── package.json               # @modelcontextprotocol/sdk, ws; devDeps: typescript, @types/*, vitest
├── tsconfig.json              # strict mode, ES2022, bundler resolution (Bun-compatible)
├── .mcp.json                  # MCP server registration for Claude Code
├── src/
│   ├── types.ts               # TypeScript types (mirrors Python kutana-core types)
│   ├── config.ts              # Config from env vars (CONVENE_API_URL, API_KEY, etc.)
│   ├── kutana-client.ts      # WebSocket client → agent gateway (auth, join, listen)
│   ├── tools.ts               # MCP tools: reply, accept_task, update_status, etc.
│   ├── resources.ts           # MCP resources: platform context, meeting context
│   └── server.ts              # Main MCP server: claude/channel capability, notifications
├── tests/
│   ├── server.test.ts         # Server initialization, capability declaration
│   ├── tools.test.ts          # Tool schemas and handlers with mock client
│   ├── resources.test.ts      # Resource registration and content
│   └── event-forwarding.test.ts  # KutanaClient event filtering by agent mode
└── .claude-plugin/
    └── manifest.json          # Plugin distribution manifest
```

## Connection Flow
1. Claude Code starts channel-server via `bun src/server.ts`
2. Server declares `claude/channel` capability in MCP initialize response
3. Server connects to Kutana agent gateway (WebSocket) using API key → JWT exchange
4. Server sends `join_meeting` for the configured meeting ID
5. Incoming `transcript` + `event/data.channel.insights` messages → `notifications/message`
6. Claude receives notifications as channel context
7. Claude calls MCP tools (`reply`, `accept_task`, etc.) for two-way communication

## Context Seeding (Three Layers)
- **Layer 1 (Platform context)**: MCP `instructions` field + `kutana://platform/context` resource
- **Layer 2 (Meeting context)**: `kutana://meeting/{id}/context` resource template
- **Layer 3 (Recap)**: `get_meeting_recap` tool + buffered entity history

## Agent Modes
| Mode | What gets forwarded |
|------|---------------------|
| `transcript` | Transcript segments only |
| `insights` | Extracted entities only |
| `both` | Both transcript + entities |
| `selective` | Entities matching `CONVENE_ENTITY_FILTER` only |

## Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `CONVENE_API_URL` | `ws://localhost:8003` | Agent gateway WebSocket URL |
| `CONVENE_HTTP_URL` | `http://localhost:8000` | API server HTTP URL (for auth) |
| `CONVENE_API_KEY` | (required) | Agent API key |
| `CONVENE_MEETING_ID` | (required) | Meeting UUID to join |
| `CONVENE_AGENT_MODE` | `both` | `transcript\|insights\|both\|selective` |
| `CONVENE_ENTITY_FILTER` | `` | Comma-separated entity types for selective mode |

## MCP Tools
| Tool | Description |
|------|-------------|
| `reply` | Send text to meeting chat |
| `accept_task` | Claim an extracted task by ID |
| `update_status` | Push progress update for a task |
| `request_context` | Keyword search over transcript buffer |
| `get_meeting_recap` | Build recap from entity buffer |
| `get_entity_history` | Fetch entities by type from buffer |

## MCP Resources
| URI | Description |
|-----|-------------|
| `kutana://platform/context` | Static platform context document |
| `kutana://meeting/{meeting_id}/context` | Dynamic per-meeting context |

## Recovery Notes (if Claude disconnects)
- Recreate `services/channel-server/` directory
- Follow architecture above: types → config → kutana-client → tools → resources → server
- Key protocol: WebSocket to `{CONVENE_API_URL}/agent/connect?token={jwt}`, send `join_meeting`
- Tools use `server.setRequestHandler(ListToolsRequestSchema/CallToolRequestSchema, ...)`
- Resources use `server.setRequestHandler(ListResourcesRequestSchema/ReadResourceRequestSchema, ...)`
- Channel notifications via `server.notification({ method: "notifications/message", params: { level: "info", logger: "convene/{topic}", data: content } })`
- Type-check: `bun run tsc --noEmit`; Tests: `bun run vitest`
