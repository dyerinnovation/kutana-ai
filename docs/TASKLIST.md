# Convene AI — Development Task List

> This file is the task queue for both manual and scheduled development sessions.
> The daily build sprint picks the next unchecked, unlocked item and implements it.
>
> **Legend:**
> - `[ ]` — Not started (eligible for scheduled pickup)
> - `[x]` — Completed
> - `🔒` — Locked (Jonathan is working on this — skip it)

---

## Phase 1A: Foundation — Monorepo & Domain Models (Steps 1-2)

- [x] Initialize uv workspace with root pyproject.toml
- [x] Create package directory structure (convene-core, convene-providers, convene-memory)
- [x] Create service directory structure (api-server, audio-service, task-engine, worker)
- [x] Set up docker-compose.yml with PostgreSQL 16 (pgvector) and Redis 7
- [x] Create .env.example with all environment variables
- [x] Set up ruff.toml and mypy.ini with strict settings
- [x] Create CI workflow (.github/workflows/ci.yml) — ruff, mypy, pytest
- [x] Implement Meeting Pydantic model with validators
- [x] Implement Participant Pydantic model
- [x] Implement Task Pydantic model with status transition validators
- [x] Implement Decision Pydantic model
- [x] Implement TranscriptSegment Pydantic model
- [x] Implement AgentConfig Pydantic model
- [x] Implement event definitions (convene-core/events/definitions.py)
- [x] Create SQLAlchemy 2.0 ORM models for all domain entities
- [x] Set up Alembic configuration with async support
- [x] Create initial Alembic migration

## Phase 1B: Provider Interfaces & Implementations (Step 3)

- [x] Implement STTProvider abstract base class
- [x] Implement TTSProvider abstract base class
- [x] Implement LLMProvider abstract base class
- [x] Implement AssemblyAI streaming STT provider (WebSocket + speaker diarization)
- [x] Implement Deepgram STT provider (alternative provider)
- [x] Implement Anthropic LLM provider (Claude tool_use for structured extraction)
- [x] Implement provider registry with factory pattern
- [x] Write integration tests for provider registry

## Phase 1C: Twilio Audio Pipeline (Step 4)

- [ ] Implement MeetingDialer (outbound call + DTMF meeting code entry)
- [ ] Implement TwilioHandler (FastAPI WebSocket for Media Streams)
- [ ] Implement AudioPipeline (μ-law 8kHz → PCM16 16kHz transcoding)
- [ ] Implement Redis Streams publisher for transcript segments
- [ ] Implement meeting end detection (silence threshold + hangup handling)
- [ ] Implement graceful cleanup and audio buffering on STT failure
- [ ] Write end-to-end test for audio pipeline with mock Twilio

## Phase 1D: Task Extraction & Memory (Step 5)

- [ ] Implement Redis Streams consumer for transcript.segment.final events
- [ ] Implement transcript segment windowing (3-5 min windows with overlap)
- [ ] Implement LLM-powered task extraction pipeline
- [ ] Implement task deduplication against existing tasks
- [ ] Implement task persistence to PostgreSQL
- [ ] Implement task.created / task.updated event emission
- [ ] Implement working memory layer (Redis hash per active meeting)
- [ ] Implement short-term memory layer (recent meeting queries)
- [ ] Implement long-term memory layer (pgvector embeddings of meeting summaries)
- [ ] Implement structured state layer (task/decision indexes)
- [ ] Implement memory context builder (assembles relevant context for LLM)

## Phase 1E: API & Dashboard (Step 6)

- [ ] Implement FastAPI app setup with dependency injection (api-server/main.py)
- [ ] Implement meeting CRUD routes
- [ ] Implement task CRUD routes
- [ ] Implement agent config routes
- [ ] Implement WebSocket endpoint for live transcript streaming
- [ ] Implement API authentication middleware
- [ ] Implement CORS and rate limiting middleware
- [ ] Create OpenAPI schema documentation
- [ ] Scaffold React dashboard (Vite + React + Tailwind)
- [ ] Implement meeting list view (upcoming, active, completed)
- [ ] Implement live transcript view for active meetings
- [ ] Implement task board (kanban: pending, in progress, done, blocked)
- [ ] Implement meeting detail view (transcript + extracted tasks)

## Phase 2: Voice Output (Future)

- [x] Implement Cartesia TTS provider
- [x] Implement ElevenLabs TTS provider
- [ ] Implement bidirectional audio pipeline (Twilio → STT + TTS → Twilio)
- [ ] Implement agent speaking logic (when to interject, progress reports)
- [ ] Implement voice activity detection for turn-taking

---

## Notes

### CoWork Edit Protocol

**Task selection:** CoWork picks the first unchecked (`- [ ]`), unlocked (no 🔒) item in the current phase.

**Completion registration:**
1. Check off the item: `- [ ]` → `- [x]`
2. Append an entry to `docs/PROGRESS.md` (never overwrite previous entries)
3. Update `docs/HANDOFF.md` with shift-change notes

**Branch naming:** `scheduled/YYYY-MM-DD-{slug}` (e.g., `scheduled/2026-02-27-pydantic-models`)

**Lock protocol:** Only Jonathan adds or removes 🔒. CoWork must never lock or unlock items.

**Quality gate:** All of the following must pass before checking off an item:
- `uv run ruff check .` — no lint errors
- `uv run mypy --strict .` — no type errors
- `uv run pytest -x -v` — all tests pass

If quality checks fail after 3 fix attempts, document the failure in PROGRESS.md, note it as a blocker in HANDOFF.md, and stop. Do not check off the item.
