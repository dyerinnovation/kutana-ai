# Summary: Wire STT Provider into Audio Service

## Date: 2026-02-28

## Work Completed

- Created `WhisperRemoteSTT` provider (`packages/kutana-providers/src/kutana_providers/stt/whisper_remote_stt.py`)
  - Remote Whisper STT that POSTs WAV files to vLLM OpenAI-compatible API
  - Handles both `verbose_json` (with segments) and plain text responses
  - Properly converts `avg_logprob` to 0.0-1.0 confidence range via `math.exp()`
- Registered `whisper-remote` in provider registry and exported from `stt/__init__.py`
- Added STT configuration fields to `AudioServiceSettings` (`stt_provider`, `stt_api_key`, `whisper_model_size`, `whisper_api_url`)
- Created `_create_stt_provider()` factory function with provider-specific kwargs and validation
- Replaced `_stt_provider = None` global with `_settings` pattern for per-connection STT creation
- Updated `lifespan()` to validate STT config at startup (create + close test provider)
- Updated `/audio-stream` endpoint to create fresh STT provider per WebSocket connection
- Created 22 unit tests in `test_stt_wiring.py` (settings, factory, lifespan, endpoint)
- Created 3 Redis integration tests in `test_redis_integration.py` (lifecycle events, no-publisher, multi-meeting)
- Updated provider count assertions in existing tests (`test_local_providers.py`, `test_registry_integration.py`)
- Checked off TASKLIST item "Wire STT provider into audio service lifespan"
- Created `claude_docs/UV_Best_Practices.md` and referenced from CLAUDE.md

## Work Remaining

- Next TASKLIST items in Phase 1D:
  - Implement Redis Streams consumer for `transcript.segment.final` events
  - Implement transcript segment windowing (3-5 min windows with overlap)
  - Complete LLM-powered task extraction pipeline
  - Milestone M1 (Audio → Transcript → Redis) can be checked off — integration test passes
  - Milestone M2 (Redis → Task Extraction → PostgreSQL) still needs task extraction pipeline

## Lessons Learned

- **macOS `UF_HIDDEN` breaks Python 3.13 `.pth` files:** Python 3.13 introduced a security fix that skips `.pth` files with the `UF_HIDDEN` flag. If `.venv` gets hidden (Finder, Time Machine, manual `chflags`), all workspace member imports break silently. Fix: `chflags -R nohidden .venv`
- **TranscriptSegment confidence validator requires 0.0-1.0:** Whisper's `avg_logprob` is negative, so it must be converted (e.g. `math.exp()`) before passing to `TranscriptSegment`
- **Per-connection STT is critical:** STT providers maintain per-connection state (WebSocket connections, audio buffers), so a shared global instance would break with concurrent meetings
- **Never use `uv pip` subcommands:** `uv pip list`, `uv pip install` operate in a different resolver context than `uv add`/`uv sync` and give incorrect results
- **httpx already a dependency:** `kutana-providers` already has `httpx>=0.27` in its dependencies, so no additional `uv add` was needed for the remote Whisper provider
