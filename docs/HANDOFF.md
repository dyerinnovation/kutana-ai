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
**Date:** 2026-03-03
**What I did:** Implemented transcript segment windowing — created `SegmentWindower` and `SegmentWindow` in `task_engine/windower.py`, wired windower into `main.py` between `StreamConsumer` and the `_on_window` logging stub, and wrote 22 unit tests.
**Branch:** scheduled/2026-03-03-transcript-segment-windowing
**Merge status:** Ready for review — do `git merge scheduled/2026-03-03-transcript-segment-windowing` after running quality checks on Mac
**Warnings:**
- ⚠️ Quality checks (ruff, mypy, pytest) must be run on Mac before merging — `.venv` is macOS ARM64 and won't execute in this Linux VM
- The `_on_window` handler in `main.py` is still a logging stub — next task wires the actual LLM extractor
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
