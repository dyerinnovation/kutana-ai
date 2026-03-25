# Shared Setup & Prerequisites

## Purpose
One-time environment setup required before running any milestone test. All subsequent docs assume this setup is complete.

## Prerequisites
- macOS or Linux
- Python 3.12+
- Node.js 18+
- Docker & Docker Compose
- `uv` package manager installed (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

## Step 1 — Clone & Install Dependencies

```bash
cd convene-ai

# Python packages (all workspace members)
UV_LINK_MODE=copy uv sync --all-packages

# Web frontend
cd web && npm install && cd ..
```

> **macOS note:** If you see reflink errors, ensure `UV_LINK_MODE=copy` is set.

## Step 2 — Start Infrastructure

```bash
docker compose up -d postgres redis
```

Verify both containers are healthy:

```bash
docker compose ps
```

Expected: `postgres` and `redis` both show `healthy`.

## Step 3 — Configure Environment

```bash
cp .env.example .env
```

Key variables (edit `.env` as needed):

| Variable | Default | Notes |
|----------|---------|-------|
| `DATABASE_URL` | `postgresql+asyncpg://convene:convene@localhost:5432/convene` | Local Postgres |
| `REDIS_URL` | `redis://localhost:6379/0` | Local Redis |
| `AGENT_GATEWAY_PORT` | `8003` | WebSocket gateway |
| `AGENT_GATEWAY_JWT_SECRET` | `change-me-in-production` | JWT signing secret |
| `STT_PROVIDER` | `whisper-remote` | Speech-to-text backend |
| `WHISPER_API_URL` | `http://spark-b0f2.local/convene-stt/v1` | Whisper endpoint |

## Step 4 — Run Database Migrations

```bash
uv run alembic upgrade head
```

Expected output ends with: `INFO  [alembic.runtime.migration] Running upgrade ... -> head`

## Step 5 — Start Services (4 terminals)

### Terminal 1 — API Server (port 8000)
```bash
uv run uvicorn api_server.main:app --reload --port 8000
```

### Terminal 2 — Agent Gateway (port 8003)
```bash
uv run python -m agent_gateway.main
```

### Terminal 3 — Web Frontend (port 5173)
```bash
cd web && npm run dev
```

### Terminal 4 — MCP Server (port 3001)
```bash
docker compose up mcp-server -d
# OR run locally:
uv run python -m mcp_server.main
```

## Step 6 — Verify Health Endpoints

```bash
# API server
curl -s http://localhost:8000/health | jq .
```
Expected:
```json
{ "status": "ok" }
```

```bash
# Web frontend (should return HTML)
curl -s -o /dev/null -w "%{http_code}" http://localhost:5173
```
Expected: `200`

## Step 7 — Register Test User

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "tester@convene.dev",
    "password": "TestPass123!",
    "name": "Test User"
  }' | jq .
```

Save the token:
```bash
export TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "tester@convene.dev",
    "password": "TestPass123!",
    "name": "Test User"
  }' | jq -r '.token')

echo "TOKEN=$TOKEN"
```

> If the user already exists, log in instead:
> ```bash
> export TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
>   -H "Content-Type: application/json" \
>   -d '{"email": "tester@convene.dev", "password": "TestPass123!"}' \
>   | jq -r '.token')
> ```

## Step 8 — Create Test Agent

```bash
export AGENT_ID=$(curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "name": "test-agent",
    "system_prompt": "You are a helpful meeting assistant.",
    "capabilities": ["listen", "speak", "transcribe"]
  }' | jq -r '.id')

echo "AGENT_ID=$AGENT_ID"
```

## Step 9 — Generate API Key

```bash
export API_KEY=$(curl -s -X POST http://localhost:8000/api/v1/agents/$AGENT_ID/keys \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"name": "test-key"}' | jq -r '.raw_key')

echo "API_KEY=$API_KEY"
```

> **Important:** The raw key is only returned at creation time. Save it immediately.

## Verification Checklist

- [ ] `docker compose ps` shows postgres and redis as healthy
- [ ] `curl http://localhost:8000/health` returns `{"status": "ok"}`
- [ ] Web frontend loads at `http://localhost:5173`
- [ ] `$TOKEN` is set (non-empty)
- [ ] `$AGENT_ID` is set (UUID format)
- [ ] `$API_KEY` is set (starts with `cvn_`)

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `uv sync` fails with reflink error | Set `UV_LINK_MODE=copy` |
| Alembic migration fails | Check `DATABASE_URL` in `.env`, ensure postgres is running |
| Port already in use | `lsof -i :8000` to find the process, kill it |
| Redis connection refused | `docker compose up -d redis` and wait for healthy |
| `ModuleNotFoundError` | Run `UV_LINK_MODE=copy uv sync --all-packages` again |
| `.pth` files not loading (macOS) | `find .venv/lib/python3.13/site-packages -maxdepth 1 -name "*.pth" -exec chflags nohidden {} \;` |

## Cleanup

To tear down everything after all testing is complete:

```bash
docker compose down -v   # Removes containers + volumes (deletes all data)
```

To keep data but stop services:
```bash
docker compose stop
# Kill API server and gateway with Ctrl+C in their terminals
```
