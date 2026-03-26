# Fix Signup 404 — Plan End

## Work Completed

- **Diagnosed root cause**: nginx ingress `rewrite-target: /$2` strips `/api` prefix, so api-server received `/v1/auth/register` but expected `/api/v1/auth/register` → 404
- **Fixed api-server `main.py`**: Changed router prefix from `/api/v1` to `/v1` on all 7 routers (auth, meetings, tasks, agents, agent_keys, agent_templates, token)
- **Fixed mcp-server `api_client.py`**: Updated all URL paths from `/api/v1/` to `/v1/` for direct in-cluster calls (no ingress rewrite)
- **Built, pushed, and deployed** both api-server and mcp-server images
- **Verified**: signup returns 201, login returns 200, health returns 200

## Work Remaining

- None — signup is working

## Lessons Learned

- **Ingress rewrite-target `/$2` strips the first path segment.** When nginx ingress uses `path: /api(/|$)(.*)` with `rewrite-target: /$2`, the app receives requests without the `/api` prefix. The app's internal routes must NOT include the ingress routing prefix.
- **External vs internal URL paths differ**: External clients (browser, CLI) use `/api/v1/...` (ingress adds `/api`). Internal clients calling api-server directly use `/v1/...` (no ingress).
- **Health endpoint was a red herring**: `/api/health` → rewrite → `/health` worked because health is mounted without prefix. This masked the fact that all prefixed routes were broken.
