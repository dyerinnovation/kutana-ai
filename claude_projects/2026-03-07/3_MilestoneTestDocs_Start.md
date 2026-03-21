# Milestone Testing Documentation — Start

## Date: 2026-03-07

## Objective
Create per-feature manual test playbooks in `docs/milestone-testing/` for all 16 features implemented during the 2026-03-07 sprint. Each doc walks through end-to-end testing with exact commands, expected outputs, and verification checklists.

## Files to Create

| File | Feature |
|------|---------|
| `00-SETUP.md` | Shared prerequisites and infrastructure startup |
| `01-meeting-lifecycle.md` | Create → Start → Join → End (API + UI) |
| `02-browser-meeting-room.md` | Mic capture, WebSocket, live transcripts |
| `03-mcp-auth-flow.md` | API key → MCP JWT → Bearer auth |
| `04-convene-cli.md` | All CLI commands end-to-end |
| `05-api-key-security.md` | Expiry, rate limiting, audit log |
| `06-openclaw-plugin.md` | Build, install, tool calls |
| `07-claude-agent-sdk.md` | 4 agent templates against live meeting |
| `08-prebuilt-agent-templates-ui.md` | Browse/activate/deactivate in dashboard |
| `09-channel-routing.md` | Two agents, subscribe/publish channels |
| `10-full-e2e-demo.md` | Run demo_meeting_flow.py, verify all 13 steps |

## Approach
1. Research all key source files (routes, MCP tools, CLI commands, frontend pages)
2. Cross-reference with demo script and existing E2E test doc for style
3. Write each doc following the established pattern: Purpose → Prerequisites → Steps → Verification → Troubleshooting → Cleanup
4. Ensure curl commands use verified endpoint paths from source code

## Key Source Files Referenced
- `services/api-server/src/api_server/main.py` — FastAPI app, all router prefixes
- `services/api-server/src/api_server/routes/meetings.py` — Meeting CRUD + lifecycle
- `services/api-server/src/api_server/routes/token.py` — Token exchange (gateway, MCP, meeting)
- `services/api-server/src/api_server/routes/agent_keys.py` — API key management
- `services/api-server/src/api_server/routes/agent_templates.py` — Template browsing/activation
- `services/api-server/src/api_server/rate_limit.py` — Redis-based rate limiting
- `services/mcp-server/src/mcp_server/main.py` — 11 MCP tools
- `services/mcp-server/src/mcp_server/auth.py` — JWT validation
- `services/cli/src/convene_cli/main.py` — Typer CLI commands
- `services/agent-gateway/src/agent_gateway/event_relay.py` — Channel routing
- `scripts/demo_meeting_flow.py` — 13-step E2E demo
- `web/src/pages/MeetingRoomPage.tsx` — Browser meeting room
- `web/src/pages/MeetingsPage.tsx` — Meeting list/create UI
- `web/src/pages/AgentTemplatePage.tsx` — Template dashboard
- `integrations/openclaw-plugin/src/index.ts` — OpenClaw plugin tools
- `examples/meeting-assistant-agent/agent.py` — Agent SDK templates
