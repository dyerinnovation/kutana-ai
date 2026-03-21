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
**What I did:** Implemented task.created and task.updated event emission — added EventPublisher to task-engine and api-server, wired TaskCreated events out of TaskExtractor after persist, and wired TaskCreated/TaskUpdated out of the api-server task routes.
**Branch:** scheduled/2026-03-21-task-event-emission
**Merge status:** Ready for review — do `git merge scheduled/2026-03-21-task-event-emission` after quality checks pass on Mac
**Warnings:**
- ⚠️ Quality checks (ruff, mypy, pytest) must be run on Mac before merging — VM Python is 3.10, project requires 3.12+
- The task-engine `_event_publisher` is created in lifespan but NOT yet passed into TaskExtractor from `_on_window` — that wiring belongs in the locked LLM pipeline task
- `update_task_status` now stamps `updated_at` on every status change (this is a net improvement but is a behavior change)
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
