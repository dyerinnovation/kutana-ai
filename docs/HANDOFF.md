# Convene AI — Handoff Notes

> This file is the shift-change log between Jonathan and CoWork scheduled tasks.
> Before starting any work, READ THIS FILE to understand the current state.
> After finishing work, OVERWRITE this section with your handoff notes.
>
> Think of it like passing a baton — the next person (human or AI) needs to know
> what just happened and what to watch out for.

---

## Latest Handoff

**Author:** CoWork (scheduled)
**Date:** 2026-02-28
**What I did:** Expanded the provider registry integration test suite from 8 to 20 tests, covering full provider lifecycles (STT/TTS/LLM), registry behaviour edge cases (type-namespace isolation, error recovery, sorted list output), and a new `TestDefaultRegistry` class that smoke-tests all 4 instantiable providers and verifies all 9 are registered.
**Branch:** scheduled/2026-02-28-registry-integration-tests
**Merge status:** Ready for review — run `git merge scheduled/2026-02-28-registry-integration-tests` after verifying quality checks
**Warnings:**
- ⚠️ **Quality checks were not run** — the CoWork Linux VM only has Python 3.10 and the `.venv` is a macOS ARM64 environment. Before merging, run on your Mac: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest -x -v`
- Docker must be running for database access: `docker compose up -d`
- Optional deps must be installed separately: `uv sync --all-extras` to get faster-whisper, piper-tts, groq
- The `from __future__ import annotations` + Pydantic v2 pattern requires `model_rebuild()` calls — see `events/definitions.py`
- `tests/__init__.py` files were removed from all packages to fix namespace collision — do NOT re-add them
- Groq is recommended for local dev (free tier, fastest inference, no credit card needed)
**Dependencies introduced:** None

---

## Handoff Protocol

When writing your handoff, include:

1. **Author** — "Jonathan" or "CoWork (scheduled)"
2. **Date** — When you finished
3. **What I did** — 1-2 sentence summary
4. **Branch** — Which branch your work is on
5. **Merge status** — "Merged to main" or "Ready for review on branch X"
6. **Warnings** — Anything the next session MUST know (incomplete work, fragile code, don't touch X)
7. **Dependencies introduced** — Any new packages added
