---
name: run-tests
description: Run the Kutana AI test suite. TRIGGER on: run tests, pytest, test suite, check tests, run unit tests, vitest, frontend tests.
permissions:
  - Bash(ssh:*)
  - Bash(uv:*)
  - Bash(npx:*)
---

# Run Tests

Runs the full test suite: pytest for Python packages/services, vitest for frontend.

## Usage

```bash
# All tests (Python + frontend)
bash .claude/skills/run-tests/scripts/run-tests.sh

# Python only
bash .claude/skills/run-tests/scripts/run-tests.sh --python

# Frontend only
bash .claude/skills/run-tests/scripts/run-tests.sh --frontend

# Specific package
bash .claude/skills/run-tests/scripts/run-tests.sh --package kutana-core
```

## Test Locations

| Scope | Command |
|---|---|
| kutana-core | `uv run pytest packages/kutana-core/tests/` |
| kutana-providers | `uv run pytest packages/kutana-providers/tests/` |
| kutana-memory | `uv run pytest packages/kutana-memory/tests/` |
| api-server | `uv run pytest services/api-server/tests/` |
| agent-gateway | `uv run pytest services/agent-gateway/tests/` |
| frontend | `cd web && npx vitest run` |

Tests run on the DGX Spark via SSH (requires running infrastructure).
