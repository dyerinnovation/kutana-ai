# Auth & API Key Patterns

## User Authentication
- `api_server/auth.py` — bcrypt password hashing, JWT token creation/validation
- `api_server/auth_deps.py` — auth dependencies for route injection
- `CurrentUser = Annotated[UserORM, Depends(get_current_user)]` — Bearer JWT only (browser users)
- `CurrentUserOrAgent = Annotated[UserORM, Depends(get_current_user_or_agent)]` — accepts Bearer JWT **or** X-API-Key (agents)
- JWT claims: `sub` (user_id UUID), `email`, `type: "user"`, `iat`, `exp`
- Secret: `Settings.jwt_secret`

## Dual Auth (CurrentUserOrAgent)
- Used on meetings endpoints so both browser users and agents (channel server, MCP clients) can access them
- **Bearer JWT path:** Decodes JWT, extracts `sub` as user_id, looks up `UserORM`
- **X-API-Key path:** Hashes key, looks up `AgentApiKeyORM` by hash, resolves `user_id` FK to `UserORM`
- `validate_api_key()` in `auth_deps.py` — shared helper for API key validation (hash check, revocation, expiry, audit logging)
- Endpoints that should remain browser-only (e.g. `update_meeting` PATCH) keep `CurrentUser`

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
