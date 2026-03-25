# Convene AI — The Agent-First Meeting Platform

## What is Convene AI?

Convene is a meeting platform built from the ground up for AI agents. Humans join via browser (WebRTC), AI agents connect via a native Agent Gateway API or MCP server, and every meeting automatically extracts tasks, builds persistent memory, and drives accountability across meetings.

Convene serves two audiences: **teams** who want meetings that actually produce results, and **developers** who need a way for their AI agents to participate in meetings without hacking into platforms that resist them.

## Repository Structure

This is a Python monorepo managed with `uv` workspaces.

```
convene-ai/
├── external-docs/                 # User-facing documentation (this directory)
├── internal-docs/                 # Contributor/maintainer documentation
├── packages/                      # Shared libraries
│   ├── convene-core/              # Domain models, events, interfaces (ABCs)
│   ├── convene-providers/         # STT, TTS, LLM provider implementations
│   └── convene-memory/            # Four-layer persistent memory system
├── services/                      # Independently runnable services
│   ├── api-server/                # FastAPI REST + WebSocket API
│   ├── audio-service/             # Audio pipeline (WebRTC → STT)
│   ├── task-engine/               # LLM-powered task extraction workers
│   ├── agent-gateway/             # Agent connection & routing (WebSocket/MCP)
│   ├── mcp-server/                # Model Context Protocol server
│   └── worker/                    # Background jobs (Slack, calendar, notifications)
├── web/                           # Meeting client (React + LiveKit SDK)
├── integrations/openclaw-plugin/  # OpenClaw plugin source
├── examples/                      # Agent examples
├── deploy/                        # Deployment scripts
└── docker-compose.yml             # Local dev environment (PostgreSQL, Redis)
```

## Architecture

```
Human (Browser)                    AI Agent (any framework)
      │                                    │
      │ WebRTC                             │ WebSocket/gRPC/MCP
      ▼                                    ▼
┌─────────────┐                   ┌─────────────────┐
│  LiveKit     │◄─── audio ───────►│  Agent Gateway   │
│  WebRTC SFU  │    routing        │  (auth, streams,  │
│              │                   │   data channels)  │
└──────┬──────┘                   └────────┬──────────┘
       │                                   │
       │         audio streams             │
       ▼                                   ▼
┌──────────────────────────────────────────────┐
│              Audio Service                    │
│  (STT streaming, transcoding, buffering)      │
└──────────────────┬───────────────────────────┘
                   │ Redis Streams events
                   ▼
┌──────────────────────────────────────────────┐
│              Task Engine                      │
│  (extraction, dedup, persistence)             │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│     API Server + Memory System                │
│  (meeting state, tasks, decisions, history)    │
└──────────────────────────────────────────────┘
```

**MCP Server** wraps the Agent Gateway, allowing Claude Desktop, Claude Code, and any MCP-compatible client to join meetings via standard MCP tool calls (`join_meeting`, `get_transcript`, `create_task`, etc.).

## Documents

### For Users
- **[Agent Platform](agent-platform/overview.md)** — Three-tier agent architecture, prebuilt templates, and how to connect
- **[MCP Auth](agent-platform/connecting/mcp-auth.md)** — OAuth 2.1 authorization flow for agent connections
- **[Providers](providers/README.md)** — Configure STT, TTS, and LLM providers
- **[Self-Hosting](self-hosting/deployment.md)** — Deploy Convene AI yourself

### For Contributors (Internal)
- **[TASKLIST](../internal-docs/development/TASKLIST.md)** — Ordered task queue
- **[PROGRESS](../internal-docs/development/PROGRESS.md)** — Append-only log of completed work
- **[ROADMAP](../internal-docs/strategy/roadmap.md)** — Feature roadmap
- **[Internal Docs Index](../internal-docs/README.md)** — All internal documentation

## Architecture Decision: Agent-First Platform

Convene's core architectural bet is **owning the meeting environment** rather than bolting onto existing platforms. Instead of hacking bots into Zoom, Teams, or Google Meet (via phone dial-in, browser automation, or Recall.ai), Convene is the meeting platform itself.

This means:
- **AI agents connect natively** via the Agent Gateway API — clean audio streams, structured data, no workarounds
- **MCP support** — any MCP-compatible AI assistant joins meetings through standard tool calls
- **No platform lock-in** — no risk of Zoom/Teams blocking bots or changing APIs
- **Better AI experience** — the platform is designed for AI participants, with real-time collaboration surfaces, agent status indicators, and structured meeting context
- **Two-sided network effects** — more agents make the platform more valuable for teams, more teams attract more agent developers

The original phone dial-in architecture (Twilio) remains functional as a fallback for joining external meetings that have dial-in numbers.

## Current Phase

**Phase 1** — Core AI Pipeline (nearly complete). STT wired, Redis Streams consumer, segment windowing, task persistence, and event emission all done. One item remaining: wire LLM provider into the extraction pipeline.

**Phase 2 / April Release Sprint** — The active sprint through April 10, 2026. Building full multi-agent participation: turn management, meeting chat, 8 new MCP tools, and Claude Code channel integration. Target: all 4 multi-party E2E scenarios passing at launch.

| Week | Dates | Focus |
|------|-------|-------|
| Week 1 | Mar 22–28 | Backend infra — participant registry, turn manager (ABC + Redis), chat store (ABC + Redis), multi-agent gateway |
| Week 2 | Mar 29–Apr 4 | MCP tools, Claude Code channel, frontend turn/chat UI, example agents |
| Week 3 | Apr 5–11 | E2E scenario testing, polish, docs, launch |

**Agent connection pattern:** Claude Agent SDK → MCP Server (Bearer token) → Agent Gateway (WebSocket). Claude Code sessions also connect via channel server.

**Next task (CoWork):** Complete LLM-powered task extraction pipeline (Phase 1), then Participant registry → Turn Management Infrastructure → Meeting Chat Infrastructure.

## Getting Started with Development

1. Read `CLAUDE.md` at the repository root — this is the bootstrap prompt for Claude Code
2. Read `docs/TASKLIST.md` — find the next unchecked, unlocked item
3. Read the relevant `claude_docs/` reference for the package/service you're working on
4. Follow the quality gate before marking any task complete

## Running Locally

```bash
# Start infrastructure
docker compose up -d postgres redis

# Install dependencies
uv sync

# Run migrations
uv run alembic upgrade head

# Start services (each in a separate terminal)
uv run uvicorn services.api_server.main:app --reload --port 8000
uv run python -m services.audio_service.main
uv run python -m services.task_engine.main
uv run python -m services.worker.main

# Agent Gateway (requires PYTHONPATH for cross-package imports)
PYTHONPATH=services/agent-gateway/src:services/audio-service/src:packages/convene-core/src:packages/convene-providers/src:packages/convene-memory/src \
  .venv/bin/uvicorn agent_gateway.main:app --reload --port 8003
```
