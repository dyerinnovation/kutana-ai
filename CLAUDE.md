# Convene AI

## Project Overview
Convene AI is an agent-first meeting platform where AI agents connect via native WebSocket API and humans join via browser WebRTC. Agents listen for commitments, extract tasks, and maintain persistent memory across meetings. The core insight: AI agents are first-class meeting participants, not bolted-on bots.

## Architecture
This is a Python monorepo managed with `uv` workspaces. The project is organized into shared packages and independent services.

### Packages (shared libraries)
- `packages/convene-core/` — Domain models (Pydantic v2), event definitions, abstract interfaces
- `packages/convene-providers/` — STT, TTS, and LLM provider implementations behind ABCs
- `packages/convene-memory/` — Four-layer memory system (working, short-term, long-term, structured)

### Services (independently runnable)
- `services/api-server/` — FastAPI REST + WebSocket API for dashboard and integrations
- `services/audio-service/` — Transport-agnostic audio pipeline and STT streaming
- `services/agent-gateway/` — WebSocket gateway for AI agent connections (auth, audio routing, event relay)
- `services/mcp-server/` — Model Context Protocol server exposing Convene tools for Claude and MCP clients
- `services/task-engine/` — Redis Streams consumer, LLM-powered task extraction workers
- `services/worker/` — Background jobs: notifications, Slack integration, calendar sync

### Frontend
- `web/` — React 19 + TypeScript + Vite + Tailwind v4 dashboard (auth, agent management, meetings)

### Infrastructure
- PostgreSQL 16 with pgvector extension — single database for relational + vector storage
- Redis 7 — event bus (Streams), working memory cache, pub/sub for real-time updates
- LiveKit — self-hosted WebRTC SFU for browser-based human participants
- Twilio (legacy/optional) — phone dial-in for joining external meetings with dial-in numbers
- Stripe — payment processing, subscription management, usage-based billing

## Tech Stack & Conventions
- **Python 3.12+** with strict type hints everywhere
- **uv** for package management and workspaces (NOT pip, NOT poetry)
- **ruff** for linting and formatting (replaces black, isort, flake8)
- **mypy** in strict mode for type checking
- **pytest** with async support (pytest-asyncio) for testing
- **Pydantic v2** for all data models — use model_validator and field_validator
- **SQLAlchemy 2.0** async style with mapped_column for ORM models
- **Alembic** for database migrations
- **FastAPI** with dependency injection for API endpoints
- **asyncio** throughout — no blocking calls in async code paths

## Key Design Principles
1. **Provider abstraction via ABCs**: Every external service (STT, TTS, LLM, phone) has an abstract base class. Implementations are swappable without changing business logic.
2. **Event-driven between services**: Services communicate via Redis Streams events, never direct calls. The audio service publishes transcript segments; the task engine consumes them.
3. **Agent-first access**: AI agents connect via WebSocket (agent-gateway), humans via WebRTC (LiveKit). No platform-specific bot SDKs needed.
4. **Pydantic models for API, SQLAlchemy for persistence**: Keep them separate. API models in convene-core, ORM models alongside the service that owns the table.
5. **Fail gracefully**: If STT drops, buffer audio and retry. If LLM extraction fails, queue for retry. Never lose meeting data.

## Code Style
- Use `async def` for all I/O operations
- Type hint every function signature and return value
- Docstrings on public methods (Google style)
- No `# type: ignore` without explanation
- Use `logging` module with structured log format (JSON in production)
- Environment variables for all config — never hardcode secrets
- Tests alongside code in `tests/` directories within each package/service

## File Naming
- Snake_case for all Python files
- Models: `models/task.py`, `models/meeting.py`
- Interfaces: `interfaces/stt.py`, `interfaces/llm.py`
- Implementations: `providers/assemblyai_stt.py`, `providers/anthropic_llm.py`

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
PYTHONPATH=services/agent-gateway/src:services/audio-service/src:packages/convene-core/src:packages/convene-providers/src:packages/convene-memory/src .venv/bin/uvicorn agent_gateway.main:app --reload --port 8003
uv run python -m services.audio_service.main
uv run python -m services.task_engine.main
uv run python -m services.worker.main
```

## Environment Variables
```
# Database
DATABASE_URL=postgresql+asyncpg://convene:convene@localhost:5432/convene

# Redis
REDIS_URL=redis://localhost:6379/0

# Agent Gateway
AGENT_GATEWAY_JWT_SECRET=change-me-in-production
AGENT_GATEWAY_PORT=8003

# MCP Server
MCP_SERVER_PORT=3000

# LiveKit (WebRTC)
LIVEKIT_URL=ws://localhost:7880
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=

# Twilio (legacy/optional — for phone dial-in to external meetings)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_PHONE_NUMBER=

