---
name: check-services
description: Health check all Kutana AI services. TRIGGER on: check services, service status, health check, are services up, is the app running, ping services.
permissions:
  - Bash(curl:*)
  - Bash(ssh:*)
---

# Check Services

Health-checks all Kutana AI services and prints a status table.

## Usage

```bash
bash .claude/skills/check-services/scripts/check-services.sh
```

## Endpoints Checked

| Service | URL | Expected |
|---|---|---|
| API Server | `https://kutana.spark-b0f2.local/api/health` | `{"status":"ok"}` |
| MCP Server | `https://kutana.spark-b0f2.local/mcp/health` | 200 |
| Frontend | `https://kutana.spark-b0f2.local/` | 200 |
| Agent Gateway | `wss://kutana.spark-b0f2.local/ws` | WebSocket upgrade |
| Postgres | `kubectl -n kutana exec statefulset/postgres -- pg_isready` | `accepting connections` |
| Redis | `kubectl -n kutana exec statefulset/redis -- redis-cli ping` | `PONG` |
