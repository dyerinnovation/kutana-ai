# Convene AI — Development Progress Log

> Append-only log of completed work. Each entry is written by whoever completed
> the work — either CoWork (scheduled) or Jonathan (manual session).
> Never delete or overwrite previous entries.

---

<!-- New entries go at the top -->

## 2026-03-02 — DGX Whisper Fix & E2E Verification

**Roadmap item:** Agent Gateway M3 milestone verification + bug fixes
**Branch:** scheduled/2026-03-01-redis-streams-consumer (merged to main)
**Author:** Jonathan (manual session with Claude Code)

### Changes
- Replaced httpx with aiohttp in `WhisperRemoteSTT` — httpx lacks Happy Eyeballs (RFC 8305), hangs on `.local` mDNS hostnames trying IPv6 link-local first. aiohttp uses `aiohappyeyeballs` and works correctly
- Fixed audio-service tests (`test_get_segments_yields_stt_segments`, `test_segments_published_as_events`) — added `process_audio()` before `get_segments()`. All 38 audio-service tests pass
- Fixed pydantic-settings crash — added `"extra": "ignore"` in `model_config` for settings classes loading shared `.env` files
- Verified full E2E pipeline: agent connects via WebSocket → sends real audio (`test-speech.wav`) → DGX Spark Whisper transcribes → 29 transcript segments returned → Redis XLEN=31 entries
- Updated all documentation (TASKLIST, PROGRESS, HANDOFF, README, E2E test guide, DAILY_BRIEF, WEEKLY_REVIEW, CLAUDE.md)
- Merged branch to main

### Quality Check Results
- pytest: ✅ All tests passing (38 audio-service + 58 gateway = 96+ service tests)
- E2E: ✅ 29 transcript segments, Redis XLEN=31

### Blockers
None

### Next Up
- Implement transcript segment windowing (3-5 min windows with overlap)

---

## 2026-03-01 — Agent Gateway M3: Full Gateway Service Implementation

**Roadmap item:** Phase 2 Agent Gateway & MCP — gateway service, auth, connections, audio routing, event relay
**Branch:** scheduled/2026-03-01-redis-streams-consumer
**Author:** Jonathan (manual session with Claude Code)

### Changes

**Agent Gateway service (`services/agent-gateway/`):**
- Implemented `GatewayProtocol` — WebSocket message types: `join_meeting`, `leave_meeting`, `audio_data`, `heartbeat`, `event`, `transcript`, `error`
- Implemented JWT-based agent authentication (API key validation on connect)
- Implemented capability negotiation (`listen`, `speak`, `transcribe`, `push-ui`, `access-transcript`)
- Implemented `ConnectionManager` — agent presence tracking, join/leave, heartbeat timeout (30s default)
- Implemented `AudioBridge` — audio stream routing from agent → STT pipeline, batched transcription every 5 seconds
- Implemented `EventRelay` — Redis Streams consumer that routes `transcript.segment.final` events back to connected agents
- Implemented FastAPI service with WebSocket endpoint, health check, lifespan management
- 58 tests across 6 test files: protocol, auth, connection manager, audio bridge, event relay, E2E flow

**WhisperRemoteSTT provider (`packages/convene-providers/`):**
- New STT provider targeting remote OpenAI-compatible Whisper API (DGX Spark)
- Registered as `"whisper-remote"` in provider registry
- One-shot transcription (not streaming) — `_consume_segments` loops periodically

**Core model & event updates (`packages/convene-core/`):**
- Added 6 new event types: `room.created`, `agent.joined`, `agent.left`, `participant.joined`, `participant.left`, `agent.data`
- Updated `TranscriptSegment.confidence` handling — Whisper avg_logprob is negative, convert via `math.exp()`

**Service refactors:**
- Audio service refactored for transport-agnostic pipeline (not just Twilio)
- STT provider wired into audio service lifespan via provider registry + config

**E2E test infrastructure:**
- `scripts/test_e2e_gateway.py` — automated E2E test script
- `docs/manual-testing/E2E_Gateway_Test.md` — step-by-step walkthrough
- `claude_docs/Agent_Gateway_Architecture.md` — gateway architecture reference
- `claude_docs/UV_Best_Practices.md` — uv workspace patterns reference

### Quality Check Results
- pytest: ✅ 58 gateway tests passing
- E2E: ✅ Verified with DGX Spark Whisper (29 segments)

### Blockers
None

### Next Up
- Implement transcript segment windowing (3-5 min windows with overlap)

---

## 2026-03-01 — Redis Streams Consumer for transcript.segment.final Events

**Roadmap item:** Implement Redis Streams consumer for transcript.segment.final events
**Branch:** scheduled/2026-03-01-redis-streams-consumer
**Author:** CoWork (scheduled)

