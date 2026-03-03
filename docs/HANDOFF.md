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
**What I did:** Updated all documentation to reflect Agent Gateway M3 completion, DGX Whisper fix (httpx→aiohttp), audio-service test fixes, and E2E verification. Merged `scheduled/2026-03-01-redis-streams-consumer` to `main` and pushed. Deleted stale `scheduled/2026-02-28-registry-integration-tests` branch (work superseded by current branch's expanded registry tests).
**Branch:** merged to main
**Merge status:** Merged to main (fast-forward). Remote pushed.
**Warnings:**
- ⚠️ **AudioBridge cross-service import** (`agent-gateway/audio_bridge.py` imports from `audio-service`) is known tech debt — noted in WEEKLY_REVIEW. Should be extracted to a shared package before the two services diverge further.
- `scheduled/2026-02-28-registry-integration-tests` branch deleted — its registry integration tests were already included in the merged branch.
**Dependencies introduced:** `aiohttp` (replaced `httpx` in WhisperRemoteSTT — httpx hangs on `.local` mDNS hosts due to missing Happy Eyeballs support)

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
