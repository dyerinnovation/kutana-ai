# Kutana AI

**The agent-first meeting platform — where AI agents are first-class participants.**

Kutana AI is a meeting platform built from the ground up for AI agents. Agents connect via a native WebSocket gateway, humans join via browser (WebRTC planned), and every meeting automatically extracts tasks, builds persistent memory, and drives accountability. It's not a transcription tool — it's a platform where AI and humans collaborate in real-time.

---

## How It Works

1. **Agent connects** via the Agent Gateway WebSocket API (authenticated with JWT)
2. **Audio streams in** — the agent sends audio frames; the gateway routes them to the STT pipeline
3. **Real-time transcription** via STT providers (Whisper Remote on DGX Spark, Deepgram, AssemblyAI, or local Whisper)
4. **Events flow back** — transcript segments are published to Redis Streams and relayed to connected agents
5. **Task extraction** — an LLM identifies action items, owners, and deadlines from the transcript
6. **Persistent memory** — tasks, decisions, and context accumulate across meetings
7. **Voice output** (planned) — the agent speaks summaries and progress reports via TTS (ElevenLabs, Cartesia, or local Piper)

## Architecture

Python monorepo managed with [uv](https://docs.astral.sh/uv/) workspaces. Services communicate via Redis Streams events.

```
kutana-ai/
├── packages/                      # Shared libraries
│   ├── kutana-core/              # Domain models, events, provider interfaces (ABCs)
│   ├── kutana-providers/         # STT, TTS, LLM provider implementations
│   └── kutana-memory/            # Four-layer persistent memory system
├── services/                      # Independently runnable services
│   ├── api-server/                # FastAPI REST + WebSocket API
│   ├── audio-service/             # Transport-agnostic audio pipeline + STT streaming
│   ├── agent-gateway/             # WebSocket gateway for AI agent connections
│   ├── mcp-server/                # Model Context Protocol server for Claude/MCP clients
│   ├── task-engine/               # LLM-powered task extraction workers
│   └── worker/                    # Background jobs (Slack, calendar, notifications)
├── web/                           # Meeting web client (React + LiveKit SDK + Tailwind)
├── alembic/                       # Database migrations
├── charts/                        # Kubernetes Helm charts (DGX Spark)
└── docs/                          # Documentation
```

### Data Flow

```
AI Agent (any framework)
    │
    │ WebSocket (JWT auth)
    ▼
Agent Gateway ──→ AudioBridge ──→ STT Provider ──→ Redis Streams
                                                        │
                  EventRelay ◄──────────────────────────┘
                      │                                 │
                      ▼                                 ▼
              Agent receives               Task Engine ──→ PostgreSQL
              transcript events                    │
                                                   ▼
                                            API Server + Memory
```

### Architecture Decision: Agent-First Platform

Kutana **owns the meeting environment** rather than bolting onto existing platforms. Instead of hacking bots into Zoom/Teams via phone dial-in or browser automation, Kutana is the meeting platform itself.

- **AI agents connect natively** via the Agent Gateway API — clean audio streams, structured data, no workarounds
- **MCP support** (planned) — any MCP-compatible AI assistant joins meetings through standard tool calls
- **No platform lock-in** — no risk of Zoom/Teams blocking bots or changing APIs

The original phone dial-in architecture (Twilio) remains functional as a fallback for joining external meetings with dial-in numbers.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12+ with strict type hints |
| Package management | uv (workspaces) |
| Web framework | FastAPI (async) |
| Database | PostgreSQL 16 + pgvector |
| Event bus | Redis 7 (Streams) |
| ORM | SQLAlchemy 2.0 (async) |
| Migrations | Alembic |
| Linting | ruff |
| Type checking | mypy (strict) |
| Testing | pytest + pytest-asyncio |
| Phone | Twilio (legacy/optional) |
| WebRTC | LiveKit (planned) |

### Provider Support

| Category | Providers |
|----------|----------|
| **STT** | Deepgram, AssemblyAI, Whisper (local), Whisper Remote (DGX Spark) |
| **TTS** | ElevenLabs, Cartesia, Piper (local) |
| **LLM** | Anthropic Claude, Groq, Ollama (local) |

All providers implement abstract base classes and are swappable via the provider registry.

## Quick Start

```bash
# Prerequisites: Docker, uv, Python 3.12+

# Start infrastructure
docker compose up -d postgres redis

# Install dependencies
uv sync --all-packages

# Run migrations
uv run alembic upgrade head

# Start services (each in a separate terminal)
uv run uvicorn api_server.main:app --reload --port 8000
uv run uvicorn audio_service.main:app --reload --port 8001
uv run uvicorn task_engine.main:app --reload --port 8002

# Agent Gateway (requires PYTHONPATH for cross-package imports)
PYTHONPATH=services/agent-gateway/src:services/audio-service/src:packages/kutana-core/src:packages/kutana-providers/src:packages/kutana-memory/src \
  .venv/bin/uvicorn agent_gateway.main:app --reload --port 8003

# Run tests
UV_LINK_MODE=copy uv run pytest -x -v
```

### Environment Variables

Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

Required for live demo:
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`
- At least one STT key (`DEEPGRAM_API_KEY` or `ASSEMBLYAI_API_KEY`)
- At least one LLM key (`ANTHROPIC_API_KEY` or `GROQ_API_KEY`)
- At least one TTS key (`ELEVENLABS_API_KEY` or `CARTESIA_API_KEY`)

For local-only development (no API keys needed): use Whisper (STT), Ollama (LLM), and Piper (TTS).

## Current Status

**Phase 1A-1C complete.** Domain models, all provider implementations, Twilio audio pipeline, and event publishing are built and tested.

**Phase 1D in progress.** STT wired into audio service, Redis Streams consumer implemented. Next: transcript segment windowing, LLM pipeline, memory system.

**Phase 2 Agent Gateway — M3 verified (2026-03-02).** Agent connects via WebSocket, sends real audio, receives 29 transcript segments E2E through DGX Spark Whisper. 58 gateway tests + 38 audio-service tests passing.

See [docs/TASKLIST.md](docs/TASKLIST.md) for the full development task queue.

## Documentation

### Product & Strategy
- [Vision & Business Case](docs/technical/VISION.md)
- [Product Roadmap](docs/technical/ROADMAP.md)
- [Competitive Analysis](docs/technical/COMPETITIVE_ANALYSIS.md)
- [Go-to-Market Strategy](docs/technical/GO_TO_MARKET.md)

### Technical Reference
- [Provider Implementations](docs/providers/README.md) — per-provider setup and usage docs
- [Core Package Patterns](claude_docs/Kutana_Core_Patterns.md) — models, events, interfaces, database
- [Provider Patterns](claude_docs/Provider_Patterns.md) — ABC signatures, registry usage
- [Memory Architecture](claude_docs/Memory_Architecture.md) — four-layer memory system
- [Service Patterns](claude_docs/Service_Patterns.md) — health endpoints, lifespan, settings, DI
- [Agent Gateway Architecture](claude_docs/Agent_Gateway_Architecture.md) — WebSocket protocol, AudioBridge, EventRelay
- [E2E Gateway Test](docs/manual-testing/E2E_Gateway_Test.md) — step-by-step E2E test walkthrough
- [UV Best Practices](claude_docs/UV_Best_Practices.md) — uv workspace patterns and known pitfalls
- [PYTHONPATH Workaround](claude_docs/PYTHONPATH_Workaround.md) — macOS UF_HIDDEN / .pth file fix
- [DGX Spark Reference](claude_docs/DGX_Spark_Reference.md) — K8s deployment on DGX Spark

### Development Workflow
- [Task List](docs/TASKLIST.md) — ordered development queue
- [CoWork Setup Guide](docs/SETUP_GUIDE.md) — automated daily build sprints
- [CoWork Task Descriptions](docs/cowork-tasks/) — scheduled task instructions
- [Progress Log](docs/PROGRESS.md) — running development log
- [Handoff Notes](docs/HANDOFF.md) — shift-change context

## License

Private — Dyer Innovation