# STT Providers
ASSEMBLYAI_API_KEY=
DEEPGRAM_API_KEY=

# LLM Providers
ANTHROPIC_API_KEY=

# TTS Providers (Phase 5)
CARTESIA_API_KEY=
ELEVENLABS_API_KEY=

# Billing (Stripe)
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PUBLISHABLE_KEY=
```

## Current Phase
**Phase 1** — Core AI Pipeline (in progress). STT wired, Redis Streams consumer implemented. Next task: transcript segment windowing, then LLM extraction pipeline and task persistence.

**Phase 2** — Agent Platform (mostly complete). Agent Gateway M3 verified. User auth, agent registration with API keys, MCP server (Streamable HTTP / Docker), web dashboard, and Claude Agent SDK example agent implemented (2026-03-02). Remaining: multi-agent support, agent modality support (Voice-to-Voice, Speech-to-Text, Text-only).

**Agent connection pattern:** Claude Agent SDK → MCP Server → Agent Gateway (WebSocket). See `docs/TASKLIST.md` for the full task queue (Phases 1–10) and `docs/technical/ROADMAP.md` for feature details.

## Git Workflow
- **Commit and push after each plan** — don't let changes accumulate across sessions
- **Keep commits small** — large commits with many files can hang on push; batch into logical chunks
- **Use SSH for GitHub** — HTTPS with GCM hangs in non-interactive shells. SSH config is at `~/.ssh/config` using `dyerinnovation-key`
- **Remote is SSH** — `git@github.com:dyerinnovation/convene-ai.git`
- **Co-author trailer** — always end commit messages with: `Co-Authored-By: Claude Opus 4.6 (1M context) <noreply@anthropic.com>`
- See `claude_docs/Git_Best_Practices.md` for full details

## What NOT to Do
- Don't use platform-specific meeting SDKs (Zoom SDK, Teams SDK) — agents connect natively via agent-gateway
- Don't use Poetry or pip — use uv exclusively
- Don't use `uv pip install` — use `uv add` (or `uv add --dev`) for managing dependencies
- Don't use synchronous database calls — always use async SQLAlchemy
- Don't put business logic in API endpoints — use service layer functions
- Don't skip type hints — mypy strict mode is enforced

## Package Implementation Details
- See `claude_docs/Convene_Core_Patterns.md` for convene-core package patterns (models, events, interfaces, database)
- See `claude_docs/Provider_Patterns.md` for provider ABC signatures, third-party library conventions, and registry usage
- See `claude_docs/Memory_Architecture.md` for the four-layer memory system design and ORM-to-domain conversion patterns
- See `claude_docs/Service_Patterns.md` for service layer conventions (health endpoints, lifespan, settings, DI, route organization)
- See `claude_docs/Agent_Gateway_Architecture.md` for Agent Gateway WebSocket protocol details (if exists)
- See `claude_docs/Auth_And_API_Keys.md` for user auth (JWT), API key system, and token exchange patterns
- See `claude_docs/MCP_Server_Architecture.md` for MCP server tools, Streamable HTTP transport, and Docker setup

## Tooling
- See `claude_docs/UV_Best_Practices.md` for uv workspace patterns, testing commands, and known pitfalls (UF_HIDDEN, UV_LINK_MODE, etc.)
- See `claude_docs/PYTHONPATH_Workaround.md` for macOS UF_HIDDEN / .pth file workaround

## Test Data
- `data/input/` — sample audio files for STT testing (`librispeech_sample.flac`, `test-speech.wav`)
- `data/output/` — test result output (e.g. `e2e_results.json`)

## Infrastructure
- See `claude_docs/DGX_Spark_Reference.md` for DGX Spark connection details, K8s patterns, and deployment gotchas
- See `charts/stt/` for the Whisper STT Helm chart deployed on DGX Spark

## CoWork Coordination
- See `docs/TASKLIST.md` for the ordered development task queue (supports `🔗 BLOCK:` multi-task items)
- See `docs/cowork-tasks/` for scheduled task instructions (daily-build supports block mode)
- See `docs/SETUP_GUIDE.md` for full CoWork setup documentation
- **Phase change rule:** When updating phase numbering, update all three files: `docs/TASKLIST.md`, `CLAUDE.md`, and `docs/README.md`

## TASKLIST Lock Protocol
- **When starting work on a TASKLIST item:** Add 🔒 to the item to prevent CoWork or other sessions from picking it up
- **When finishing work on a TASKLIST item:** Replace `- [ ] 🔒` with `- [x]` (checked off, lock removed)
- **Only the session that locked an item should unlock it** — if you see a 🔒 you didn't place, skip that item
- **Milestone items (🏁)** are verification checkpoints, not implementation tasks — check them off when their prerequisites pass
