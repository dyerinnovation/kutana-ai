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
**Date:** 2026-03-21
**What I did:** Replaced the ORM placeholder in `TaskExtractor._persist_tasks` with a real `TaskORM` insert, updated `TaskDeduplicator._fetch_existing_descriptions` to use a typed ORM query instead of raw SQL, and wrote 25 unit tests across two new test files.
**Branch:** scheduled/2026-03-21-task-persistence-v2
**Merge status:** Ready for review — do `git merge scheduled/2026-03-21-task-persistence-v2` after running quality checks on Mac
**Warnings:**
- ⚠️ Quality checks (ruff, mypy, pytest) must be run on Mac before merging — VM Python is 3.10, project requires 3.12+
- ruff check passes on the 4 modified files; full-repo scan hits a filesystem deadlock on api-server/pyproject.toml (pre-existing VM issue)
- The `_on_window` handler in `main.py` is still a logging stub — next locked task (LLM extraction pipeline) wires it up
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