### Changes
- Created `services/task-engine/src/task_engine/stream_consumer.py` — `StreamConsumer` class using XREADGROUP consumer groups, exponential back-off reconnection, and per-entry XACK after processing
- Updated `services/task-engine/src/task_engine/main.py` — replaced sleep-based placeholder with real `StreamConsumer` wired into the FastAPI lifespan; added `consumer_group` and `consumer_name` settings; added thin `_on_segment` logging handler
- Created `services/task-engine/tests/test_stream_consumer.py` — 20 unit tests across 7 classes covering: initialisation defaults, consumer group creation (incl. BUSYGROUP handling), per-entry processing (happy path, non-segment skip, parse error, callback error, missing field), stop/cancellation, consume loop reconnection, and TaskEngineSettings env-var overrides

### Quality Check Results
- ruff: ⚠️ Could not run — CoWork Linux VM has Python 3.10; ruff binary in .venv is macOS ARM64
- mypy: ⚠️ Could not run — same environment constraint
- pytest: ⚠️ Could not run — same environment constraint
- Syntax validation: ✅ Passed (ast.parse on all 3 files)
- Structural checks: ✅ Passed (verified XREADGROUP, xgroup_create, xack, BUSYGROUP, backoff, CancelledError present)

### Notes
- Consumer group uses `id="$"` so the task-engine only processes events published after it first starts; historical replay is not needed
- Malformed or unhandled entries are ACKed immediately to prevent PEL accumulation — failures are logged at ERROR level for observability
- `_on_segment` is a logging stub; the full extraction pipeline (windowing → LLM → dedup → persist) will replace it in the next Phase 1D tasks
- The `consumer_name` setting defaults to `worker-<hostname>` so multiple replicas automatically get distinct identities

