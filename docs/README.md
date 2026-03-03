# Convene AI — The Agent-First Meeting Platform

## What is Convene AI?

Convene is a meeting platform built from the ground up for AI agents. Humans join via browser (WebRTC), AI agents connect via a native Agent Gateway API or MCP server, and every meeting automatically extracts tasks, builds persistent memory, and drives accountability across meetings.

Convene serves two audiences: **teams** who want meetings that actually produce results, and **developers** who need a way for their AI agents to participate in meetings without hacking into platforms that resist them.

## Repository Structure

This is a Python monorepo managed with `uv` workspaces.

```
convene-ai/
├── CLAUDE.md                      # Bootstrap prompt for Claude Code development
├── docs/                          # Product & strategy documentation
│   ├── README.md                  # This file
│   ├── TASKLIST.md                # Ordered development task queue
│   ├── PROGRESS.md                # Append-only log of completed work
│   ├── HANDOFF.md                 # Shift-change notes for CoWork
│   ├── PIVOT_RECOMMENDATIONS.md   # Analysis of pivot changes needed
│   ├── technical/
│   │   ├── VISION.md              # Product vision & business case
│   │   ├── ROADMAP.md             # Feature roadmap (Claude Code-ready)
│   │   ├── COMPETITIVE_ANALYSIS.md # Market sizing & competitive landscape
│   │   └── GO_TO_MARKET.md        # Go-to-market strategy
│   ├── prompts/                   # Claude Code planning prompts
│   ├── providers/                 # Provider setup guides
│   └── milestone-testing/         # Milestone test plans
├── claude_docs/                   # Claude Code development reference docs
├── packages/                      # Shared libraries
│   ├── convene-core/              # Domain models, events, interfaces (ABCs)
│   ├── convene-providers/         # STT, TTS, LLM provider implementations
│   └── convene-memory/            # Four-layer persistent memory system
├── services/                      # Independently runnable services
│   ├── api-server/                # FastAPI REST + WebSocket API
│   ├── audio-service/             # Audio pipeline (Twilio + WebRTC → STT)
│   ├── task-engine/               # LLM-powered task extraction workers
│   ├── agent-gateway/             # Agent connection & routing (WebSocket/gRPC)
│   ├── mcp-server/                # Model Context Protocol server
│   └── worker/                    # Background jobs (Slack, calendar, notifications)
├── web/                           # Meeting client (React + LiveKit SDK)
├── charts/                        # Helm charts (Whisper STT on DGX Spark)
├── pyproject.toml                 # Root workspace config (uv)
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

### Strategy
- **[VISION.md](./technical/VISION.md)** — Product vision, business case, market opportunity, revenue model, and competitive moat. Covers the dual-audience thesis (developers + teams) and the agent-first platform positioning.
- **[ROADMAP.md](./technical/ROADMAP.md)** — Feature-by-feature development roadmap structured for Claude Code. Each feature has context, acceptance criteria, and technical notes. Organized into 7 phases from Foundation through Platform Hardening.
- **[COMPETITIVE_ANALYSIS.md](./technical/COMPETITIVE_ANALYSIS.md)** — Market sizing and competitive landscape. Covers transcription tools (Otter, Fireflies), platform AI (Zoom, Teams), and agent infrastructure (Recall.ai).
- **[GO_TO_MARKET.md](./technical/GO_TO_MARKET.md)** — Go-to-market strategy for the two-sided market. Developer track (API, SDK, MCP) and team track (meetings, task extraction, memory).

### Development
- **[TASKLIST.md](./TASKLIST.md)** — Ordered task queue for manual and scheduled development sessions. Phases 1A-1C complete, 1D in progress. New Phases 2-7 cover Agent Gateway, auth, billing, WebRTC, dashboard, marketplace, and hardening.
- **[PROGRESS.md](./PROGRESS.md)** — Append-only log of completed work.
- **[HANDOFF.md](./HANDOFF.md)** — Shift-change notes for CoWork sessions.

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

**Phase 1D** — Task Extraction & Memory (in progress). The audio-to-transcript pipeline is proven (M1 milestone passed). Task extraction windowing, LLM pipeline, and memory system are next.

**Next up:** Phase 2 — Agent Gateway & MCP (the core platform differentiator).

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
```
