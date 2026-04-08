# Pre-Release Sprint Plan

> Pick this up in a fresh session: "Execute the pre-release sprint plan in `internal-docs/development/PRE-RELEASE-SPRINT-PLAN.md`"

## Context

The TASKLIST.md has been updated with new "Pre-Release Critical" and "Pre-Release High Priority" sections (password reset, email verification, error boundary, monitoring, mobile nav, SEO, billing usage endpoint). These need to be implemented alongside the remaining April Sprint items 1-5.

Worktrees have been cleaned up — main is clean at commit `1349bd6`.

## Team Structure (5 teammates)

### 1. `auth` — Auth & Account Security
**Type:** general-purpose (needs Edit, Write, Bash)
**Migration coordinator** — this agent owns all Alembic migrations to avoid chain conflicts.

Tasks:
- **Password Reset Flow** — Add `password_reset_token` + `password_reset_expires` columns (migration), `POST /v1/auth/forgot-password`, `POST /v1/auth/reset-password`, email dispatch integration (SendGrid/SES), frontend pages (`ForgotPasswordPage.tsx`, `ResetPasswordPage.tsx`), routes in `App.tsx`, rate limiting (3/hr per email)
- **Email Verification** — Add `email_verified` + `email_verification_token` columns (migration), send on register, `GET /v1/auth/verify-email?token=...`, gate premium features, resend endpoint with rate limiting
- **Account Lockout** — 5 failed attempts → 15-min cooldown (Redis-backed), log attempts to audit trail, rate limit by IP on `/auth/login` and `/auth/register`

Key files:
- `services/api-server/src/api_server/routes/auth.py`
- `services/api-server/src/api_server/auth.py`
- `packages/kutana-core/src/kutana_core/database/models.py`
- `alembic/versions/` (new migration)
- `web/src/pages/LoginPage.tsx`, `RegisterPage.tsx`
- `web/src/App.tsx`
- `web/src/api/auth.ts`
- `.env.example`, `services/api-server/src/api_server/deps.py` (add SMTP env vars)

### 2. `frontend` — Frontend UX & Meeting UI
**Type:** general-purpose

Tasks:
- **Error Boundary & 404** — `ErrorBoundary.tsx` wrapper, `NotFoundPage.tsx`, catch-all route `<Route path="*">` in `App.tsx`, global API error toast handler
- **Mobile Navigation** — Hamburger menu in `LandingNav.tsx` (`md:hidden` toggle), slide-out drawer, backdrop dismiss. Also check `Layout.tsx` sidebar for mobile
- **SEO & Meta Tags** — `<meta name="description">`, OG tags, Twitter cards in `web/index.html`, `robots.txt` + `sitemap.xml` in `web/public/`, favicon set (replace `vite.svg` with Kutana K icon)
- **Turn Management & Chat UI** (April item 5) — Speaker queue panel, hand-raise button, meeting chat panel, participant status indicators, WebSocket event integration in `MeetingRoomPage.tsx`

Key files:
- `web/src/App.tsx`
- `web/src/components/Layout.tsx`
- `web/src/components/landing/LandingNav.tsx`
- `web/src/pages/MeetingRoomPage.tsx`
- `web/index.html`
- `web/public/` (new: robots.txt, sitemap.xml, favicons)

### 3. `platform` — Agent Platform (April items 1-3)
**Type:** general-purpose

Tasks:
- **Agent Capability Declaration** (April item 1) — Extend `kutana_join_meeting` with `audio_capability` param, `tts_voice_id` override, gateway routes audio by capability, participant events include capability field, update OpenClaw plugin, integration tests
- **Voice Agent Audio Sidecar** (April item 2) — `/v1/audio/{session_id}` WebSocket endpoint, Bearer JWT auth, PCM16 LE 16kHz 20ms frames, mixed-minus mixing, VAD filter, integration tests
- **MCP Tool Prefix Standardization** (April item 3) — Rename bare tool names → `kutana_` prefix, update OpenClaw plugin, update examples, update tests

