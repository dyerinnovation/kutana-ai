# Evals — Managed Agents Only

This directory evaluates **real Anthropic managed agent sessions** against the live Kutana pipeline. It does NOT mock the agent, stub the MCP tool layer, or call the Anthropic Messages API directly to simulate an agent.

## What a run does

1. Creates a real meeting via `POST /v1/meetings`
2. Calls `POST /v1/agent-templates/{id}/activate` — spins up an actual Anthropic managed agent session (visible in the Anthropic console)
3. Injects `transcript.segment.final` events into Redis `kutana:events`
4. `MeetingEventRelay` (in `services/api-server/src/api_server/agent_lifecycle.py`) forwards each segment to the live managed agent session
5. Agent events stream back through `agent_lifecycle.stream_and_publish_events` → Redis → `E2ERunner.observe_agent_events`
6. Judge scores the collected `agent.message` / `agent.mcp_tool_use` events + the final summary

## Do NOT

- Call `client.messages.create()` directly to simulate an agent's response
- Stub MCP tool schemas to generate synthetic `tool_use` blocks
- Add a "mock mode" flag — if the live path is broken, fix the live path, don't shim around it
- Add pytest tests here — the harness runs as a K8s Job via `k8s_runner.py`, not pytest

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
