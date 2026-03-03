# Plan: TASKLIST Rewrite, CoWork Block Support & Skipped Steps Resolution

**Date:** 2026-03-02
**Branch:** `feature/2026-03-02-tasklist-rewrite`
**Author:** Jonathan + Claude Code

## Context

The Convene AI project has pivoted from a Twilio dial-in bot to an agent-first meeting platform. Significant implementation has landed (Agent Gateway M3 verified, 58 gateway + 38 audio-service tests), but `docs/TASKLIST.md` still reflects the old architecture with obsolete phases. Several Phase 1C items were checked off despite files being intentionally deleted. The CoWork daily-build system is limited to one task per session, which is too slow for blocks of related work.

## Objectives

1. **Full rewrite of `docs/TASKLIST.md`** — Replace the old 7-phase structure with a new 10-phase structure aligned with the agent-first product vision
2. **CoWork block support** — Update `daily-build.md` to handle `🔗 BLOCK:` multi-task items in a single session
3. **Architecture doc updates** — Update `CLAUDE.md`, `docs/README.md`, and `docs/HANDOFF.md` for consistency with new phase numbering

## Files to Modify

| File | Change |
|------|--------|
| `docs/TASKLIST.md` | Full rewrite — new 10-phase structure |
| `docs/cowork-tasks/cowork-task-descriptions/daily-build.md` | Add block work support |
| `CLAUDE.md` | Update current phase, add agent modality notes |
| `docs/README.md` | Update phase descriptions |
| `docs/HANDOFF.md` | Update latest handoff |

## Key Decisions

- Collapse completed 1A/1B/1C into "Completed Foundation" section
- Mark deprecated Twilio items with `(deprecated — removed in agent-first refactor)`
- Use `🔗 BLOCK:` prefix for multi-task items that CoWork should handle as a unit
- New phase ordering: Core AI Pipeline → Agent Platform → MCP/SDK → Auth/Billing → Meeting Platform → Memory → Cloud → Voice → Ecosystem → Hardening
- Agent modalities: Voice-to-Voice, Speech-to-Text, Text-only

## Verification Checklist

- [ ] New TASKLIST has all completed items properly marked
- [ ] Deprecated items annotated
- [ ] Phase numbering is sequential
- [ ] Block syntax (🔗) used for multi-task items
- [ ] daily-build.md supports blocks
- [ ] CLAUDE.md and docs/README.md consistent with new phases
- [ ] All changes on feature branch
