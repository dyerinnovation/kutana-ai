#!/usr/bin/env bash
# Health check all Kutana AI services
set -uo pipefail

BASE="https://kutana.spark-b0f2.local"
PASS=0
FAIL=0

check_http() {
  local label=$1
  local url=$2
  local expected=${3:-200}
  local code
  code=$(curl -sk -o /dev/null -w "%{http_code}" "$url")
  if [[ "$code" == "$expected" ]]; then
    printf "  %-20s OK (%s)\n" "$label" "$code"
    ((PASS++)) || true
  else
    printf "  %-20s FAIL (got %s, expected %s)\n" "$label" "$code" "$expected"
    ((FAIL++)) || true
  fi
}

check_exec() {
  local label=$1
  local cmd=$2
  local expected=$3
  local out
  out=$(eval "$cmd" 2>&1 || true)
  if echo "$out" | grep -q "$expected"; then
    printf "  %-20s OK\n" "$label"
    ((PASS++)) || true
  else
    printf "  %-20s FAIL (%s)\n" "$label" "$out"
    ((FAIL++)) || true
  fi
}

echo "==> Checking services..."
echo ""
check_http "API health"   "$BASE/api/health"  200
check_http "MCP server"   "$BASE/mcp/health"  200
check_http "Frontend"     "$BASE/"            200

echo ""
echo "==> Checking infrastructure..."
check_exec "Postgres" \
  "kubectl -n kutana exec -i statefulset/postgres -- pg_isready -U kutana" \
  "accepting connections"
check_exec "Redis" \
  "kubectl -n kutana exec -i statefulset/redis -- redis-cli ping" \
  "PONG"

echo ""
echo "==> Results: $PASS up, $FAIL down"
[[ $FAIL -eq 0 ]] || exit 1
