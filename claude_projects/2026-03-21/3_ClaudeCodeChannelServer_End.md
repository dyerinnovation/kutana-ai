# Phase C: Claude Code Channel Server — Completion Summary

## Work Completed

- **`services/channel-server/`** — new TypeScript service directory, Bun-compatible

- **`src/types.ts`** — TypeScript types mirroring Python kutana-core models: 7 entity types
  (`TaskEntity`, `DecisionEntity`, `QuestionEntity`, `EntityMentionEntity`, `KeyPointEntity`,
  `BlockerEntity`, `FollowUpEntity`) plus `AnyExtractedEntity` union, `TranscriptSegment`,
  `GatewayMessage`, `ChannelMessage`, `AgentMode`, `EntityType`.

- **`src/config.ts`** — `ChannelServerConfig` interface and `loadConfig()` reading from env vars
  (`CONVENE_API_URL`, `CONVENE_HTTP_URL`, `CONVENE_API_KEY`, `CONVENE_MEETING_ID`,
  `CONVENE_AGENT_MODE`, `CONVENE_ENTITY_FILTER`). HTTP URL derived from WS URL (port 8003→8000).

- **`src/kutana-client.ts`** — `KutanaClient` WebSocket client:
  - Authenticates via `POST /api/v1/token/gateway` with `X-API-Key`
  - Connects to `{API_URL}/agent/connect?token={jwt}`
  - Sends `join_meeting` on WS open; subscribes to 9 insight data channels
  - Routes `transcript` / `event/data.channel.insights` messages to registered callback
  - 4 agent modes: `transcript`, `insights`, `both`, `selective` (with entity filter)
  - `sendChatMessage()`, `acceptTask()`, `updateTaskStatus()` for two-way communication
  - `getRecentTranscript()` / `getEntities()` buffer accessors
  - Injectable `WebSocketConstructor` for test isolation

- **`src/tools.ts`** — 6 MCP tools registered via `server.setRequestHandler`:
  - `reply` — send text to meeting chat
  - `accept_task` — claim a task by ID
  - `update_status` — report task progress
  - `request_context` — keyword search over transcript buffer
  - `get_meeting_recap` — build structured recap from entity buffer
  - `get_entity_history` — retrieve entities by type

- **`src/resources.ts`** — MCP resources + `PLATFORM_CONTEXT_DOC` (Layer 1 context):
  - `kutana://platform/context` — static markdown explaining the platform, message formats, tools
  - `kutana://meeting/{meeting_id}/context` — dynamic context: connection status, agent mode, entity
    counts, and 5-segment transcript preview

- **`src/server.ts`** — Main MCP server:
  - `createServer()` factory exported for tests
  - `claude/channel` declared in capabilities (type-extended `ServerCapabilities`)
  - `instructions` field passed via spread into `Server` options (MCP 2024-11-05+)
  - Kutana events → `notifications/message` (level=info, logger=`convene/{topic}`)
  - `isEntryPoint` guard using `(import.meta as unknown as { main?: boolean }).main`
    to prevent `main()` running when imported by Vitest
  - Graceful shutdown on SIGINT/SIGTERM

- **`package.json`** — `@modelcontextprotocol/sdk@^1.0.0` (installed 1.27.1), `ws@^8.18.0`;
  `bun install` confirmed working

- **`tsconfig.json`** — strict mode, ES2022, bundler moduleResolution (Bun-compatible)

- **`.mcp.json`** — MCP server registration for Claude Code

- **`.claude-plugin/manifest.json`** — plugin distribution manifest

- **`tests/` — 52 tests, 4 files, all passing (vitest 2.1.9)**:
  - `server.test.ts` — `createServer()` returns server/client, initial state, callback wiring
  - `tools.test.ts` — all 6 tools: listing, schema validation, handler behaviour, error cases
  - `resources.test.ts` — resource listing, template listing, platform context, dynamic context
  - `event-forwarding.test.ts` — all 4 agent modes, entity filtering, message formatting

## Work Remaining

- None for this phase.
- Potential future enhancements:
  - Wire the channel server to an actual running meeting (E2E test)
  - Support recap burst on late-join (Layer 3 context seeding)
  - Add reconnect/backoff logic if the gateway drops mid-meeting
  - Implement `claude/channel/message` custom notification if Claude Code channel spec differs
    from `notifications/message` (one-line change in `server.ts`)

## Lessons Learned

- **`_requestHandlers` is private in MCP SDK** — tests must access via
  `(server as any)._requestHandlers.get(methodName)`. The public API only exposes
  `setRequestHandler`; handler retrieval requires a cast. Confirmed with `bun -e` REPL.

- **MockWebSocket instance capture** — when injecting a WebSocket constructor for tests,
  the KutanaClient creates a NEW instance internally. The test must use a capturing pattern
  (`let lastMockWs; class MockWS { constructor() { lastMockWs = this; } }`) to get a reference
  to the actual instance driven by the client, not a separate one created by the test.

- **`import.meta.main` for Bun entry-point guard** — Bun sets `import.meta.main = true` when
  the file is executed directly. Use `(import.meta as unknown as { main?: boolean }).main ?? false`
  to prevent `main()` running under Vitest (which doesn't set this). Without the guard, Vitest
  importing `server.ts` will trigger `process.exit(1)` and cause all tests to fail.

- **`instructions` in MCP SDK 1.27.1** — the `Server` constructor doesn't list `instructions`
  in its TypeScript interface, but the underlying protocol includes it in `InitializeResult`.
  Passing it via spread (`...({ instructions: PLATFORM_INSTRUCTIONS } as object)`) works at
  runtime in MCP 2024-11-05+ servers. The SDK stores it in `this._instructions`.

- **`server.notification()` for channel events** — standard `notifications/message` with
  `level: "info"` and `logger: "convene/{topic}"` is the reliable, spec-compliant way to push
  channel context. The `claude/channel` capability declaration signals intent to Claude Code.
