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

**Phase 3** — Meeting Platform. LiveKit WebRTC integration, browser meeting room with video tiles, screen sharing, video layout modes (gallery/speaker/presentation), and real-time collaboration sidebar.

**Agent connection pattern:** Claude Agent SDK → MCP Server (Bearer token) → Agent Gateway (WebSocket).

See `internal-docs/development/TASKLIST.md` for the full task queue and `internal-docs/strategy/roadmap.md` for feature details.

## Strategy
- **LLM:** Anthropic Claude only. Haiku for extraction, Sonnet for recaps/dialogue, Opus for premium. See `internal-docs/strategy/cost-architecture.md`.
- **STT:** Deepgram Nova-2 (primary, all tiers). Self-hosted faster-whisper is Enterprise-only. See `internal-docs/strategy/cost-architecture.md`.
- **Billing:** Stripe. Free / Pro ($29) / Business ($79) / Enterprise (custom). See `internal-docs/strategy/cost-architecture.md`.

## Package Implementation Details
- `internal-docs/architecture/patterns/convene-core.md` — models, events, interfaces, database
- `internal-docs/architecture/patterns/provider-patterns.md` — ABC signatures, library conventions, registry
- `internal-docs/architecture/patterns/message-bus.md` — MessageBus ABC, Redis Streams, MockMessageBus
- `internal-docs/architecture/patterns/memory-architecture.md` — four-layer memory system, ORM-to-domain patterns
- `internal-docs/architecture/patterns/service-patterns.md` — health endpoints, lifespan, settings, DI, route organization
- `internal-docs/architecture/patterns/auth-and-api-keys.md` — JWT auth, API key system, token exchange
- `internal-docs/architecture/patterns/mcp-server.md` — MCP tools, Streamable HTTP transport, Docker setup
- `internal-docs/architecture/patterns/uv-best-practices.md` — uv workspace patterns, testing commands, pitfalls
- `internal-docs/architecture/patterns/pythonpath-workaround.md` — macOS UF_HIDDEN / .pth file workaround

## Agent Platform & Integrations
- `external-docs/agent-platform/overview.md` — three-tier agent architecture
- `external-docs/agent-platform/connecting/mcp-auth.md` — MCP OAuth 2.1 authorization flow
- `internal-docs/infrastructure/agent-context-seeding.md` — platform/meeting/recap context layers
- `external-docs/openclaw/plugin-guide.md` — OpenClaw plugin integration
- `external-docs/agent-platform/connecting/claude-agent-sdk.md` — Claude Agent SDK setup
- `external-docs/agent-platform/connecting/claude-code-channel.md` — Claude Code channel connection
- `external-docs/agent-platform/connecting/cli.md` — Convene CLI reference
- `examples/meeting-assistant-agent/` — Claude Agent SDK example with 4 templates

## Infrastructure & Tooling
- `internal-docs/architecture/patterns/dgx-spark-reference.md` — DGX hardware, K8s patterns, deployment gotchas
- `internal-docs/architecture/patterns/dgx-spark-ssh.md` — SSH patterns, sudo, PATH, containerd
- `charts/stt/` — Whisper STT Helm chart on DGX Spark

## Test Data & QA
- `data/input/` — sample audio files (`librispeech_sample.flac`, `test-speech.wav`)
- `internal-docs/testing/milestone-playbooks/` — per-feature QA playbooks (00-SETUP through 10-full-e2e-demo)
- `internal-docs/testing/manual/e2e-gateway-test.md` — gateway + STT integration walkthrough

## CoWork Coordination
- `internal-docs/development/TASKLIST.md` — ordered task queue (supports `🔗 BLOCK:` multi-task items)
- `internal-docs/development/cowork-tasks/` — scheduled task instructions
- `internal-docs/development/cowork-setup.md` — full CoWork setup documentation
- **Phase change rule:** update all three: `internal-docs/development/TASKLIST.md`, `CLAUDE.md`, `external-docs/README.md`

## TASKLIST Lock Protocol
- **Starting work:** Add 🔒 to the item to prevent other sessions from picking it up
- **Finishing work:** Replace `- [ ] 🔒` with `- [x]` (lock removed)
- **Only the session that locked an item should unlock it** — if you see 🔒 you didn't place, skip it
- **Milestone items (🏁)** are verification checkpoints — check off only when prerequisites pass
