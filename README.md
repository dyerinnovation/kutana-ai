# Convene AI

**The AI meeting participant that listens, extracts, and speaks.**

Convene AI is a voice-first AI agent that dials into your meetings via phone, listens for commitments, extracts and tracks tasks across meetings, and speaks to report progress. It's not a transcription tool — it's a meeting participant.

---

## How It Works

1. **Schedule a meeting** via the API with a dial-in number and meeting code
2. **Convene dials in** using Twilio, enters the meeting code via DTMF tones, and starts listening
3. **Real-time transcription** via STT providers (Deepgram, AssemblyAI, or local Whisper)
4. **Task extraction** — an LLM identifies action items, owners, and deadlines from the transcript
5. **Persistent memory** — tasks, decisions, and context accumulate across meetings
6. **Voice output** — the agent speaks summaries and progress reports via TTS (ElevenLabs, Cartesia, or local Piper)

## Architecture

Python monorepo managed with [uv](https://docs.astral.sh/uv/) workspaces. Services communicate via Redis Streams events.

```
convene-ai/
├── packages/                      # Shared libraries
│   ├── convene-core/              # Domain models, events, provider interfaces (ABCs)
│   ├── convene-providers/         # STT, TTS, LLM provider implementations
│   └── convene-memory/            # Four-layer persistent memory system
├── services/                      # Independently runnable services
│   ├── api-server/                # FastAPI REST + WebSocket API
│   ├── audio-service/             # Twilio Media Streams + audio pipeline
│   ├── task-engine/               # LLM-powered task extraction workers
│   └── worker/                    # Background jobs (Slack, calendar, notifications)
├── alembic/                       # Database migrations
├── charts/                        # Kubernetes Helm charts (DGX Spark)
└── docs/                          # Documentation
```

### Data Flow

```
Twilio Call ──→ Audio Service ──→ STT Provider ──→ Redis Streams
                                                       │
                                                       ▼
API Server ◄── PostgreSQL ◄── Task Engine ◄── LLM Provider
    │
    ▼
 Dashboard / TTS Readback
```

### Key Architectural Decision: Phone Dial-In

Convene uses **Twilio phone dial-in** instead of platform-specific bot SDKs (Zoom SDK, Teams Bot Framework). Every major meeting platform supports phone participants — one integration works everywhere.

**Tradeoff:** Phone-quality audio (8kHz) instead of 48kHz, no video access. Modern STT handles phone audio well, and for task extraction this is acceptable.

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
| Phone | Twilio (Media Streams) |

### Provider Support

| Category | Providers |
|----------|----------|
| **STT** | Deepgram, AssemblyAI, Whisper (local) |
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

**Phase 1A-1C complete.** Domain models, all provider implementations, Twilio audio pipeline, and event publishing are built and tested (149 tests passing).

**Phase 1D-1E in progress.** Task extraction pipeline, API database integration, and the path to the first live demo (agent dials into a real meeting, extracts notes, speaks them back via TTS).

See [docs/TASKLIST.md](docs/TASKLIST.md) for the full development task queue.

## Documentation

### Product & Strategy
- [Vision & Business Case](docs/technical/VISION.md)
- [Product Roadmap](docs/technical/ROADMAP.md)
- [Competitive Analysis](docs/technical/COMPETITIVE_ANALYSIS.md)
- [Go-to-Market Strategy](docs/technical/GO_TO_MARKET.md)

### Technical Reference
- [Provider Implementations](docs/providers/README.md) — per-provider setup and usage docs
- [Core Package Patterns](claude_docs/Convene_Core_Patterns.md) — models, events, interfaces, database
- [Provider Patterns](claude_docs/Provider_Patterns.md) — ABC signatures, registry usage
- [Memory Architecture](claude_docs/Memory_Architecture.md) — four-layer memory system
- [Service Patterns](claude_docs/Service_Patterns.md) — health endpoints, lifespan, settings, DI
- [DGX Spark Reference](claude_docs/DGX_Spark_Reference.md) — K8s deployment on DGX Spark

### Development Workflow
- [Task List](docs/TASKLIST.md) — ordered development queue
- [CoWork Setup Guide](docs/SETUP_GUIDE.md) — automated daily build sprints
- [CoWork Task Descriptions](docs/cowork-tasks/) — scheduled task instructions
- [Progress Log](docs/PROGRESS.md) — running development log
- [Handoff Notes](docs/HANDOFF.md) — shift-change context

## License

Private — Dyer Innovation
