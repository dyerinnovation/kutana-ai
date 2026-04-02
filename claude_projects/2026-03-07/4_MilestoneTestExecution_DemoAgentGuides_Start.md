# Milestone Test Execution + Demo Agent Guides

## Objective
Execute all 11 milestone testing playbooks (00-SETUP through 10-full-e2e-demo) and then create a `demo-agents/` folder with setup + connection guides for three agent frameworks (OpenClaw, Claude Agent SDK, OpenAI Agents SDK).

## Part 1: Execute Milestone Tests (Phases 0-10)
- Phase 0: Setup (install deps, start infra, configure env, register user/agent/key)
- Phase 1: Meeting Lifecycle (CRUD + state machine, UI testing)
- Phase 2: Browser Meeting Room (mic capture, transcripts, mute/unmute)
- Phase 3: MCP Auth Flow (token exchange, JWT claims, revocation)
- Phase 4: Kutana CLI (all commands end-to-end)
- Phase 5: API Key Security (expiry, revocation, rate limiting, audit log)
- Phase 6: OpenClaw Plugin (build, install, test 6 tools)
- Phase 7: Claude Agent SDK (4 templates, custom prompt, alt model)
- Phase 8: Prebuilt Templates UI (API + browser testing)
- Phase 9: Channel Routing (multi-agent pub/sub, isolation)
- Phase 10: Full E2E Demo (demo_meeting_flow.py, DB/Redis verification)

## Part 2: Build Demo Agent Guides (Phases 11-13)
- Phase 11: OpenClaw guide (SETUP_OPENCLAW.md + README.md)
- Phase 12: Claude Agent SDK guide (SETUP_CLAUDE_SDK.md + agent.py + README.md)
- Phase 13: OpenAI Agents SDK guide (SETUP_OPENAI_SDK.md + agent.py + README.md)

## Human Intervention Required
- Phase 1.B: Browser UI testing
- Phase 2.2-8: Browser meeting room (mic, transcripts)
- Phase 6.3, 6.5-11: OpenClaw desktop app
- Phase 7.1: ANTHROPIC_API_KEY
- Phase 8.4-6: Template UI in browser
- Phase 13: OPENAI_API_KEY

## Status
- Starting Phase 0 (Setup)...
