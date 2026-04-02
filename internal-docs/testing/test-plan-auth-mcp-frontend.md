# Test Plan: User Auth, Agent Registration, MCP Server & Frontend

## Overview
This document covers manual and automated testing for the user authentication, agent registration, API key management, MCP server, web frontend, and Claude Agent SDK integration implemented in the `feature/user-auth-agent-registration-mcp` branch.

---

## Prerequisites

### Infrastructure
```bash
# Start PostgreSQL and Redis
docker compose up -d postgres redis

# Apply database migration
uv sync --all-packages
uv run alembic upgrade head
```

### Services
```bash
# Terminal 1: API Server
PYTHONPATH=services/api-server/src:services/agent-gateway/src:packages/kutana-core/src \
  .venv/bin/uvicorn api_server.main:app --reload --port 8000

# Terminal 2: Agent Gateway
PYTHONPATH=services/agent-gateway/src:services/audio-service/src:packages/kutana-core/src:packages/kutana-providers/src:packages/kutana-memory/src \
  .venv/bin/uvicorn agent_gateway.main:app --reload --port 8003

# Terminal 3: MCP Server (Docker)
export MCP_API_KEY=<generated-key>
export MCP_AGENT_CONFIG_ID=<agent-uuid>
docker compose up mcp-server

# Terminal 4: Frontend
cd web && npm install && npm run dev
```

---

## Test 1: Database Migration

**Objective:** Verify the Alembic migration creates all new tables/columns correctly.

| Step | Action | Expected Result |
|------|--------|-----------------|
| 1.1 | Run `uv run alembic upgrade head` | Migration completes without error |
| 1.2 | Connect to PostgreSQL, check `users` table exists | Table with columns: id, email, hashed_password, name, is_active, created_at, updated_at |
| 1.3 | Check `agent_api_keys` table exists | Table with columns: id, key_prefix, key_hash, agent_config_id, user_id, name, revoked_at, created_at |
| 1.4 | Check `agent_configs` has `owner_id` column | Nullable UUID column with FK to `users.id` |
| 1.5 | Run `uv run alembic downgrade -1` then `upgrade head` | Downgrade and re-upgrade succeed |

---

## Test 2: User Registration & Login

**Objective:** Verify the auth endpoints work correctly.

### 2.1 Registration
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123","name":"Test User"}'
```

| Check | Expected |
|-------|----------|
| Status code | 201 |
| Response has `token` | Non-empty JWT string |
| Response has `user.id` | Valid UUID |
| Response has `user.email` | `test@example.com` |
| Duplicate email registration | 409 Conflict |
| Short password (<8 chars) | 422 Unprocessable Entity |

### 2.2 Login
```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"testpass123"}'
```

| Check | Expected |
|-------|----------|
| Status code | 200 |
| Response has `token` | Non-empty JWT string |
| Wrong password | 401 Unauthorized |
| Non-existent email | 401 Unauthorized |

### 2.3 Get Current User
```bash
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer <token>"
```

| Check | Expected |
|-------|----------|
| Status code | 200 |
| `email` matches registered email | `test@example.com` |
| No auth header | 403 Forbidden |
| Invalid token | 401 Unauthorized |

---

## Test 3: Agent CRUD (Authenticated)

**Objective:** Verify agent creation, listing, and deletion with user ownership.

### 3.1 Create Agent
```bash
curl -s -X POST http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Agent","system_prompt":"You are a test agent","capabilities":["listen","transcribe"]}'
```

| Check | Expected |
|-------|----------|
| Status code | 201 |
| Response has `id` | Valid UUID |
| `name` | `Test Agent` |
| No auth | 403 Forbidden |

### 3.2 List Agents
```bash
curl -s http://localhost:8000/api/v1/agents \
  -H "Authorization: Bearer <token>"
```

| Check | Expected |
|-------|----------|
| Status code | 200 |
| `total` >= 1 | Only shows agents owned by this user |
| Different user's token | Returns 0 agents (ownership isolation) |

### 3.3 Get Single Agent
```bash
curl -s http://localhost:8000/api/v1/agents/<agent_id> \
  -H "Authorization: Bearer <token>"
```

| Check | Expected |
|-------|----------|
| Own agent | 200 with agent details |
| Non-existent ID | 404 |
| Another user's agent | 404 (not 403, to avoid enumeration) |

### 3.4 Delete Agent
```bash
curl -s -X DELETE http://localhost:8000/api/v1/agents/<agent_id> \
  -H "Authorization: Bearer <token>"
