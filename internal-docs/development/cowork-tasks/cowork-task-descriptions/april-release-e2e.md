# April Release E2E Test Sprint

> **Purpose**: Run the 4 multi-party E2E scenarios for the April release milestone (M_APRIL).
> **When to use**: Week 3 of April release sprint (Apr 5-11, 2026), after all backend and frontend work is merged.
> **Trigger**: Jonathan assigns this task manually — do not start until all `April Release Sprint` blocks in TASKLIST.md are checked off.

---

## Pre-Flight

```bash
# Pull latest
git pull origin main

# Verify all services healthy
ssh dgx 'docker compose -f ~/kutana-ai/docker-compose.yml ps'

# Verify migrations current
ssh dgx 'cd ~/kutana-ai && uv run alembic current'

# Run existing test suite
uv run pytest -x -v
```

If any pre-flight step fails, stop. Document in HANDOFF.md and notify Jonathan.

---

## What This Task Does

Runs the 4 E2E scenarios defined in `docs/milestone-testing/M_APRIL_E2E_Test.md`:

- **Scenario A**: 1 human + 1 agent
- **Scenario B**: 2 humans + 1 agent
- **Scenario C**: 1 human + multiple agents
- **Scenario D**: multiple humans + multiple agents

For each scenario, verify the acceptance criteria from the playbook:
- Turn management (raise hand → queue → speak → finish)
- Chat (send → receive → history)
- Meeting status snapshot accuracy
- No service errors

---

## How to Test

This is **functional testing**, not unit testing. You are verifying integration behavior by:

1. Using API calls to set up meetings and participants
2. Opening WebSocket connections to simulate agents (use test scripts if available in `tests/e2e/`)
3. Verifying responses match expected state
4. Checking service logs for errors

```bash
# Check if E2E test scripts exist
ls tests/e2e/ 2>/dev/null || echo "No E2E test dir — use API calls manually"

# Run E2E tests if they exist
uv run pytest tests/e2e/ -v --timeout=60

# If no E2E tests: use httpx/websockets to script the scenarios
# See docs/manual-testing/E2E_Gateway_Test.md for the pattern
```

If automated E2E tests don't exist for a scenario, script it manually using the same pattern as `docs/manual-testing/E2E_Gateway_Test.md`. Document any manual steps in the progress log.

---

## Pass / Fail Criteria

**Pass** — all of the following:
- [ ] All 4 scenarios complete without WebSocket errors
- [ ] Turn queue ordering is correct (timestamp-ordered, atomic)
- [ ] Chat messages delivered to all participants
- [ ] `get_meeting_status` returns accurate real-time snapshot
- [ ] No ERROR logs in any service during test
- [ ] `uv run pytest -x -v` passes (existing suite, not just E2E)

**Fail** — any of the following:
- Service crash or unrecoverable error during scenario
- Wrong queue order (position 2 gets turn before position 1)
- Chat messages not delivered or missing attribution
- Test suite regressions

---

## Output

After testing:

1. **If all scenarios pass:**
   - Check off M_APRIL in `docs/TASKLIST.md`
   - Append entry to `docs/PROGRESS.md`
   - Update `docs/HANDOFF.md` with: launch state, what was verified, any caveats

2. **If any scenario fails:**
   - Do NOT check off M_APRIL
   - Document exactly which scenario failed, what the expected vs. actual behavior was
   - Append to `docs/PROGRESS.md` with blocker note
   - Update `docs/HANDOFF.md` with failure details for Jonathan

---

## Hard Rules

- **Read-only for failing tests**: If a scenario fails, do not attempt to fix code in this session. Document and stop.
- **One fix allowed**: If a scenario fails due to a trivial configuration issue (wrong env var, missing migration), fix that specific thing and re-run. If it fails again, stop.
- **Never force-push** or modify PROGRESS.md entries.
- **Do not modify** `docs/milestone-testing/M_APRIL_E2E_Test.md` — it is the source of truth.
