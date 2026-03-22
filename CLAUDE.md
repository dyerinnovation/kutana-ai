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
- `services/cli/` — Convene CLI tool (typer-based, wraps REST API)

### Frontend
- `web/` — React 19 + TypeScript + Vite + Tailwind v4 dashboard (auth, agent management, meetings)

### Infrastructure
- PostgreSQL 16 with pgvector extension — single database for relational + vector storage
- Redis 7 — event bus (Streams), working memory cache, pub/sub for real-time updates
- LiveKit — self-hosted WebRTC SFU for browser-based human participants
- Twilio (legacy/optional) — phone dial-in for joining external meetings with dial-in numbers
- Stripe — payment processing, subscription management, usage-based billing

### Messaging Layer
The platform messaging layer is abstracted behind a MessageBus ABC. Services never import a specific messaging implementation directly. The provider registry resolves the bus implementation at startup based on `CONVENE_MESSAGE_BUS` config (`redis`, `aws-sns-sqs`, `gcp-pubsub`, `nats`). This ensures Convene AI is deployable on any infrastructure.

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

**Phase 2** — Agent Platform (complete as of 2026-03-07). MCP OAuth 2.1 auth, meeting lifecycle, browser meeting room with mic audio, prebuilt agent templates, CLI tool, OpenClaw plugin, Claude Code skill, channel routing, API key security.

**Agent connection pattern:** Claude Agent SDK → MCP Server (Bearer token) → Agent Gateway (WebSocket). See `docs/TASKLIST.md` for the full task queue (Phases 1–10) and `docs/technical/ROADMAP.md` for feature details.

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
- See `claude_docs/MessageBus_Patterns.md` for MessageBus ABC, Redis Streams provider, MockMessageBus, and service wiring patterns
- See `claude_docs/Memory_Architecture.md` for the four-layer memory system design and ORM-to-domain conversion patterns
- See `claude_docs/Service_Patterns.md` for service layer conventions (health endpoints, lifespan, settings, DI, route organization)
- See `claude_docs/Agent_Gateway_Architecture.md` for Agent Gateway WebSocket protocol details (if exists)
- See `claude_docs/Auth_And_API_Keys.md` for user auth (JWT), API key system, and token exchange patterns
- See `claude_docs/MCP_Server_Architecture.md` for MCP server tools, Streamable HTTP transport, and Docker setup

## Agent Platform & Integrations
- Agent context is provided through three layers: platform context (fixed, explains Convene AI to agents), meeting context (dynamic, from calendar invite), and meeting recap (live, for late joiners). See `docs/technical/agent-context-seeding.md`.
- See `docs/technical/AGENT_PLATFORM.md` for three-tier agent architecture and access matrix
- See `docs/technical/MCP_AUTH.md` for MCP OAuth 2.1 authorization flow
- See `docs/integrations/OPENCLAW.md` for OpenClaw plugin integration
- See `docs/integrations/CLAUDE_AGENT_SDK.md` for Claude Agent SDK setup
- See `docs/integrations/CLI.md` for Convene CLI reference
- See `integrations/openclaw-plugin/` for the OpenClaw plugin source
- See `examples/meeting-assistant-agent/` for Claude Agent SDK example with 4 templates

## Tooling
- See `claude_docs/UV_Best_Practices.md` for uv workspace patterns, testing commands, and known pitfalls (UF_HIDDEN, UV_LINK_MODE, etc.)
- See `claude_docs/PYTHONPATH_Workaround.md` for macOS UF_HIDDEN / .pth file workaround

## Test Data
- `data/input/` — sample audio files for STT testing (`librispeech_sample.flac`, `test-speech.wav`)
- `data/output/` — test result output (e.g. `e2e_results.json`)
- See `docs/milestone-testing/` for per-feature QA playbooks (00-SETUP through 10-full-e2e-demo)
- See `docs/manual-testing/E2E_Gateway_Test.md` for gateway + STT integration walkthrough