Key files:
- `services/mcp-server/src/mcp_server/tools/`
- `services/agent-gateway/src/agent_gateway/`
- `services/agent-gateway/src/agent_gateway/protocol.py`
- `services/agent-gateway/src/agent_gateway/session.py`
- `packages/kutana-core/src/kutana_core/`

### 4. `infra` — Monitoring, Logging & Billing
**Type:** general-purpose

Tasks:
- **Monitoring & Observability** — Integrate Sentry SDK (backend `sentry-sdk[fastapi]` + frontend `@sentry/react`), add `SENTRY_DSN` to `.env.example` + Settings + Helm, structured JSON logging across services, X-Request-ID propagation, Prometheus metrics endpoints, Slack webhook for alerts
- **Billing Usage Endpoint** — `GET /v1/billing/usage` returning `UsageRecordORM` data grouped by resource_type + billing_period, update `BillingPage.tsx` to fetch real data (replace hardcoded `usedMinutes: 0`), usage breakdown visualization
- **Stripe Webhook Secret** — Set in `charts/kutana/values-secrets.yaml` (coordinate with Jonathan for actual value)

Key files:
- `services/api-server/src/api_server/deps.py` (Settings)
- `services/api-server/src/api_server/routes/billing.py`
- `web/src/pages/BillingPage.tsx`
- `web/src/api/billing.ts`
- `.env.example`
- `charts/kutana/values.yaml`, `values-secrets.yaml`
- All service `main.py` files (logging setup)

### 5. `docs` — Developer Onboarding Documentation (April item 4)
**Type:** general-purpose

Tasks:
- **Claude Code Channel Setup Guide** — `docs/integrations/CLAUDE_CODE_CHANNEL.md` (API key → settings.json → first join, end-to-end)
- **Voice Agent Quickstart** — `docs/integrations/VOICE_AGENT_QUICKSTART.md` (sidecar, PCM16, VAD)
- **TTS Agent Quickstart** — `docs/integrations/TTS_AGENT_QUICKSTART.md` (tts_enabled, voice assignment, start_speaking)
- **Update Example Templates** — Update `internal-docs/examples/meeting-assistant-agent/` with new capability declaration + `kutana_` prefix
- **Developer Onboarding Checklist** — `docs/SETUP_GUIDE.md`

Note: docs agent should coordinate with platform agent — wait for MCP prefix rename and capability declaration to land before finalizing tool names in docs.

## Task Dependencies

```
auth (migrations) ← no blockers, start immediately
frontend (error boundary, mobile nav, SEO) ← no blockers, start immediately
frontend (turn management UI) ← blocked by platform finishing MCP tools
platform (items 1-3) ← no blockers, start immediately
infra (monitoring, billing) ← no blockers, start immediately
docs (all guides) ← blocked by platform finishing items 1-3 (needs final tool names)
```

## Migration Coordination

**auth** is the migration coordinator. If any other agent needs schema changes, they must communicate requirements to auth, who creates migrations in sequence. This prevents Alembic chain branching.

## Execution Command

```
Create team "pre-release-sprint" with 5 teammates:

1. Agent(name="auth", team_name="pre-release-sprint") — auth + account security
2. Agent(name="frontend", team_name="pre-release-sprint") — error boundary, mobile nav, SEO, turn mgmt UI
3. Agent(name="platform", team_name="pre-release-sprint") — agent capability, audio sidecar, MCP prefix
4. Agent(name="infra", team_name="pre-release-sprint") — monitoring, logging, billing usage
5. Agent(name="docs", team_name="pre-release-sprint") — developer onboarding guides

Create tasks per teammate, set dependencies (docs blocked by platform), assign owners, let them run.
```

## Verification

After all tasks complete:
1. `uv run ruff check .` — no lint errors
2. `uv run mypy --strict .` — no type errors  
3. `uv run pytest -x -v` — all tests pass
4. `pnpm --prefix web run tsc --noEmit` — no frontend type errors
5. Build and deploy to dev cluster
6. Manual smoke test: register → verify email → login → create meeting → billing page shows usage
7. Test password reset flow end-to-end
8. Test mobile landing page nav
9. Check OG tags with social media debugger
10. Verify Sentry receives test error
