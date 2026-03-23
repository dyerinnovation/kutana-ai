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
**Date:** 2026-03-22
**What I did:** Completed the LLM-powered task extraction pipeline by adding cross-window context continuity (`_context_cache`) to `_on_window` in the task-engine, and wrote 27 unit tests for `test_main.py` covering all pipeline branches.
**Branch:** scheduled/2026-03-22-llm-extraction-pipeline
**Merge status:** ❌ Merge FAILED — branch left unmerged for manual review (push and quality checks required on Mac)
**Warnings:**
- ⚠️ Quality checks (ruff, mypy, pytest) must be run on Mac before merging — VM Python is 3.10, project requires 3.12+. Push the branch from Mac with `git push origin scheduled/2026-03-22-llm-extraction-pipeline`, run checks, then merge to main.
- Syntax check (py_compile Python 3.10) passed for all changed files
- Next item is Milestone M2 (integration test) — requires running PostgreSQL and Redis
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
