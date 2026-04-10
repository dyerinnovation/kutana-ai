# Eval Reports Rule

Every managed-agents eval run or debugging session produces a markdown report in `eval_outputs/YYYY-MM-DD/<slug>.md` at the repo root.

## When

- After completing a run of `/run-eval-job` (pass or fail)
- After any debugging session that found bugs in the eval path, api-server, or agent-lifecycle code
- After making an infra change that affects activation, vaults, sessions, MCP, or the transcript relay

## File location

```
eval_outputs/
├── 2026-04-10/
│   ├── 2026-04-10-managed-agents-investigation.md
│   └── 2026-04-10-scenario-run-meeting-notetaker.md
├── 2026-04-11/
│   └── 2026-04-11-audio-pipeline-smoke.md
```

`eval_outputs/` is gitignored. Reports stay on the machine that ran the session.

## Required structure

```
# <Title> — YYYY-MM-DD

One-paragraph summary: what was tested, what the outcome was.

## Context
- What prompted this run/investigation
- What state the system was in going in

## Bugs found
For each bug:
### N. <Short bug title>
**Root cause:** ...
**Fix:** file:line — before → after
**Commit:** <sha>
**Verified:** <how>

## Results
- Eval job exit code
- Per-scenario: score, judge summary, event counts, session ID
- api-server log confirmation lines

## Deliverables shipped
- Commits
- Skills added/updated
- Config/infra changes

## Open decisions
Things needing a human call — agent design, rubric tuning, scope questions.

## Next action
What happens next, who's doing it.
```

## Don't

- Commit `eval_outputs/` to git
- Write reports anywhere other than `eval_outputs/YYYY-MM-DD/`
- Skip the "Bugs found" section even if the run was clean — write "No bugs found this run" explicitly
- Dump raw logs into the report — summarize and link commits instead
