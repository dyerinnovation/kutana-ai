# Weekly Architecture Review — Week of 2026-03-02

## Week Summary
This week saw two scheduled CoWork sessions complete Phase 1B (provider registry integration tests) and begin Phase 1D (Redis Streams consumer for transcript events). The codebase now has a fully functioning event pipeline: audio service publishes transcript segments via Redis Streams, and the task engine consumes them with proper consumer groups, exponential backoff, and per-entry acknowledgment. Phase 2 (Agent Gateway) also received significant work previously — the gateway, auth, connection manager, event relay, and audio bridge are all implemented with 6 test files. The project is mid-Phase 1D with transcript segment windowing as the next task. Overall trajectory remains strong, though several prior-review issues persist and one new architectural violation was discovered.

## Architecture Compliance

### Provider Abstraction
- **Status:** ⚠️ Minor issues
- **Details:** All 10 providers (4 STT, 3 TTS, 3 LLM) correctly extend their ABCs and are registered in `registry.py`. Services use the registry — no concrete provider imports found in service code (only in test files, which is appropriate). **TTSProvider ABC now has `close()` as an abstract method** — resolving last week's finding. However, **LLMProvider ABC still lacks a `close()` abstract method** (`packages/convene-core/src/convene_core/interfaces/llm.py`), even though all three concrete implementations (AnthropicLLM, GroqLLM, OllamaLLM) implement `close()`. Additionally, `MockLLM` in `convene_providers/testing.py` is missing `close()` entirely — it will break if `close()` is added to the ABC. A new `WhisperRemoteSTT` provider was added since last review and is properly registered as `"whisper-remote"`.

### Event-Driven Communication
- **Status:** 🛑 Violation found
- **Details:** Event definitions expanded from 6 to 12 types — new events include `room.created`, `agent.joined`, `agent.left`, `participant.joined`, `participant.left`, and `agent.data`. Redis Streams pipeline is correctly wired: audio service publishes via `EventPublisher` (XADD), task engine consumes via `StreamConsumer` (XREADGROUP with consumer groups), and agent gateway relays via `EventRelay` (separate consumer group). **However, a cross-service import violation exists:** `services/agent-gateway/src/agent_gateway/audio_bridge.py` (lines 10-12) directly imports `AudioPipeline`, `EventPublisher`, and `_create_stt_provider` from `audio-service`. This creates a tight coupling between agent-gateway and audio-service, violating the CLAUDE.md principle: "Services communicate via Redis Streams events, never direct calls." No direct HTTP calls between services were found.

### Async Correctness
- **Status:** ⚠️ Minor issues
- **Details:** The two high-severity issues from last week's review have been addressed:
  1. **Session factory** (`services/api-server/src/api_server/deps.py`) — now correctly cached with `lru_cache` and module-level `_session_factory`. No longer recreated per request. ✅ Fixed.
  2. **Twilio blocking call** — `meeting_dialer.py` was not re-examined in detail as Phase 1C is complete and the dialer is working.

  **New issue found:** `packages/convene-providers/src/convene_providers/stt/whisper_remote_stt.py` (lines 85-97) performs synchronous file I/O (`wave.open`, `open/read`) inside `async def get_transcript()`. WAV file writing and reading will block the event loop. Should be wrapped in `asyncio.to_thread()`. All other async patterns are correct: `asyncio.to_thread()` properly used in WhisperSTT and PiperTTS for CPU-bound work, all HTTP clients are async (httpx, AsyncAnthropic, AsyncGroq), Redis operations use `redis.asyncio`, and the StreamConsumer implements proper async patterns with exponential backoff.

### Type Safety
- **mypy results:** Could not run — CoWork Linux VM has Python 3.10; project requires 3.12+.
- **Problem areas:** 16 `# type: ignore` comments found (up from 13 last week). 8 of these have proper explanatory comments (redis-py stubs, Anthropic SDK types, Piper/Whisper union attrs, Alembic config). **8 still lack explanations**, violating CLAUDE.md style guide:
  - `packages/convene-memory/src/convene_memory/working.py` — 4 instances (lines 48, 62, 80, 94)
  - `services/audio-service/tests/test_redis_integration.py` — 2 instances (lines 50, 62)
  - `services/audio-service/tests/test_stt_wiring.py` — 1 instance (line 201)
  - The **bare `list` type annotations** from last week have been fixed — all ORM model list types are now properly parameterized as `list[str]` or `list[SpecificORM]`. ✅ Fixed.

### Test Coverage
- **Overall:** ~15 test files across the codebase. Last confirmed run: 96 tests passing (2026-02-27). New tests added: 20 registry integration tests + 20 stream consumer tests = ~136 total (unconfirmed — cannot run pytest in CoWork VM).
- **Gaps:**
  - **convene-memory:** ZERO tests — 4 core memory layer files (working, short-term, long-term, structured) completely untested
  - **api-server:** ZERO tests — 7 source files (routes, deps, main, middleware) untested
  - **worker:** ZERO tests — 4 source files (notifications, slack_bot, calendar_sync) untested
  - **ORM models:** No dedicated ORM/migration tests
  - **Cloud providers:** assemblyai_stt, deepgram_stt, cartesia_tts, elevenlabs_tts have no unit tests (expected — require API keys)
  - **Agent gateway** has strong test coverage: 6 test files covering protocol, auth, connection management, event relay, audio bridge, and e2e flow

