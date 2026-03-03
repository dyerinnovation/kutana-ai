# Convene AI — Handoff Notes

> This file is the shift-change log between Jonathan and CoWork scheduled tasks.
> Before starting any work, READ THIS FILE to understand the current state.
> After finishing work, OVERWRITE this section with your handoff notes.
>
> Think of it like passing a baton — the next person (human or AI) needs to know
> what just happened and what to watch out for.

---

## Latest Handoff

**Author:** Jonathan (manual session with Claude Code)
**Date:** 2026-03-02
**What I did:** Full rewrite of `docs/TASKLIST.md` — replaced old 7-phase structure with new 10-phase structure aligned with agent-first product vision. Added `🔗 BLOCK:` multi-task support to CoWork daily-build. Updated `CLAUDE.md`, `docs/README.md` for consistency with new phase numbering. Added agent modality notes (V2V, S2T, text-only) and Claude Agent SDK → MCP Server → Gateway connection pattern.
**Branch:** `feature/2026-03-02-tasklist-rewrite`
**Merge status:** Ready for review — do `git merge feature/2026-03-02-tasklist-rewrite` after reviewing
**Warnings:**
- ⚠️ **AudioBridge cross-service import** (`agent-gateway/audio_bridge.py` imports from `audio-service`) is known tech debt — now tracked as explicit item in Phase 2.
- Phase 1C deprecated items (MeetingDialer, TwilioHandler, meeting end detection) are annotated but kept checked off for historical record.
- CoWork daily-build now supports `🔗 BLOCK:` items — ensure all scheduled sessions use the updated `daily-build.md`.
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
