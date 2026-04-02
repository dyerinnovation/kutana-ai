# Weekly Architecture Review — Week of 2026-03-16

## Week Summary
No new code has landed since the last progress entry on 2026-03-03 (transcript segment windowing). The LLM-powered task extraction pipeline remains locked by Jonathan, blocking Phase 1 completion. Phase 2 Agent Gateway core (M3) is verified and stable, but the three follow-on blocks (Polish, Registration & Credentials, Modality Support) are untouched. Overall trajectory is stalled — the project needs either the extraction pipeline unlocked for CoWork or a manual push from Jonathan to regain momentum. Two weeks without a merge is the longest gap since project inception.

## Architecture Compliance

### Provider Abstraction
- **Status:** ✅ Compliant
- **Details:** All 10 providers (4 STT, 3 TTS, 3 LLM) correctly extend their ABCs in `packages/kutana-core/src/kutana_core/interfaces/`. All are registered in `packages/kutana-providers/src/kutana_providers/registry.py` (lines 140-153). No direct imports of concrete providers found in service code — services exclusively use the registry factory pattern. **Carried forward (3 weeks):** `LLMProvider` ABC still lacks an abstract `close()` method, though all 3 concrete implementations (AnthropicLLM:322, GroqLLM:268, OllamaLLM:259) define one. `STTProvider` and `TTSProvider` ABCs both define `close()` — this inconsistency should be resolved.

### Event-Driven Communication
- **Status:** 🛑 Violations found (unchanged from last week)
- **Details:** Two violations persist:
  1. **Cross-service import:** `services/agent-gateway/src/agent_gateway/audio_bridge.py` (lines 10-12) directly imports `AudioPipeline`, `EventPublisher`, and `_create_stt_provider` from `audio-service`. The `agent-gateway/pyproject.toml` also declares `audio-service` as a workspace dependency — a service-to-service coupling that violates the event-driven principle.
  2. **Ad-hoc event publishing:** `services/agent-gateway/src/agent_gateway/agent_session.py` (lines 218-224) publishes raw `data.channel.{name}` events via direct XADD instead of using the `AgentData` event class from `kutana_core/events/definitions.py`.
  The audio-service → task-engine path is correctly wired via EventPublisher and StreamConsumer with proper XREADGROUP/XACK semantics. 13 event types are defined; only 3 are actively published (`meeting.started`, `meeting.ended`, `transcript.segment.final`). The remaining 10 have no publishers or consumers yet.

### Async Correctness
- **Status:** ⚠️ Minor issues (unchanged)
- **Details:** No `time.sleep()` or synchronous HTTP usage found. All database operations use async SQLAlchemy with `await db.execute()`. **Persistent issue (3 weeks):** `packages/kutana-providers/src/kutana_providers/stt/whisper_remote_stt.py` (lines 101-108) performs synchronous file I/O (`wave.open`, `open/read`) inside `async def get_transcript()`, blocking the event loop. The sibling `whisper_stt.py` correctly uses `asyncio.to_thread()` at line 128 — the fix pattern already exists in the codebase. Minor: `services/api-server/src/api_server/rate_limit.py` (line 74) uses `time.time()` in an async dispatch method — functionally harmless.

### Type Safety
- **mypy results:** Cannot run — CoWork Linux VM has Python 3.10; project requires 3.12+ and `.venv` contains macOS ARM64 binaries.
- **Problem areas:** Syntax validation via `ast.parse` passes on all 132 Python files. All 25 `# type: ignore` comments have inline explanations per CLAUDE.md convention. 5 pytest fixtures in `services/agent-gateway/tests/` lack return type hints: `test_audio_bridge.py` (lines 13, 21, 36) and `test_event_relay_transcript.py` (lines 14, 20). Jonathan should run `uv run mypy --strict .` locally to validate.

### Test Coverage
- **Overall:** 16 test files, ~313 test functions across the codebase. Last confirmed run (2026-03-02): 96+ tests passing (58 gateway + 38 audio-service). Additional test files cover core models/events (2), providers (2), task-engine (2), and CLI (1).
- **Gaps:**
  - `packages/kutana-memory/` — **0 test files** (4 memory layer implementations untested)
  - `services/api-server/` — **0 test files** (routes, deps, auth, rate limiter untested)
  - `services/worker/` — **0 test files** (notifications, slack_bot, calendar_sync untested)
  - `services/mcp-server/` — **0 test files** (MCP tools, gateway client untested)
  - Cloud STT/TTS providers have no unit tests (expected — require API keys)

### Code Organization
- **Status:** ✅ Clean
- **Details:** Pydantic domain models correctly in `kutana-core/models/` (10 model files). ORM models in `kutana-core/database/models.py` with additional structured memory models alongside `kutana-memory`. API route handlers are thin CRUD stubs — no business logic leaks detected. All Python files follow snake_case naming. Google-style docstrings present on public methods. No circular dependencies between packages. All workspace packages use `{ workspace = true }` references with `>=` version constraints for externals.

## Technical Debt Identified

