---
name: run-tests
description: Run the Convene AI test suite. TRIGGER on: run tests, pytest, test suite, check tests, run unit tests, vitest, frontend tests.
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
bash .claude/skills/run-tests/scripts/run-tests.sh --package convene-core
```

## Test Locations

| Scope | Command |
|---|---|
| convene-core | `uv run pytest packages/convene-core/tests/` |
| convene-providers | `uv run pytest packages/convene-providers/tests/` |
| convene-memory | `uv run pytest packages/convene-memory/tests/` |
| api-server | `uv run pytest services/api-server/tests/` |
| agent-gateway | `uv run pytest services/agent-gateway/tests/` |
| frontend | `cd web && npx vitest run` |

Tests run on the DGX Spark via SSH (requires running infrastructure).
