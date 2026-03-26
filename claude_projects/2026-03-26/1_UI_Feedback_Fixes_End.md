# UI Feedback Fixes — Plan End

## Work Completed

- **Fixed WebSocket "connection failed"**: Changed agent-gateway endpoint from `/human/connect` to `/connect` — ingress strips `/human` via rewrite-target, same pattern as the signup 404 fix
- **Fixed Templates 500**: Created `agent_templates` + `hosted_agent_sessions` tables via Alembic migration + direct SQL on DGX postgres. Seeded 4 default templates (Meeting Notetaker, Technical Scribe, Standup Facilitator, Meeting Summarizer)
- **Restructured sidebar nav**: Dashboard (/) → summary page, Agents (/agents) → user agents + Convene Managed Agents, removed Templates entry, added /templates → /agents redirect
- **New DashboardPage**: Welcome greeting, upcoming meetings card, agents summary card, quick action buttons
- **New AgentsPage**: User agents grid + "Convene Managed Agents" section with category filters and activate modal
- **Removed "Video soon"** placeholder text from meeting room tiles
- **Proportional video tiles**: Dynamic grid sizing based on participant count (1 person fills space, scales down for more)

## Verification

- `GET /api/v1/agent-templates` returns 200 with 4 seed templates
- `GET /api/health` returns 200
- Frontend returns 200
- All 8 pods running with 0 restarts
- TypeScript compiles cleanly

## Lessons Learned

- **Ingress rewrite-target affects ALL services the same way**: `/api` stripped for api-server, `/human` stripped for agent-gateway, `/ws` stripped for websocket. Any FastAPI/Starlette endpoint behind the ingress must NOT include the ingress routing prefix in its path.
- **Running Alembic migrations in K3s**: Can exec directly into the postgres statefulset with psql for one-off migrations. Heredoc over SSH doesn't work well; use individual `-c` commands.
- **Cherry-pick across worktree branches**: When committing on a worktree branch, cherry-pick to main rather than merging to avoid pulling in unrelated worktree commits.