```

| Check | Expected |
|-------|----------|
| Status code | 204 |
| Subsequent GET | 404 |

---

## Test 4: API Key Management

**Objective:** Verify API key generation, listing, and revocation.

### 4.1 Generate API Key
```bash
curl -s -X POST http://localhost:8000/api/v1/agents/<agent_id>/keys \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"name":"test-key"}'
```

| Check | Expected |
|-------|----------|
| Status code | 201 |
| `raw_key` starts with `cvn_` | 36 chars total (4 prefix + 32 hex) |
| `key_prefix` | First 8 chars of raw_key |
| `name` | `test-key` |

### 4.2 List Keys
```bash
curl -s http://localhost:8000/api/v1/agents/<agent_id>/keys \
  -H "Authorization: Bearer <token>"
```

| Check | Expected |
|-------|----------|
| Status code | 200 |
| `total` >= 1 | Keys listed with prefix, name, dates |
| `raw_key` NOT in response | Only shown on creation |

### 4.3 Revoke Key
```bash
curl -s -X DELETE http://localhost:8000/api/v1/agents/<agent_id>/keys/<key_id> \
  -H "Authorization: Bearer <token>"
```

| Check | Expected |
|-------|----------|
| Status code | 204 |
| Subsequent list | Key shows `revoked_at` timestamp |

---

## Test 5: Token Exchange (API Key → Gateway JWT)

**Objective:** Verify API key can be exchanged for a gateway JWT.

### 5.1 Exchange Valid Key
```bash
curl -s -X POST http://localhost:8000/api/v1/token/gateway \
  -H "X-API-Key: <raw_api_key>"
```

| Check | Expected |
|-------|----------|
| Status code | 200 |
| `token` | Non-empty JWT string |
| `agent_config_id` | Matches the agent's UUID |
| `name` | Matches agent name |

### 5.2 Revoked Key
```bash
# After revoking the key:
curl -s -X POST http://localhost:8000/api/v1/token/gateway \
  -H "X-API-Key: <revoked_api_key>"
```

| Check | Expected |
|-------|----------|
| Status code | 401 |
| `detail` | "Invalid or revoked API key" |

### 5.3 Invalid Key
```bash
curl -s -X POST http://localhost:8000/api/v1/token/gateway \
  -H "X-API-Key: cvn_invalid_key_here"
```

| Check | Expected |
|-------|----------|
| Status code | 401 |

---

## Test 6: Meeting & Task CRUD (Authenticated)

### 6.1 Create Meeting
```bash
curl -s -X POST http://localhost:8000/api/v1/meetings \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"platform":"kutana","title":"Test Meeting","scheduled_at":"2026-03-02T10:00:00Z"}'
```

| Check | Expected |
|-------|----------|
| Status code | 201 |
| `id` | Valid UUID |
| `status` | `scheduled` |

### 6.2 Create Task
```bash
curl -s -X POST http://localhost:8000/api/v1/tasks \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"meeting_id":"<meeting_id>","description":"Follow up on budget","priority":"high"}'
```

| Check | Expected |
|-------|----------|
| Status code | 201 |
| `meeting_id` matches | Yes |
| `priority` | `high` |

### 6.3 List Tasks by Meeting
```bash
curl -s "http://localhost:8000/api/v1/tasks?meeting_id=<meeting_id>" \
  -H "Authorization: Bearer <token>"
```

| Check | Expected |
|-------|----------|
| Status code | 200 |
| `total` >= 1 | Only tasks for this meeting |

---

## Test 7: MCP Server (Streamable HTTP)

**Objective:** Verify MCP server starts and tools are accessible.

### 7.1 Server Startup
```bash
docker compose up mcp-server
```

| Check | Expected |
|-------|----------|
| Container starts | No errors in logs |
| Port 3001 accessible | `curl http://localhost:3001/mcp` returns response |

### 7.2 Tool Discovery
Use the MCP Inspector or curl to list available tools:
```bash
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

| Check | Expected |
|-------|----------|
| Response lists tools | 7 tools: list_meetings, join_meeting, leave_meeting, get_transcript, get_tasks, create_task, get_participants |

### 7.3 Resource Discovery
```bash
curl -X POST http://localhost:3001/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"resources/list"}'
```

| Check | Expected |
|-------|----------|
| Resources listed | meeting://{meeting_id}, meeting://{meeting_id}/transcript |

---

## Test 8: Web Frontend

**Objective:** Verify all frontend pages work with the backend.

### 8.1 Login Page
| Step | Action | Expected |
|------|--------|----------|
| 8.1.1 | Navigate to `http://localhost:5173/login` | Login form displayed |
| 8.1.2 | Enter valid credentials, submit | Redirects to dashboard |
| 8.1.3 | Enter invalid credentials | Error message displayed |

