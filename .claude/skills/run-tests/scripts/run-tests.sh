#!/usr/bin/env bash
# Run Convene AI test suite: pytest (Python) + vitest (frontend)
set -euo pipefail

DGX=dgx
MODE=${1:-}     # --python | --frontend
PACKAGE=${2:-}  # e.g. convene-core

PASS=0
FAIL=0

run_pytest() {
  local label=$1
  local path=$2
  echo "--- $label ---"
  if ssh "$DGX" "cd ~/convene-ai && PATH=\$HOME/.local/bin:\$PATH uv run pytest $path -q 2>&1"; then
    echo "  PASS"
    ((PASS++)) || true
  else
    echo "  FAIL"
    ((FAIL++)) || true
  fi
  echo ""
}

if [[ "$MODE" != "--frontend" ]]; then
  echo "==> Python tests"
  echo ""
  if [[ -n "$PACKAGE" ]]; then
    run_pytest "$PACKAGE" "packages/$PACKAGE/tests/"
  else
    run_pytest "convene-core"      "packages/convene-core/tests/"
    run_pytest "convene-providers" "packages/convene-providers/tests/"
    run_pytest "convene-memory"    "packages/convene-memory/tests/"
    run_pytest "api-server"        "services/api-server/tests/"
    run_pytest "agent-gateway"     "services/agent-gateway/tests/"
    run_pytest "mcp-server"        "services/mcp-server/tests/"
    run_pytest "task-engine"       "services/task-engine/tests/"
  fi
fi

if [[ "$MODE" != "--python" ]]; then
  echo "==> Frontend tests (vitest)"
  if ssh "$DGX" "cd ~/convene-ai/web && npx vitest run 2>&1"; then
    echo "  PASS"
    ((PASS++)) || true
  else
    echo "  FAIL"
    ((FAIL++)) || true
  fi
fi

echo ""
echo "==> Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] || exit 1
