# Plan: Post-Session Cleanup — Tech Debt Fixes + Docs Reorganization

**Date:** 2026-02-28

## Context

The weekly architecture review (`docs/WEEKLY_REVIEW.md`) identified 8 technical debt items. This plan fixes the actionable ones, adds groq to root dev-deps to fix test failures, and reorganizes `docs/` into a cleaner structure.

## Work Items

### 1. Fix Groq Test Failures
- Add `"groq>=0.11"` to root `pyproject.toml` dev-dependencies
- Run `uv sync --all-packages`

### 2. Fix Blocking Twilio Call (Tech Debt #1 — HIGH)
- Wrap `self._client.calls.create(...)` in `asyncio.to_thread()` in `meeting_dialer.py`

### 3. Fix Session Factory Per-Request (Tech Debt #2 — HIGH)
- Add `@lru_cache` to `_build_session_factory()` in `deps.py`

### 4. Add `close()` to TTSProvider ABC (Tech Debt #3 — MEDIUM)
- Add abstract `close()` to `tts.py` interface
- Add implementation in `piper_tts.py`

### 5. Add Explanations to `# type: ignore` Comments (Tech Debt #4 — MEDIUM)
- 5 files with bare `# type: ignore` comments

### 6. Fix Bare `list` Types in ORM Models (Tech Debt #5 — LOW)
- 4 instances of `Mapped[list | None]` → `Mapped[list[str] | None]`

### 7. Reorganize docs/ Directory
- Move agent output files to `docs/cowork-task-output/`
- Move reference docs to `docs/technical/`
- Update references in cowork-tasks and SETUP_GUIDE.md

## NOT Fixing (deferred)
- Tech Debt #6 (Task status transition validation) — Phase 1E
- Tech Debt #7 (Task persistence placeholder) — Phase 1D
- Tech Debt #8 (`tool.uv.dev-dependencies` deprecation) — separate cleanup
