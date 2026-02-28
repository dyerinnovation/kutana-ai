# Convene AI — Development Progress Log

> Append-only log of completed work. Each entry is written by whoever completed
> the work — either CoWork (scheduled) or Jonathan (manual session).
> Never delete or overwrite previous entries.

---

<!-- New entries go at the top -->

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
