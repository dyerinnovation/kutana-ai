# Convene AI

## Project Overview
Convene AI is an agent-first meeting platform where AI agents connect via native WebSocket API and humans join via browser WebRTC. Agents listen for commitments, extract tasks, and maintain persistent memory across meetings. The core insight: AI agents are first-class meeting participants, not bolted-on bots.

## Architecture
Python monorepo managed with `uv` workspaces.

### Packages (shared libraries)
- `packages/convene-core/` — Domain models (Pydantic v2), event definitions, abstract interfaces
- `packages/convene-providers/` — STT, TTS, and LLM provider implementations behind ABCs
- `packages/convene-memory/` — Four-layer memory system (working, short-term, long-term, structured)

### Services (independently runnable)
- `services/api-server/` — FastAPI REST + WebSocket API
- `services/audio-service/` — Transport-agnostic audio pipeline and STT streaming
- `services/agent-gateway/` — WebSocket gateway for AI agent connections
- `services/mcp-server/` — MCP server exposing Convene tools for Claude and MCP clients
- `services/task-engine/` — Redis Streams consumer, LLM-powered task extraction
- `services/worker/` — Background jobs: notifications, Slack, calendar sync
- `services/cli/` — Convene CLI tool (typer-based)

### Frontend
- `web/` — React 19 + TypeScript + Vite + Tailwind v4

### Infrastructure
- PostgreSQL 16 + pgvector, Redis 7, LiveKit (WebRTC SFU), Stripe (billing)
- All services run on the **DGX Spark K3s cluster** — see `.claude/rules/dgx-connection.md`
- MessageBus is abstracted (Redis Streams by default) — never import a provider directly

## Current Phase
**Phase 1** — Core AI Pipeline (in progress). STT wired, Redis Streams consumer implemented. Next: transcript segment windowing → LLM extraction pipeline → task persistence.

**Phase 2** — Agent Platform (complete as of 2026-03-07). MCP OAuth 2.1 auth, meeting lifecycle, browser meeting room, prebuilt agent templates, CLI, OpenClaw plugin, Claude Code skill, channel routing, API key security.

**Agent connection pattern:** Claude Agent SDK → MCP Server (Bearer token) → Agent Gateway (WebSocket).

See `docs/TASKLIST.md` for the full task queue and `docs/technical/ROADMAP.md` for feature details.

## Strategy
- **LLM:** Anthropic Claude only. Haiku for extraction, Sonnet for recaps/dialogue, Opus for premium. See `docs/technical/cost-architecture.md`.
- **STT:** Deepgram Nova-2 (primary, all tiers). Self-hosted faster-whisper is Enterprise-only. See `docs/technical/cost-architecture.md`.
- **Billing:** Stripe. Free / Pro ($29) / Business ($79) / Enterprise (custom). See `docs/technical/cost-architecture.md`.

## Package Implementation Details
- `claude_docs/Convene_Core_Patterns.md` — models, events, interfaces, database
- `claude_docs/Provider_Patterns.md` — ABC signatures, library conventions, registry
- `claude_docs/MessageBus_Patterns.md` — MessageBus ABC, Redis Streams, MockMessageBus
- `claude_docs/Memory_Architecture.md` — four-layer memory system, ORM-to-domain patterns
- `claude_docs/Service_Patterns.md` — health endpoints, lifespan, settings, DI, route organization
- `claude_docs/Auth_And_API_Keys.md` — JWT auth, API key system, token exchange
- `claude_docs/MCP_Server_Architecture.md` — MCP tools, Streamable HTTP transport, Docker setup
- `claude_docs/UV_Best_Practices.md` — uv workspace patterns, testing commands, pitfalls
- `claude_docs/PYTHONPATH_Workaround.md` — macOS UF_HIDDEN / .pth file workaround

## Agent Platform & Integrations
- `docs/technical/AGENT_PLATFORM.md` — three-tier agent architecture and access matrix
- `docs/technical/MCP_AUTH.md` — MCP OAuth 2.1 authorization flow
- `docs/technical/agent-context-seeding.md` — platform/meeting/recap context layers
- `docs/integrations/OPENCLAW.md` — OpenClaw plugin integration
- `docs/integrations/CLAUDE_AGENT_SDK.md` — Claude Agent SDK setup
- `docs/integrations/CLI.md` — Convene CLI reference
- `examples/meeting-assistant-agent/` — Claude Agent SDK example with 4 templates

## Infrastructure & Tooling
- `claude_docs/DGX_Spark_Reference.md` — DGX hardware, K8s patterns, deployment gotchas
- `claude_docs/DGX_Spark_SSH_Connection.md` — SSH patterns, sudo, PATH, containerd
- `charts/stt/` — Whisper STT Helm chart on DGX Spark

## Test Data & QA
- `data/input/` — sample audio files (`librispeech_sample.flac`, `test-speech.wav`)
- `docs/milestone-testing/` — per-feature QA playbooks (00-SETUP through 10-full-e2e-demo)
- `docs/manual-testing/E2E_Gateway_Test.md` — gateway + STT integration walkthrough

## CoWork Coordination
- `docs/TASKLIST.md` — ordered task queue (supports `🔗 BLOCK:` multi-task items)
- `docs/cowork-tasks/` — scheduled task instructions
- `docs/SETUP_GUIDE.md` — full CoWork setup documentation
- **Phase change rule:** update all three: `docs/TASKLIST.md`, `CLAUDE.md`, `docs/README.md`

## TASKLIST Lock Protocol
- **Starting work:** Add 🔒 to the item to prevent other sessions from picking it up
- **Finishing work:** Replace `- [ ] 🔒` with `- [x]` (lock removed)
- **Only the session that locked an item should unlock it** — if you see 🔒 you didn't place, skip it
- **Milestone items (🏁)** are verification checkpoints — check off only when prerequisites pass
