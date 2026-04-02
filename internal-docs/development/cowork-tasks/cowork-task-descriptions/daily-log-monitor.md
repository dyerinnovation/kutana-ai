# Daily Log Monitor — Task Instructions

> These instructions are read and executed by the CoWork scheduled task.
> This task checks infrastructure health and application logs for errors.

---

## Pre-flight

1. Verify infrastructure is running:
   ```bash
   docker compose ps
   ```
   If containers are down, note it as a critical alert.

2. Read project conventions:
   ```
   Read CLAUDE.md for service architecture context.
   ```

---

## Health Checks

### 1. PostgreSQL

```bash
docker compose exec -T postgres pg_isready -U kutana
```

If unhealthy:
- Check container logs: `docker compose logs --tail=50 postgres`
- Check disk usage: `docker compose exec -T postgres df -h /var/lib/postgresql/data`
- Alert threshold: connection refused or disk > 80%

### 2. Redis

```bash
docker compose exec -T redis redis-cli ping
docker compose exec -T redis redis-cli info memory | grep used_memory_human
docker compose exec -T redis redis-cli info clients | grep connected_clients
```

Alert thresholds:
- PING fails
- Memory > 500MB (investigate stream accumulation)
- Connected clients > 50 (potential connection leak)

### 3. Docker Containers

```bash
docker compose ps --format json
```

Check for:
- Containers in "restarting" state (crash loop)
- Containers that exited unexpectedly
- MCP server container health

---

## Application Log Checks

### 4. API Server Errors

```bash
# Check for recent errors in API server (if running locally)
# Look for ERROR level logs, HTTP 500s, unhandled exceptions
```

Alert on:
- Any HTTP 500 responses
- Database connection errors
- JWT validation failures (potential auth issues)
- Rate limit violations

### 5. Agent Gateway Errors

Check for:
- WebSocket connection failures (4001 auth, 4029 limit)
- Audio bridge errors (STT timeout, buffer overflow)
- Event relay disconnections

### 6. Redis Streams Health

```bash
docker compose exec -T redis redis-cli XLEN meeting_events
docker compose exec -T redis redis-cli XINFO GROUPS meeting_events 2>/dev/null || echo "No consumer groups"
```

Alert on:
- Stream length > 10000 (consumer lag — messages not being processed)
- Consumer group pending > 1000 (stale messages)
- No consumer groups when services should be running

---

## Report Format

Write results to `docs/cowork-tasks/cowork-task-output/log-monitor-{date}.md`:

```markdown
# Log Monitor Report — {date}

## Infrastructure Health
| Service | Status | Notes |
|---------|--------|-------|
| PostgreSQL | ✅/⚠️/❌ | {details} |
| Redis | ✅/⚠️/❌ | {details} |
| MCP Server | ✅/⚠️/❌ | {details} |

## Application Health
| Check | Status | Notes |
|-------|--------|-------|
| API Server | ✅/⚠️/❌ | {details} |
| Gateway | ✅/⚠️/❌ | {details} |
| Redis Streams | ✅/⚠️/❌ | {details} |

## Alerts
{List any items exceeding thresholds}

## Recommendations
{Any suggested actions}
```

---

## Hard Rules

- **Read-only.** This task never modifies application code or configuration.
- **No restarts.** If a service is down, report it — don't restart it.
- **Always write the report.** Even if everything is healthy, write the report confirming it.
- **Keep reports for 7 days.** Delete reports older than 7 days to prevent accumulation.
