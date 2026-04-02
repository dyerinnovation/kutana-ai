#!/usr/bin/env bash
# Show or create test user credentials for Kutana AI
set -euo pipefail

BASE="https://kutana.spark-b0f2.local"
MODE=${1:-}  # --create

if [[ "$MODE" == "--create" ]]; then
  echo "==> Creating test users..."
  for TIER in free pro biz; do
    EMAIL="test-${TIER}@kutana.test"
    PASS="TestPass123!"
    curl -sk -X POST "$BASE/api/v1/auth/register" \
      -H "Content-Type: application/json" \
      -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\",\"name\":\"Test ${TIER^}\"}" \
      | python3 -m json.tool || true
    echo "  Created: $EMAIL / $PASS"
  done
fi

echo ""
echo "==> Getting JWT tokens..."
for TIER in free pro biz; do
  EMAIL="test-${TIER}@kutana.test"
  PASS="TestPass123!"
  echo "--- $EMAIL ---"
  TOKEN=$(curl -sk -X POST "$BASE/api/v1/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token','ERROR'))")
  echo "  JWT: $TOKEN"

  # Get API key
  APIKEY=$(curl -sk -X POST "$BASE/api/v1/api-keys" \
    -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"name":"test-key"}' \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('key','ERROR'))")
  echo "  API Key: $APIKEY"
done