### 8.2 Registration Page
| Step | Action | Expected |
|------|--------|----------|
| 8.2.1 | Navigate to `/register` | Registration form displayed |
| 8.2.2 | Fill form and submit | Redirects to dashboard |
| 8.2.3 | Try duplicate email | Error "Email already registered" |

### 8.3 Dashboard
| Step | Action | Expected |
|------|--------|----------|
| 8.3.1 | View dashboard after login | Agent cards displayed (or empty state) |
| 8.3.2 | Click "Create Agent" | Navigates to agent creation form |

### 8.4 Agent Creation
| Step | Action | Expected |
|------|--------|----------|
| 8.4.1 | Fill name, system prompt, select capabilities | Form accepts input |
| 8.4.2 | Submit | Navigates to agent detail page |

### 8.5 Agent Detail Page (Critical)
| Step | Action | Expected |
|------|--------|----------|
| 8.5.1 | View agent info | Name, system prompt, capabilities displayed |
| 8.5.2 | Click "Generate Key" | Dialog opens |
| 8.5.3 | Enter key name, submit | Green banner shows raw key (cvn_...) |
| 8.5.4 | Copy raw key | Clipboard has the key |
| 8.5.5 | Dismiss key banner | Banner disappears, key gone forever |
| 8.5.6 | View API keys list | Key prefix + name + date shown |
| 8.5.7 | Click "Revoke" on a key | Key moves to revoked section |
| 8.5.8 | View MCP Configuration section | Streamable HTTP URL displayed |
| 8.5.9 | View Server Environment section | Env vars with real key (if just generated) |
| 8.5.10 | Click "Delete Agent" | Confirmation dialog, then redirects to dashboard |

### 8.6 Meetings Page
| Step | Action | Expected |
|------|--------|----------|
| 8.6.1 | View meetings list | Meetings displayed (or empty state) |
| 8.6.2 | Create a new meeting | Meeting appears in list |

### 8.7 Protected Routes
| Step | Action | Expected |
|------|--------|----------|
| 8.7.1 | Navigate to `/` without auth | Redirects to `/login` |
| 8.7.2 | Clear localStorage token, refresh | Redirects to `/login` |

---

## Test 9: E2E Automated Test

**Objective:** Run the full-stack integration test.

```bash
python scripts/test_e2e_full_stack.py
```

| Step | Expected |
|------|----------|
| Register user | PASS |
| Login | PASS |
| GET /me | PASS |
| Create agent | PASS |
| Generate API key | PASS |
| Exchange for gateway token | PASS |
| Create meeting | PASS |
| Create task | PASS |
| Verify task persisted | PASS |
| List agents | PASS |
| List API keys | PASS |
| **All 11 steps pass** | Exit code 0 |

---

## Test 10: Claude Agent SDK Integration

**Objective:** Verify the example agent can connect to the MCP server.

### Prerequisites
- MCP server container running with valid `MCP_API_KEY` and `MCP_AGENT_CONFIG_ID`
- API server and gateway running
- A meeting exists in the system

### Steps
```bash
export ANTHROPIC_API_KEY=sk-ant-...
export MCP_SERVER_URL=http://localhost:3001

cd examples/meeting-assistant-agent
uv run python agent.py
```

| Check | Expected |
|-------|----------|
| Agent starts | No import errors |
| Agent calls `list_meetings` | Returns meeting list from API |
| Agent calls `join_meeting` | Connects to gateway via MCP server |
| Agent calls `get_transcript` | Returns buffered transcript segments |
| Agent calls `create_task` | Task created in database |

---

## Test 11: Security Checks

| Check | Expected |
|-------|----------|
| SQL injection in email field | Rejected by Pydantic EmailStr validation |
| JWT with wrong secret | 401 Unauthorized |
| Expired JWT | 401 Unauthorized |
| API key without `cvn_` prefix | 401 (hash won't match) |
| CORS from unauthorized origin | Request blocked |
| Access another user's agents | 404 (not 403) |
| Revoked API key for token exchange | 401 |

---

## Test Summary Checklist

- [ ] Test 1: Database migration up/down
- [ ] Test 2: Registration, login, /me
- [ ] Test 3: Agent CRUD with ownership
- [ ] Test 4: API key generate/list/revoke
- [ ] Test 5: Token exchange (valid/revoked/invalid)
- [ ] Test 6: Meeting & task CRUD
- [ ] Test 7: MCP server startup + tool discovery
- [ ] Test 8: Frontend all pages
- [ ] Test 9: E2E automated script
- [ ] Test 10: Claude Agent SDK integration
- [ ] Test 11: Security checks
