#!/usr/bin/env bash
# connect.sh — Join a Convene meeting from the command line.
#
# Usage:
#   ./scripts/connect.sh "Standup"              # join by title
#   ./scripts/connect.sh --id <meeting_uuid>    # join by ID
#
# Required env vars:
#   CONVENE_API_KEY   — API key from the Convene dashboard
#   CONVENE_URL       — Base URL (default: https://convene.spark-b0f2.local)

set -euo pipefail

CONVENE_URL="${CONVENE_URL:-https://convene.spark-b0f2.local}"
MCP_URL="${CONVENE_URL}/mcp"

if [[ -z "${CONVENE_API_KEY:-}" ]]; then
  echo "Error: CONVENE_API_KEY is not set." >&2
  echo "  export CONVENE_API_KEY=cvn_..." >&2
  exit 1
fi

# Parse arguments
MEETING_TITLE=""
MEETING_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --id)
      MEETING_ID="$2"
      shift 2
      ;;
    --help|-h)
      sed -n '2,12p' "$0" | sed 's/^# \?//'
      exit 0
      ;;
    *)
      MEETING_TITLE="$1"
      shift
      ;;
  esac
done

if [[ -z "$MEETING_TITLE" && -z "$MEETING_ID" ]]; then
  echo "Usage: $0 \"Meeting Title\" | --id <uuid>" >&2
  exit 1
fi

# ── Step 1: Exchange API key for MCP JWT ────────────────────────────────────
echo "Authenticating with Convene API..."
TOKEN_RESPONSE=$(curl -sf -X POST \
  "${CONVENE_URL}/api/v1/token/mcp" \
  -H "X-API-Key: ${CONVENE_API_KEY}" \
  -H "Content-Type: application/json")

MCP_TOKEN=$(echo "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])" 2>/dev/null || true)
if [[ -z "$MCP_TOKEN" ]]; then
  echo "Error: Failed to obtain MCP token. Check CONVENE_API_KEY and CONVENE_URL." >&2
  echo "Response: $TOKEN_RESPONSE" >&2
  exit 1
fi
echo "Authenticated."

# ── Step 2: Resolve meeting ID from title if needed ─────────────────────────
if [[ -z "$MEETING_ID" ]]; then
  echo "Looking for active meeting: \"${MEETING_TITLE}\"..."
  MEETINGS=$(curl -sf -X POST "$MCP_URL" \
    -H "Authorization: Bearer $MCP_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"list_meetings","arguments":{}},"id":1}')

  MEETING_ID=$(echo "$MEETINGS" | python3 - "$MEETING_TITLE" <<'EOF'
import sys, json

data = json.loads(sys.stdin.read())
title = sys.argv[1]
text = data.get("result", {}).get("content", [{}])[0].get("text", "[]")
meetings = json.loads(text)
for m in meetings:
    if m.get("title") == title and m.get("status") == "active":
        print(m["id"])
        sys.exit(0)
# Not found active — try any status
for m in meetings:
    if m.get("title") == title:
        print(m["id"])
        sys.exit(0)
sys.exit(1)
EOF
  ) || true

  if [[ -z "$MEETING_ID" ]]; then
    echo "No meeting found with title \"${MEETING_TITLE}\". Creating one..."
    CREATE=$(curl -sf -X POST "$MCP_URL" \
      -H "Authorization: Bearer $MCP_TOKEN" \
      -H "Content-Type: application/json" \
      -d "{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\",\"params\":{\"name\":\"join_or_create_meeting\",\"arguments\":{\"title\":\"${MEETING_TITLE}\"}},\"id\":1}")
    echo "Meeting result:"
    echo "$CREATE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(json.loads(d['result']['content'][0]['text']), indent=2))" 2>/dev/null || echo "$CREATE"
    exit 0
  fi
fi

# ── Step 3: Join the meeting ─────────────────────────────────────────────────
echo "Joining meeting ${MEETING_ID}..."
JOIN=$(curl -sf -X POST "$MCP_URL" \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\",\"params\":{\"name\":\"join_meeting\",\"arguments\":{\"meeting_id\":\"${MEETING_ID}\"}},\"id\":1}")

echo "Join result:"
echo "$JOIN" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(json.loads(d['result']['content'][0]['text']), indent=2))" 2>/dev/null || echo "$JOIN"

# ── Step 4: Show meeting status ──────────────────────────────────────────────
echo ""
echo "Meeting status:"
STATUS=$(curl -sf -X POST "$MCP_URL" \
  -H "Authorization: Bearer $MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"jsonrpc\":\"2.0\",\"method\":\"tools/call\",\"params\":{\"name\":\"get_meeting_status\",\"arguments\":{\"meeting_id\":\"${MEETING_ID}\"}},\"id\":1}")

echo "$STATUS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(json.loads(d['result']['content'][0]['text']), indent=2))" 2>/dev/null || echo "$STATUS"