## Development Infrastructure

### DGX Spark (Primary Compute)
- All Docker containers, tests, and heavy compute run on the DGX Spark
- Do NOT run Docker builds or container workloads on the personal Mac
- **SSH alias:** `ssh dgx` (key-based auth, no password — see `~/.ssh/config`)
- **SSH key:** `~/.ssh/id_dgx_spark` (ed25519, authorized on DGX since 2026-03-21)
- The DGX Spark runs: postgres, redis, api-server, agent-gateway, audio-service, task-engine
- GPU available for self-hosted Whisper STT (NVIDIA GB10 Grace Blackwell, 128GB unified memory)
- Always-on Claude Code with Discord channel

#### SSH Connection Patterns
- **Regular commands (preferred):** `ssh dgx '<command>'` — key-based auth, no password needed
- **File transfer:** `scp file.txt dgx:~/path/` or `scp dgx:~/path/file.txt ./`
- **File sync:** `rsync -av ./local/ dgx:~/remote/`
- **Sudo commands (fallback):** Use `sshpass` with `DGX_PASSWORD` from `.env` (sudo requires password):
  ```bash
  export $(grep -v '^#' .env | xargs)
  sshpass -p "$DGX_PASSWORD" ssh dgx 'echo '"$DGX_PASSWORD"' | sudo -S <command>'
  ```
  - **Always use single quotes** around the remote command to prevent `!` in the password from being interpreted by the local shell
- **KUBECONFIG:** `/etc/rancher/k3s/k3s.yaml` — always pass via `sudo env KUBECONFIG=...` (sudo drops the env var)
- **Container runtime:** containerd, not Docker — import images via `sudo k3s ctr images import <file>`
- **Helm path:** `/home/jondyer3/.local/bin/helm` — not in default PATH; `sudo env` does not inherit PATH so always use full path
- **Spark PATH:** `$HOME/.local/bin:$HOME/.nvm/versions/node/v22.22.0/bin:$PATH`

### Personal Mac (Client Only)
- Used for Dispatch/Cowork orchestration and code editing
- SSH into DGX for running services and tests
- No Docker containers should run here

### Mac Mini (Control Plane — Planned)
- Will run Claude Desktop with Dispatch/Cowork 24/7
- Orchestrates work across DGX Spark and other nodes
- Low-power, always-on

## Infrastructure
- See `claude_docs/DGX_Spark_Reference.md` for DGX Spark hardware, K8s patterns, and deployment gotchas
- See `claude_docs/DGX_Spark_SSH_Connection.md` for full SSH connection patterns, sshpass usage, sudo patterns, and PATH gotchas
- See `charts/stt/` for the Whisper STT Helm chart deployed on DGX Spark

## LLM Strategy
All LLM operations use the Anthropic Claude API via the Claude Agent SDK. No OpenAI or Google model integrations. Model tiers: **Claude Haiku** for entity extraction (high volume, low cost), **Claude Sonnet** for meeting recaps and agent dialogue, **Claude Opus** for premium analysis (optional, Business/Enterprise tiers). See `docs/technical/cost-architecture.md` for full model and cost details.

## STT Strategy
Primary STT provider at launch: **Deepgram Nova-2** (all tiers) — $0.0043/min, speaker diarization included free, real-time streaming. Self-hosted faster-whisper + pyannote.audio is an Enterprise-only option (Phase D) for data sovereignty use cases requiring GPU compute. AWS Transcribe and GCP Speech-to-Text are available via provider abstraction but not recommended as primary.

## Billing Architecture
Billing uses Stripe for subscription management and usage-based metering. Four tiers: Free (5 meetings/month), Pro ($29/user/month), Business ($79/user/month), Enterprise (custom). Plan tier gates feature access (entity types, diarization, custom extractors, model selection). Usage is metered per meeting minute, extraction call, and agent session. See `docs/technical/cost-architecture.md` for full cost model and Stripe integration details.

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