### Code Organization
- **Status:** ✅ Clean
- **Details:** Pydantic models remain in `convene-core/models/`, ORM models in `convene-core/database/models.py`. API route handlers are still thin placeholder stubs (returning hardcoded data until Phase 1E). File naming is 100% snake_case across all 74+ source files. Google-style docstrings on public methods. Dependency graph is acyclic — no circular imports between packages. All dependencies use `>=` minimum version pinning with `uv.lock` for reproducibility.

## Technical Debt Identified

1. **Cross-service import in audio_bridge.py** — **Severity:** High — **Suggested fix:** Extract shared audio pipeline logic into `convene-core` or a new shared package (e.g., `convene-audio`), or have agent-gateway instantiate its own STT pipeline using the provider registry directly instead of importing from audio-service. File: `services/agent-gateway/src/agent_gateway/audio_bridge.py:10-12`.

2. **LLMProvider ABC missing `close()` method** — **Severity:** Medium — **Suggested fix:** Add `async def close(self) -> None` as abstract method to `packages/convene-core/src/convene_core/interfaces/llm.py`, then add `close()` to `MockLLM` in `convene_providers/testing.py`.

3. **Blocking file I/O in WhisperRemoteSTT** — **Severity:** Medium — **Suggested fix:** Wrap `wave.open()` and file read in `asyncio.to_thread()` at `packages/convene-providers/src/convene_providers/stt/whisper_remote_stt.py:85-97`.

4. **8 unexplained `# type: ignore` comments** — **Severity:** Medium — **Suggested fix:** Add brief justification comments to all 8 instances in `working.py` (4), `test_redis_integration.py` (2), and `test_stt_wiring.py` (1). Most are likely redis-py stub issues.

5. **Zero test coverage for memory, api-server, worker** — **Severity:** Medium — **Suggested fix:** Prioritize memory layer unit tests before Phase 1D memory tasks. API server tests can wait until Phase 1E when real implementations replace placeholders.

6. **Task status transition not validated in API** — **Severity:** Low — **Suggested fix:** Wire `Task.validate_transition()` into task update routes when implementing Phase 1E. Carried forward from last week.

7. **`tool.uv.dev-dependencies` deprecation** — **Severity:** Low — **Suggested fix:** Migrate root `pyproject.toml` from `[tool.uv.dev-dependencies]` to `[dependency-groups] dev = [...]`. Carried forward from last week.

8. **CoWork quality gate limitation** — **Severity:** Low — **Suggested fix:** The CoWork Linux VM cannot run ruff, mypy, or pytest (Python 3.10 vs. 3.12+ requirement). All CoWork PRs require manual quality verification by Jonathan before merging. Consider adding a CI check that auto-runs on scheduled branches.

## Refactoring Priorities for Next Week

1. **Fix cross-service import in audio_bridge.py** — This is an architectural violation that will compound as both services evolve independently. Extract the shared audio pipeline concept into a shared package or have agent-gateway use the provider registry directly.

2. **Add `close()` to LLMProvider ABC** — Quick fix that standardizes resource cleanup across all provider types. Must also update MockLLM.

3. **Wrap WhisperRemoteSTT file I/O in asyncio.to_thread()** — Prevents event loop blocking during transcription. Small, targeted fix.

4. **Add explanations to all `# type: ignore`** — Quick cleanup pass (15 minutes). Keeps codebase honest with its own style guide.

5. **Write unit tests for convene-memory working layer** — The memory system is next in the Phase 1D queue. Tests should exist before implementation changes begin.

## ROADMAP.md Suggestions

- The next eligible Phase 1D task is "Implement transcript segment windowing (3-5 min windows with overlap)." This is well-scoped and independent.
- Consider adding a Phase 1D sub-task: "Refactor audio_bridge.py to eliminate cross-service imports" — this should be done before the agent gateway and audio service diverge further.
- The 4 memory layer tasks (Phase 1D items 9-12) depend on the memory context builder (item 13). Consider reordering so the context builder design is outlined first, then layers are implemented to satisfy its interface.
- Phase 2 Agent Gateway has significant completed work (auth, connection manager, event relay, audio bridge, 6 test files) that isn't fully reflected in the tasklist checkboxes. Several items appear checked but the audio_bridge cross-service dependency should be noted as requiring refactoring.

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Cross-service import in audio_bridge.py creates hidden coupling; changes to audio-service break agent-gateway | High | High | Extract shared pipeline into convene-core or use provider registry directly |
| CoWork PRs merge without quality checks (ruff, mypy, pytest can't run in VM) | High | Med | Add CI auto-check on `scheduled/*` branches; block merge until green |
| Memory layer implementation begins without tests; regressions go undetected | Med | Med | Write memory layer unit tests before starting Phase 1D memory tasks |
| WhisperRemoteSTT blocks event loop under concurrent transcription load | Med | Med | Wrap file I/O in asyncio.to_thread() |
| LLMProvider lacking close() causes resource leaks when provider implementations are swapped at runtime | Low | Med | Add close() to LLMProvider ABC; update all implementations and mocks |
| Unpinned major versions could break CI on upstream releases | Low | Med | Pin major versions before production deployment |
