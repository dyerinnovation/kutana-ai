# Milestone Testing Documentation — End

## Date: 2026-03-07

## Work Completed

- Created `docs/milestone-testing/00-SETUP.md` — Shared infrastructure setup (deps, docker, migrations, 4 services, user/agent/key creation)
- Created `docs/milestone-testing/01-meeting-lifecycle.md` — Full CRUD + state machine (Part A: API with 10 curl commands, Part B: UI walkthrough)
- Created `docs/milestone-testing/02-browser-meeting-room.md` — Mic capture, WebSocket audio, live transcripts, mute/unmute, participants
- Created `docs/milestone-testing/03-mcp-auth-flow.md` — API key → MCP JWT → Bearer chain, JWT claim decode, revocation, invalid token 401s
- Created `docs/milestone-testing/04-kutana-cli.md` — All Typer CLI commands: login, status, agents create/list, meetings create/list, keys generate, logout
- Created `docs/milestone-testing/05-api-key-security.md` — 4 parts: expiry (5s TTL), revocation, rate limiting (60/min → 429), audit log queries
- Created `docs/milestone-testing/06-openclaw-plugin.md` — Build, install in OpenClaw, test all 6 tools, error handling
- Created `docs/milestone-testing/07-claude-agent-sdk.md` — 4 templates (assistant/summarizer/action-tracker/decision-logger), custom prompt, Claude Desktop/Code config
- Created `docs/milestone-testing/08-prebuilt-agent-templates-ui.md` — Template grid, category filters, activate modal, hosted sessions, deactivation
- Created `docs/milestone-testing/09-channel-routing.md` — Two agents, subscribe/publish, channel isolation, multi-channel subscription
- Created `docs/milestone-testing/10-full-e2e-demo.md` — 13-step demo script, DB/Redis verification, silence test, alternative audio
- Created `claude_projects/2026-03-07/3_MilestoneTestDocs_Start.md` — Plan documentation

## Work Remaining

- **Live verification:** Walk through `00-SETUP.md` startup commands against running services
- **Curl validation:** Run `01-meeting-lifecycle.md` Part A curl commands against live API
- **Demo validation:** Run `10-full-e2e-demo.md` demo script to verify it still works
- **Endpoint cross-check:** Spot-check curl commands against route source files for correctness
- **Template seeding:** Verify agent templates are seeded in DB (if not, docs 08 may need seed script reference)

## Lessons Learned

- **API route prefix structure:** All routes mount under `/api/v1/` in `main.py`. Agent keys are nested under `/api/v1/agents/{agent_id}/keys` despite having a separate router
- **Rate limiting requires Redis:** Rate limit middleware degrades gracefully (allows all requests) when Redis is unavailable — testing must verify Redis is running first
- **MCP server transport:** Uses Streamable HTTP at `/mcp` endpoint (not SSE), with JSON-RPC 2.0 protocol for tool calls
- **Audio format:** Browser room captures at 16kHz mono with ScriptProcessorNode (4096 samples), converts Float32 to Int16 PCM, base64-encodes. Demo script uses 16000-byte chunks
- **JWT structure:** MCP tokens include `type: "mcp"` claim, gateway tokens include `type: "gateway"`. Both validated with HS256 against `AGENT_GATEWAY_JWT_SECRET`
- **Channel routing filter logic:** `data.channel.*` events are filtered by agent subscription list in `EventRelay._should_relay`. Other event types (transcript, meeting, room) route to all qualifying agents
- **CLI uses Typer + Rich:** Output is formatted with Rich tables and panels. Terminal must support Unicode
- **OpenClaw plugin uses lazy auth:** Authenticates on first tool call, not at plugin load time
