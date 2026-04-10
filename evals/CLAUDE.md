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