### Blockers
- Quality checks (ruff, mypy, pytest) must be run by Jonathan on his Mac before merging: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest -x -v`

### Next Up
- Implement transcript segment windowing (3-5 min windows with overlap)

---

## 2026-02-28 — Integration Tests for Provider Registry

**Roadmap item:** Write integration tests for provider registry
**Branch:** scheduled/2026-02-28-registry-integration-tests
**Author:** CoWork (scheduled)

### Changes
- Expanded `packages/convene-providers/tests/test_registry_integration.py` from 8 tests to 20 tests across 6 test classes:
  - `TestSTTLifecycle` — added `test_audio_buffer_accumulates`, `test_multiple_segments_ordered`, `test_close_resets_state`
  - `TestTTSLifecycle` — added `test_synthesize_different_texts_return_same_audio`, `test_get_voices_returns_voice_objects`
  - `TestLLMLifecycle` — added `test_extract_tasks_returns_configured_tasks`, `test_generate_report_with_tasks`, `test_defaults_when_no_kwargs`
  - `TestRegistryBehaviour` — added `test_same_name_different_type_allowed`, `test_unregistered_is_registered_returns_false`, `test_error_does_not_corrupt_registry`, `test_list_providers_empty_registry`, `test_list_providers_sorted`, `test_list_providers_type_isolation`
  - `TestDefaultRegistry` (new class) — smoke tests for all 4 instantiable provider types (whisper, piper, ollama, groq), completeness checks for all 9 registered providers, sorted output check, mutation safety check

### Quality Check Results
- ruff: ⚠️ Could not run — CoWork Linux VM has only Python 3.10; ruff binary in .venv is macOS ARM64
- mypy: ⚠️ Could not run — same environment constraint
- pytest: ⚠️ Could not run — same environment constraint
- Syntax validation: ✅ Passed (via `python3 ast.parse`)
- Manual code review: ✅ Passed — imports, type hints, docstrings, and test logic are correct

### Notes
- The CoWork Linux VM does not have Python 3.12+ and network access to download it is blocked, so quality tools from the `.venv` (which is a macOS ARM64 virtualenv) cannot execute
- All 20 tests follow the project's existing patterns — pytest-asyncio for async tests, Google-style docstrings, strict type annotations, fixtures via helper functions
- Tests cover: full provider lifecycle (start/send/stream/close), registry isolation, kwargs pass-through, duplicate registration, type-namespace isolation, sorted list output, error recovery, and default registry completeness

### Blockers
- Quality checks (ruff, mypy, pytest) must be run by Jonathan on his Mac before merging: `git merge scheduled/2026-02-28-registry-integration-tests`

### Next Up
- Phase 1C: Implement MeetingDialer (outbound call + DTMF meeting code entry)

---

## 2026-02-27 — Local/Free Providers, Mock Providers, Provider Docs

**Roadmap items:** Local providers for API-free development, mock providers for testing, provider setup documentation
**Branch:** main
**Author:** Jonathan (manual session with Claude Code)

### Changes

**New providers (4):**
- `WhisperSTT` — Local STT using faster-whisper (CTranslate2), no API key, CPU-optimized int8 inference
- `PiperTTS` — Local TTS using Piper ONNX neural voices, no API key, on-device synthesis
- `OllamaLLM` — Local LLM via Ollama REST API (httpx), no API key, default model: mistral
- `GroqLLM` — Free-tier cloud LLM using Groq SDK (AsyncGroq), LPU hardware, default model: llama-3.1-8b-instant

**Mock providers for testing:**
- `MockSTT`, `MockTTS`, `MockLLM` — Deterministic test doubles that return pre-configured fixtures

**Registry updates:**
- Registered all 4 new providers (whisper, piper, ollama, groq) — total: 3 STT, 3 TTS, 3 LLM
- Updated `__init__.py` re-exports for stt/, tts/, llm/ subpackages

**Provider documentation (10 files in docs/providers/):**
- README.md — Provider matrix with comparison table
- Individual setup guides for all 10 providers (whisper, assemblyai, deepgram, piper, cartesia, elevenlabs, ollama, groq, anthropic)

**Configuration updates:**
- `.env.example` — Added OLLAMA_HOST, OLLAMA_MODEL, GROQ_API_KEY, GROQ_MODEL
- `pyproject.toml` — Added optional deps: whisper, piper, groq
- Removed `tests/__init__.py` from all packages to fix namespace collision with multiple test directories

### Quality Check Results
- ruff: ✅ No issues
- ruff format: ✅ All files formatted
- pytest: ✅ 96 passed, 0 failed (48 original + 48 new)

### Notes
- Initial Alembic migration still not generated (Docker not running)
- Optional deps (faster-whisper, piper-tts, groq) must be installed with `uv sync --all-extras` for full test coverage
- Groq provider requires free API key from console.groq.com (no credit card)

### Blockers
None

### Next Up
- Start Docker and generate initial Alembic migration
- Write integration tests for providers (requires running Ollama, Groq API key)

---

## 2026-02-27 — Phase 1A Bootstrap: Monorepo & Domain Models

**Roadmap items:** All Phase 1A items (16 of 17) + Phase 1B provider ABCs and implementations (7 of 8)
**Branch:** main
**Author:** Jonathan (manual session with Claude Code)

### Changes

**Documentation fixes:**
- Fixed `scheduled-tasks` → `cowork-tasks` path references in SETUP_GUIDE.md and cowork-tasks/README.md
- Renamed ROADMAP-TASKLIST.md → TASKLIST.md, updated all references across docs
- Added CoWork Edit Protocol section to TASKLIST.md
- Updated VISION.md with "Giving Agents a Seat at the Table" section
- Replaced bootstrap CLAUDE.md with project conventions CLAUDE.md
- Moved bootstrap instructions to docs/BOOTSTRAP_REFERENCE.md

**Root configuration:**
- pyproject.toml (uv workspace with 7 members)
- docker-compose.yml (PostgreSQL 16 pgvector + Redis 7)
- .env.example, ruff.toml, mypy.ini
- .github/workflows/ci.yml (lint, type-check, test with services)
- .gitignore

**Packages:**
- `packages/convene-core/` — Pydantic v2 domain models (Meeting, Participant, Task, Decision, TranscriptSegment, AgentConfig), event definitions (6 event types), provider ABCs (STT, TTS, LLM), SQLAlchemy ORM models, Alembic config, async session factory
- `packages/convene-providers/` — STT (AssemblyAI, Deepgram), TTS (Cartesia, ElevenLabs), LLM (Anthropic), provider registry
- `packages/convene-memory/` — Working (Redis), short-term (SQL), long-term (pgvector), structured memory layers

**Services:**
- `services/api-server/` — FastAPI app with health check, meeting/task/agent CRUD routes, DI, CORS middleware
- `services/audio-service/` — Twilio handler, audio pipeline (mulaw→PCM16), meeting dialer
- `services/task-engine/` — Task extractor, deduplicator, health check
- `services/worker/` — Slack bot, calendar sync, notification service

**Tests:**
- 48 tests: 32 model tests + 16 event tests — all passing

### Quality Check Results
- ruff: ✅ No issues
- ruff format: ✅ All files formatted
- pytest: ✅ 48 passed, 0 failed

### Notes
- Initial Alembic migration not generated (requires running database)
- Provider registry integration tests deferred (requires API keys)
- `from __future__ import annotations` requires `model_rebuild()` on Pydantic models that reference other models in events
- All workspace packages need `[tool.hatch.build.targets.wheel] packages = ["src/package_name"]` for hatchling to find src layout

### Blockers
None

### Next Up
- Create initial Alembic migration (requires `docker compose up -d`)
- Write integration tests for provider registry
