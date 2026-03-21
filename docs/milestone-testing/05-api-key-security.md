# API Key Security

## Purpose
Verify API key security features: expiry enforcement, revocation, rate limiting (429), and audit log entries.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed
- [03-mcp-auth-flow.md](./03-mcp-auth-flow.md) verified (token exchange works)
- `$TOKEN`, `$AGENT_ID` exported
- API server (8000) running
- Redis running (required for rate limiting)

## Part A — Key Expiry

### Step 1: Create a Short-Lived Key (5 seconds)

```bash
EXPIRY=$(date -u -v+5S +%Y-%m-%dT%H:%M:%SZ)

SHORT_KEY=$(curl -s -X POST http://localhost:8000/api/v1/agents/$AGENT_ID/keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"name\": \"expiry-test\", \"expires_at\": \"$EXPIRY\"}" | jq -r '.raw_key')

echo "SHORT_KEY=$SHORT_KEY (expires in ~5s)"
```

### Step 2: Use Key Immediately (should succeed)

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $SHORT_KEY"
```

Expected: `200`

### Step 3: Wait and Retry (should fail)

```bash
echo "Waiting 6 seconds for key to expire..."
sleep 6

curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $SHORT_KEY"
```

Expected: `401`

## Part B — Key Revocation

### Step 4: Create and Immediately Revoke a Key

```bash
# Create
REVOKE_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/agents/$AGENT_ID/keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "revoke-test"}')

REVOKE_KEY=$(echo "$REVOKE_RESPONSE" | jq -r '.raw_key')
REVOKE_KEY_ID=$(echo "$REVOKE_RESPONSE" | jq -r '.id')

echo "REVOKE_KEY=$REVOKE_KEY"
echo "REVOKE_KEY_ID=$REVOKE_KEY_ID"
```

### Step 5: Verify Key Works Before Revocation

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $REVOKE_KEY"
```

Expected: `200`

### Step 6: Revoke the Key

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE http://localhost:8000/api/v1/agents/$AGENT_ID/keys/$REVOKE_KEY_ID \
  -H "Authorization: Bearer $TOKEN"
```

Expected: `204`

### Step 7: Verify Revoked Key Fails

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $REVOKE_KEY"
```

Expected: `401`

### Step 8: Verify Revoked Key Shows in List

```bash
curl -s http://localhost:8000/api/v1/agents/$AGENT_ID/keys \
  -H "Authorization: Bearer $TOKEN" | jq '.items[] | select(.name == "revoke-test") | {name, revoked_at}'
```

Expected: `revoked_at` is non-null.

## Part C — Rate Limiting

### Step 9: Create a Key for Rate Limit Testing

```bash
export RATE_KEY=$(curl -s -X POST http://localhost:8000/api/v1/agents/$AGENT_ID/keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "rate-limit-test"}' | jq -r '.raw_key')

echo "RATE_KEY=$RATE_KEY"
```

### Step 10: Send 65 Rapid Requests

```bash
# Send 65 requests rapidly and track status codes
for i in $(seq 1 65); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST http://localhost:8000/api/v1/token/mcp \
    -H "X-API-Key: $RATE_KEY")
  if [ "$STATUS" = "429" ]; then
    echo "Request $i: 429 — Rate limited!"
    break
  fi
  echo "Request $i: $STATUS"
done
```

Expected: Requests 1-60 return `200`, request ~61+ returns `429`.

### Step 11: Verify Rate Limit Headers

```bash
# Check response headers on a rate-limited request
curl -s -D - -o /dev/null \
  -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $RATE_KEY" 2>&1 | grep -iE "ratelimit|retry"
```

Expected headers:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
Retry-After: 60
```

### Step 12: Verify Rate Limit Response Body

```bash
curl -s -X POST http://localhost:8000/api/v1/token/mcp \
  -H "X-API-Key: $RATE_KEY" | jq .
```

Expected (when rate limited):
```json
{
  "detail": "Rate limit exceeded",
  "retry_after": 60
}
```

## Part D — Audit Log

### Step 13: Query Audit Log Entries

```bash
# Connect to the database and query audit entries
docker exec -it $(docker compose ps -q postgres) psql -U convene -d convene -c \
  "SELECT event_type, key_prefix, ip_address, created_at
   FROM api_key_audit_log
   ORDER BY created_at DESC
   LIMIT 10;"
```

Expected entries include:
- `created` — when keys were generated
- `used` — when keys were exchanged for tokens
- `revoked` — when keys were revoked

### Step 14: Verify IP and User-Agent Logging

```bash
docker exec -it $(docker compose ps -q postgres) psql -U convene -d convene -c \
  "SELECT event_type, ip_address, user_agent
   FROM api_key_audit_log
   WHERE event_type = 'used'
   ORDER BY created_at DESC
   LIMIT 3;"
```

Expected: `ip_address` is `127.0.0.1` (or `::1`), `user_agent` contains `curl/...`.

## Verification Checklist

- [ ] Short-lived key works immediately (200)
- [ ] Short-lived key fails after expiry (401)
- [ ] Key works before revocation (200)
- [ ] DELETE revokes key (204)
- [ ] Revoked key fails (401)
- [ ] Revoked key shows `revoked_at` in list
- [ ] 60 rapid requests succeed (200)
- [ ] Request 61+ returns 429
- [ ] Rate limit headers present (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `Retry-After`)
- [ ] Rate limit body contains `detail` and `retry_after`
- [ ] Audit log contains `created` entries
- [ ] Audit log contains `used` entries with IP
- [ ] Audit log contains `revoked` entries

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Rate limiting not triggering at 60 | Check `RateLimitMiddleware` config. Default is 60/minute |
| Rate limiting never triggers | Verify Redis is running — rate limiting degrades gracefully (allows all) without Redis |
| Audit log table doesn't exist | Run `uv run alembic upgrade head` to apply migrations |
| `psql: FATAL: role "convene" does not exist` | Check docker-compose postgres config |
| Key expires too fast/slow | Verify system clock is UTC-synchronized |

## Cleanup

```bash
# Wait 60 seconds for rate limit window to reset, or use a fresh key:
export API_KEY=$(curl -s -X POST http://localhost:8000/api/v1/agents/$AGENT_ID/keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "post-security-test"}' | jq -r '.raw_key')

echo "Fresh API_KEY=$API_KEY"
```
