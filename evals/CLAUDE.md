# Evals — Managed Agents Only

This directory evaluates **real Anthropic managed agent sessions** against the live Kutana pipeline. It does NOT mock the agent, stub the MCP tool layer, or call the Anthropic Messages API directly to simulate an agent.

## What a run does

1. Creates a real meeting via `POST /v1/meetings`
2. Calls `PUT /v1/meetings/{id}/selected-agents` — snapshots the desired
   template list on the meeting row (Phase A.7 decoupled flow)
3. Drives synthetic presence: `SADD kutana:presence:{meeting_id} eval-stub-participant`
4. Calls `POST /v1/meetings/{id}/start` — transitions to ACTIVE and
   fires one background `_warm_agent_in_background` task per selection
5. Waits for the first `agent.session.warmed` event on the
   `kutana:events` stream to confirm the managed agent session is ready
6. Injects `transcript.segment.final` events into Redis `kutana:events`
7. `MeetingEventRelay` (in `services/api-server/src/api_server/agent_lifecycle.py`) forwards each segment to the live managed agent session
8. Agent events stream back through `agent_lifecycle.stream_and_publish_events` → Redis → `E2ERunner.observe_agent_events`
9. Judge scores the collected `agent.message` / `agent.mcp_tool_use` events + the final summary
10. Cleanup: `SREM` the presence entry so the reconciler doesn't keep the meeting warm

## How presence is driven in evals

The Phase A.7 `PresenceReconciler` (api-server, `agent_presence_heartbeat.py`)
runs every 30 s and shuts down every active managed-agent session for any
meeting with `SCARD(kutana:presence:{meeting_id}) == 0`. Evals have no
real participants, so the harness writes a synthetic entry directly:

```python
await redis.sadd(f"kutana:presence:{meeting_id}", "eval-stub-participant")
```

The write happens **before** `POST /meetings/{id}/start` so the reconciler
never sees an empty set while warms are in flight. The entry stays in
place for the full eval and is drained with `SREM` during cleanup (see
`E2ERunner.cleanup_meeting`).

If you see `Presence-reconciler: meeting X has no participants, stopping
N active session(s)` in the api-server logs during an eval run, the
eval forgot to call `mark_presence` before `start_meeting` — fix the
order of operations, don't relax the reconciler.

## Do NOT

- Call `client.messages.create()` directly to simulate an agent's response
- Stub MCP tool schemas to generate synthetic `tool_use` blocks
- Add a "mock mode" flag — if the live path is broken, fix the live path, don't shim around it
- Add pytest tests here — the harness runs as a K8s Job via `k8s_runner.py`, not pytest
- Call the deprecated `POST /v1/agent-templates/{id}/activate` — use
  `PUT /v1/meetings/{id}/selected-agents` + `POST /v1/meetings/{id}/start` instead
- Skip the `SADD kutana:presence:{meeting_id}` step — without it the
  `PresenceReconciler` will reap the managed agent session mid-eval

## Files

- `k8s_runner.py` — entrypoint, drives the scenario loop
- `e2e_runner.py` — Kutana API + Redis orchestrator
- `judge.py` — LLM-as-judge scoring (the ONLY place the Messages API is called)
- `conftest.py` — scenario/rubric loader helpers (imported by `k8s_runner.py`, not pytest fixtures)
- `data/` — scenarios, transcripts, rubrics
- `Dockerfile` — thin layer on top of `api-server` base image

## Running the eval job

**Always** use the `/run-eval-job` skill (or directly: `bash ~/.claude/skills/run-eval-job/run.sh`) instead of running `kubectl delete` + `helm upgrade` + `kubectl logs` manually. The skill handles the full lifecycle and prevents stale-job errors.

```bash
# Default — meeting-notetaker on haiku tier
bash ~/.claude/skills/run-eval-job/run.sh

# All 10 agents
bash ~/.claude/skills/run-eval-job/run.sh --agents all --tier haiku

# Rebuild eval image first, then run
bash ~/.claude/skills/run-eval-job/run.sh --rebuild --agents all

# Specific agents, sonnet tier
bash ~/.claude/skills/run-eval-job/run.sh --agents meeting-notetaker,action-item-tracker --tier sonnet
```

The script requires `kubectl` and `helm` on `PATH` and `charts/kutana/values-secrets.yaml` to exist (credentials come from there — never hardcode them). Set `KUTANA_REPO` if the repo is not at the default path.

## Writing eval reports

After every eval run or investigation, a markdown report goes to `eval_outputs/YYYY-MM-DD/<descriptive-name>.md` at the repo root. The directory is gitignored — reports are local-only per-session artifacts.

**When to write one:**
- After any full scenario run (pass or fail) — capture scores, event counts, bugs surfaced
- After a debugging session — capture root causes, fixes shipped, open decisions
- After an infra change that affects the eval path — capture what changed and the verification result

**Naming:** `eval_outputs/YYYY-MM-DD/YYYY-MM-DD-<slug>.md` — e.g. `2026-04-10-managed-agents-investigation.md`, `2026-04-11-scenario-run-meeting-notetaker.md`. Multiple reports per day are fine.

**Required sections** (see `.claude/rules/eval-reports.md` for the full template):
1. **Context** — what you were testing / investigating
2. **Bugs found** — root cause, fix, verification for each
3. **Deliverables shipped** — commits, skills, config changes
4. **Open decisions** — things needing a human call
5. **Next action** — what happens next

Past reports live in `eval_outputs/` (gitignored — look on the machine where the session ran).
