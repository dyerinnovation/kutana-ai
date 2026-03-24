---
name: check-services
description: Health check all Convene AI services. TRIGGER on: check services, service status, health check, are services up, is the app running, ping services.
permissions:
  - Bash(curl:*)
  - Bash(ssh:*)
---

# Check Services

Health-checks all Convene AI services and prints a status table.

## Usage

```bash
bash .claude/skills/check-services/scripts/check-services.sh
```

## Endpoints Checked

| Service | URL | Expected |
|---|---|---|
| API Server | `https://convene.spark-b0f2.local/api/health` | `{"status":"ok"}` |
| MCP Server | `https://convene.spark-b0f2.local/mcp/health` | 200 |
| Frontend | `https://convene.spark-b0f2.local/` | 200 |
| Agent Gateway | `wss://convene.spark-b0f2.local/ws` | WebSocket upgrade |
| Postgres | `ssh dgx kubectl exec postgres -- pg_isready` | `accepting connections` |
| Redis | `ssh dgx kubectl exec redis -- redis-cli ping` | `PONG` |
