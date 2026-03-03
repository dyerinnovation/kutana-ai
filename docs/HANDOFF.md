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
**Date:** 2026-03-01
**What I did:** Implemented the Redis Streams consumer (`StreamConsumer`) for `transcript.segment.final` events in the task-engine service. Replaced the sleep-based placeholder in `main.py` with a real XREADGROUP consumer group loop with exponential back-off reconnection and per-entry XACK. Added 20 unit tests.
**Branch:** scheduled/2026-03-01-redis-streams-consumer
**Merge status:** Branch committed locally — CoWork could not push (no GitHub credentials in VM). Run `git push origin scheduled/2026-03-01-redis-streams-consumer` from your Mac, then merge after quality checks pass
**Warnings:**
- ⚠️ **Quality checks were not run** — the CoWork Linux VM only has Python 3.10 and the `.venv` is a macOS ARM64 environment. Before merging, run on your Mac: `uv run ruff check . && uv run ruff format --check . && uv run mypy --strict . && uv run pytest -x -v`
- The branch is based on `scheduled/2026-02-28-registry-integration-tests` (which has the registry integration tests not yet merged to main). Rebase onto main or merge in order after pushing both branches.
- Docker must be running for database access: `docker compose up -d`
- Optional deps must be installed separately: `uv sync --all-extras` to get faster-whisper, piper-tts, groq
**Dependencies introduced:** None (redis>=5.0 was already declared in task-engine/pyproject.toml)

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