1. **Cross-service import + dependency: agent-gateway → audio-service** — **Severity:** High — **Suggested fix:** Extract shared audio pipeline logic into `kutana-core` or a new `kutana-audio` shared package. Remove `audio-service` from `agent-gateway/pyproject.toml`. Files: `services/agent-gateway/src/agent_gateway/audio_bridge.py:10-12`, `services/agent-gateway/pyproject.toml`. **Carried forward 3 weeks — this is now the longest-standing architectural violation.**

2. **LLMProvider ABC missing `close()` method** — **Severity:** Medium — **Suggested fix:** Add `@abstractmethod async def close(self) -> None` to `packages/kutana-core/src/kutana_core/interfaces/llm.py`, then add `close()` to `MockLLM` in `kutana_providers/testing.py`. **Carried forward 3 weeks.**

3. **Blocking file I/O in WhisperRemoteSTT** — **Severity:** Medium — **Suggested fix:** Wrap `wave.open()` and file read/write in `asyncio.to_thread()` at `packages/kutana-providers/src/kutana_providers/stt/whisper_remote_stt.py:101-108`. Fix pattern exists in `whisper_stt.py:128`. **Carried forward 3 weeks.**

4. **Ad-hoc event publishing in agent_session.py** — **Severity:** Medium — **Suggested fix:** Use the `AgentData` event class from `kutana_core/events/definitions.py` instead of raw XADD with `data.channel.{name}` at `services/agent-gateway/src/agent_gateway/agent_session.py:221`. **Carried forward 2 weeks.**

5. **Zero test coverage for memory, api-server, worker, mcp-server** — **Severity:** Medium — **Suggested fix:** Prioritize `kutana-memory` unit tests before Phase 6 memory tasks. API server and worker tests should be added as those services get real implementations.

6. **5 pytest fixtures missing type hints** — **Severity:** Low — **Suggested fix:** Add return type annotations to fixtures in `test_audio_bridge.py` (lines 13, 21, 36) and `test_event_relay_transcript.py` (lines 14, 20).

7. **CoWork quality gate limitation** — **Severity:** Low — **Suggested fix:** CoWork VM cannot run ruff/mypy/pytest due to Python 3.10 + macOS ARM64 .venv mismatch. Add CI auto-check on `scheduled/*` branches. **Carried forward 3 weeks.**

## Refactoring Priorities for Next Week

1. **Fix cross-service import in audio_bridge.py** — This is the only architectural violation in the codebase and has now persisted for 3+ weeks. Extract the AudioPipeline/EventPublisher dependency into a shared package or have agent-gateway use the provider registry directly. This is explicitly listed in the TASKLIST as a standalone item under Phase 2.

2. **Add `close()` to LLMProvider ABC + MockLLM** — Quick 5-minute fix that standardizes resource cleanup across all provider types. No reason to carry this forward a fourth week.

3. **Wrap WhisperRemoteSTT file I/O** — Small targeted fix. The exact pattern already exists in `whisper_stt.py`. Prevents event loop blocking under concurrent transcription load.

4. **Standardize agent-gateway event publishing** — Use the defined `AgentData` event class instead of ad-hoc XADD calls.

5. **Unlock or complete the LLM extraction pipeline** — Phase 1 completion is blocked on this single locked item. If Jonathan's work is paused, unlocking it would let CoWork finish Phase 1.

## ROADMAP.md Suggestions

- The locked Phase 1 item (LLM-powered task extraction pipeline) has been blocking Phase 1 completion for 2+ weeks. Consider unlocking it for CoWork to complete, or provide a design doc so CoWork can implement it.
- The tech debt item "Refactor AudioBridge cross-service import" is already in the TASKLIST under Phase 2 — consider promoting it to be the next unlocked item, since it's been flagged for 3 consecutive weekly reviews.
- Phase 2 blocks (Agent Gateway Polish, Agent Registration & Credentials, Agent Modality Support) are large multi-task blocks. Consider breaking them into smaller independently-shippable tasks to improve CoWork throughput.
- Phase 3 MCP Server block lists tasks that may already be partially implemented (`services/mcp-server/` exists with tools, gateway client, auth). Reconcile the TASKLIST with actual code state to avoid duplicate work.
- Consider adding a "Tech Debt Sprint" phase between Phase 2 and Phase 3 to address the accumulated items before adding more features.

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Cross-service import creates hidden coupling; audio-service changes break agent-gateway silently | High | High | Extract shared pipeline into kutana-core or new shared package. **3 weeks unresolved — escalating likelihood.** |
| CoWork PRs merge without quality checks (ruff, mypy, pytest can't run in VM) | High | Med | Add CI auto-check on `scheduled/*` branches; block merge until green |
| Phase 1 stalls indefinitely due to locked extraction pipeline task | High | High | Unlock task for CoWork if Jonathan's work is paused. **Now 2+ weeks with no progress on this item.** |
| Memory layer implementation begins (Phase 6) without test foundation | Med | Med | Write memory layer unit tests proactively |
| WhisperRemoteSTT blocks event loop under concurrent transcription load | Med | Med | Wrap file I/O in asyncio.to_thread() — fix pattern exists in codebase |
| 10 of 13 defined events never published — event schema may drift from implementation | Low | Med | Add event publishing as services implement features; review event definitions quarterly |
| Tech debt items carried forward 3+ weeks without resolution | Med | Med | Dedicate a session to clearing top-3 debt items before starting new feature work |
