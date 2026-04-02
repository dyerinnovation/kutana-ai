# Summary: User Auth, Agent Registration, MCP Server & Claude Agent SDK

## Date: 2026-03-02

## Work Completed

### Block 1: Database Schema
- Added `UserORM` table (id, email, hashed_password, name, is_active, timestamps)
- Added `AgentApiKeyORM` table (id, key_prefix, key_hash, agent_config_id, user_id, name, revoked_at, timestamps)
- Added `owner_id` FK to `AgentConfigORM` (nullable for backward compat)
- Created Alembic migration `b3c4d5e6f7a8_user_auth_and_api_keys.py`
- Created `User` Pydantic model in `kutana_core.models.user`

### Block 2: Auth Utilities
- Added `passlib[bcrypt]`, `PyJWT`, `python-multipart` deps to api-server
- Created `auth.py` with: `hash_password()`, `verify_password()`, `create_user_token()`, `decode_user_token()`, `generate_api_key()`, `hash_api_key()`
- Created `auth_deps.py` with `get_current_user()` FastAPI dependency and `CurrentUser` type alias
- Added `jwt_secret` and `agent_gateway_jwt_secret` to Settings

### Block 3: Auth API Routes
- `POST /api/v1/auth/register` — email, password, name → JWT + user
- `POST /api/v1/auth/login` — email, password → JWT + user
- `GET /api/v1/auth/me` — (authenticated) → user profile

### Block 4: Agent CRUD + API Key Management
- Rewrote `agents.py` routes with real DB ops + auth
- Rewrote `meetings.py` routes with real DB ops + auth
- Rewrote `tasks.py` routes with real DB ops + auth
- Created `agent_keys.py` — POST/GET/DELETE for API key CRUD
- Created `token.py` — `POST /api/v1/token/gateway` exchanges API key for gateway JWT
- Added all new routers to `main.py`

### Block 5: MCP Server (Streamable HTTP / Docker)
- Created `services/mcp-server/` as new workspace member
- **Transport: Streamable HTTP** (not STDIO) — runs as Docker container on port 3001
- Tools: `list_meetings`, `join_meeting`, `leave_meeting`, `get_transcript`, `get_tasks`, `create_task`, `get_participants`
- Resources: `meeting://{id}`, `meeting://{id}/transcript`
- Created `Dockerfile` and added `mcp-server` service to `docker-compose.yml`
- Uses `stateless_http=True, json_response=True` for production scalability

### Block 6-7: Web Frontend
- Full React 19 + TypeScript + Vite + Tailwind v4 scaffold (27 files)
- Auth pages: Login, Register
- Dashboard: Agent cards with create/detail/delete
- AgentDetailPage: API key management, MCP config snippet (Streamable HTTP URL)
- MeetingsPage: List + create meetings
- Dark theme, API client with JWT auth

### Block 8: Claude Agent SDK Example
- Created `examples/meeting-assistant-agent/` with `agent.py` and `README.md`
- Uses Streamable HTTP URL (`http://localhost:3001/mcp`) to connect to MCP server
- System prompt drives behavior — fully configurable

### Block 9: Integration Test
- Created `scripts/test_e2e_full_stack.py` — 11-step test covering register → login → create agent → generate key → exchange token → create meeting → create task → verify

## Test Plan
See `docs/TEST_PLAN_Auth_MCP_Frontend.md` for the full test plan with 11 test sections covering database migration, auth flow, agent CRUD, API keys, token exchange, MCP server, frontend, E2E automation, Claude Agent SDK integration, and security checks.

## Work Remaining
- Run `uv sync --all-packages` to install new dependencies
- Run `uv run alembic upgrade head` to apply the migration
- Execute the test plan: `docs/TEST_PLAN_Auth_MCP_Frontend.md`
- Run `scripts/test_e2e_full_stack.py` against live services
- `npm install` in `web/` directory and verify frontend
- Build and test the Docker MCP server container (`docker compose up mcp-server`)
- Add pytest unit tests for auth, agent CRUD, key management
- OAuth (Google/GitHub) login — deferred to future milestone
- Agent marketplace, billing — deferred

## Lessons Learned
- MCP Python SDK supports `stateless_http=True, json_response=True` for production — no session persistence needed
- `mcp.run(transport="streamable-http")` with `host` and `port` params on FastMCP constructor
- For Docker MCP server, use `host.docker.internal` to reach host services
- `pydantic[email]` provides `EmailStr` for email validation in auth schemas
- API key pattern: `cvn_` prefix + 32 hex chars, SHA-256 hash stored in DB, raw key shown once
- Token exchange pattern bridges user auth (API keys) with gateway auth (JWTs) cleanly
