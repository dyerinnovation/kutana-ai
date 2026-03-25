# Auth & API Key Patterns

## User Authentication
- `api_server/auth.py` — bcrypt password hashing, JWT token creation/validation
- `api_server/auth_deps.py` — `get_current_user()` FastAPI dependency (HTTPBearer + JWT decode + DB lookup)
- `CurrentUser = Annotated[UserORM, Depends(get_current_user)]` — type alias for route injection
- JWT claims: `sub` (user_id UUID), `email`, `type: "user"`, `iat`, `exp`
- Secret: `Settings.jwt_secret`

## API Key System
- Format: `cvn_` + 32 hex chars (e.g., `cvn_a1b2c3d4e5f6...`)
- Stored as SHA-256 hash in `agent_api_keys.key_hash`
- `key_prefix` (first 8 chars) stored for display
- Raw key shown ONCE on creation, never stored or retrievable

## Token Exchange (API Key → Gateway JWT)
- `POST /api/v1/token/gateway` with `X-API-Key` header
- Validates key hash against `agent_api_keys` table (checks not revoked)
- Returns a short-lived gateway JWT via `agent_gateway.auth.create_agent_token()`
- This bridges user auth (API keys) with gateway auth (JWTs) without modifying the gateway

## Database Models
- `UserORM` — `users` table (id, email, hashed_password, name, is_active)
- `AgentApiKeyORM` — `agent_api_keys` table (id, key_prefix, key_hash, agent_config_id, user_id, name, revoked_at)
- `AgentConfigORM.owner_id` — FK to `users.id` (nullable for backward compat)
