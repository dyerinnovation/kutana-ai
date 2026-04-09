# Kutana AI — Development Task List

> This file is the task queue for both manual and scheduled development sessions.
> The daily build sprint picks the next unchecked, unlocked item (or block) and implements it.
>
> **Legend:**
> - `[ ]` — Not started (eligible for scheduled pickup)
> - `[x]` — Completed
> - `🔒` — Locked (Jonathan is working on this — skip it)
> - `🔗 BLOCK:` — Multi-task block (CoWork handles all sub-tasks in one session)
> - `(deprecated)` — Removed in agent-first refactor, kept for historical record

---

## Completed Foundation

> Phases 1A–1C are complete. Collapsed here for reference.

<details>
<summary>Phase 1A: Foundation — Monorepo & Domain Models ✅</summary>

- [x] Initialize uv workspace with root pyproject.toml
- [x] Create package directory structure (kutana-core, kutana-providers, kutana-memory)
- [x] Create service directory structure (api-server, audio-service, task-engine, worker)
- [x] Set up docker-compose.yml with PostgreSQL 16 (pgvector) and Redis 7
- [x] Create .env.example with all environment variables
- [x] Set up ruff.toml and mypy.ini with strict settings
- [x] Create CI workflow (.github/workflows/ci.yml) — ruff, mypy, pytest
- [x] Implement Meeting Pydantic model with validators
- [x] Implement Participant Pydantic model
- [x] Implement Task Pydantic model with status transition validators
- [x] Implement Decision Pydantic model
- [x] Implement TranscriptSegment Pydantic model
- [x] Implement AgentConfig Pydantic model
- [x] Implement event definitions (kutana-core/events/definitions.py)
- [x] Create SQLAlchemy 2.0 ORM models for all domain entities
- [x] Set up Alembic configuration with async support
- [x] Create initial Alembic migration

</details>

<details>
<summary>Phase 1B: Provider Interfaces & Implementations ✅</summary>

- [x] Implement STTProvider abstract base class
- [x] Implement TTSProvider abstract base class
- [x] Implement LLMProvider abstract base class
- [x] Implement AssemblyAI streaming STT provider (WebSocket + speaker diarization)
- [x] Implement Deepgram STT provider (alternative provider)
- [x] Implement Anthropic LLM provider (Claude tool_use for structured extraction)
- [x] Implement provider registry with factory pattern
- [x] Write integration tests for provider registry

</details>

<details>
<summary>Phase 1C: Audio Pipeline ✅ (partially deprecated)</summary>

- [x] Implement MeetingDialer (deprecated — removed in agent-first refactor)
- [x] Implement TwilioHandler (deprecated — removed in agent-first refactor)
- [x] Implement AudioPipeline (μ-law 8kHz → PCM16 16kHz transcoding)
- [x] Implement Redis Streams publisher for transcript segments
- [x] Implement meeting end detection (deprecated — removed in agent-first refactor)
- [x] Implement graceful cleanup and audio buffering on STT failure
- [x] Write end-to-end test for audio pipeline with mock Twilio

</details>

---

## Pre-Release Critical — Production Blockers

> These items must ship before any public launch. Ordered by severity.

- [ ] 🔗 BLOCK: Password Reset Flow
  - [ ] Add `password_reset_token` and `password_reset_expires` columns to UserORM (Alembic migration)
  - [ ] Implement `POST /v1/auth/forgot-password` — generates time-limited reset token, sends email
  - [ ] Implement `POST /v1/auth/reset-password` — validates token, updates password hash
  - [ ] Integrate email dispatch service (SendGrid or AWS SES — env vars: `SMTP_HOST`, `SMTP_FROM`, `SMTP_API_KEY`)
  - [ ] Create password reset email template (HTML + plain text)
  - [ ] Build frontend `ForgotPasswordPage.tsx` and `ResetPasswordPage.tsx`
  - [ ] Add routes `/forgot-password` and `/reset-password/:token` to `App.tsx`
  - [ ] Rate limit reset requests (3/hour per email)

- [ ] 🔗 BLOCK: Email Verification
  - [ ] Add `email_verified` boolean and `email_verification_token` to UserORM (Alembic migration)
  - [ ] Send verification email on registration
  - [ ] Implement `GET /v1/auth/verify-email?token=...` — marks email as verified
  - [ ] Gate premium features on `email_verified=true` (allow login but show banner)
  - [ ] Build email verification landing page component
  - [ ] Add "Resend verification" endpoint with rate limiting

- [ ] 🔗 BLOCK: Error Boundary & 404 Page
  - [ ] Create `ErrorBoundary.tsx` component wrapping the app (catch React render errors, show recovery UI)
  - [ ] Create `NotFoundPage.tsx` with navigation back to dashboard/landing
  - [ ] Add `<Route path="*" element={<NotFoundPage />} />` catch-all to `App.tsx`
  - [ ] Add API error toast notifications (global error handler in API client layer)

- [ ] 🔗 BLOCK: Account Security Hardening
  - [ ] Implement account lockout after 5 failed login attempts (15-min cooldown, stored in Redis)
  - [ ] Add `failed_login_attempts` and `locked_until` to UserORM or Redis
  - [ ] Log failed login attempts to audit trail
  - [ ] Add rate limiting by IP on `/auth/login` and `/auth/register` (not just API key)

- [ ] 🔗 BLOCK: Monitoring & Observability
  - [ ] Integrate Sentry for error tracking (backend + frontend)
  - [ ] Add `SENTRY_DSN` env var to `.env.example`, Settings class, and Helm values
  - [ ] Implement structured JSON logging across all services (replace print/basic logging)
  - [ ] Add request tracing headers (X-Request-ID propagation across services)
  - [ ] Set up health check dashboard (Prometheus metrics endpoint on each service)
  - [ ] Add Slack webhook for deploy notifications and critical alerts

---

## Pre-Release High Priority

> Should ship before public launch but not strictly blocking.

- [ ] 🔗 BLOCK: Mobile Navigation
  - [ ] Add hamburger menu toggle to `LandingNav.tsx` (visible on `md:hidden`)
  - [ ] Implement slide-out mobile nav drawer with all nav links + auth actions
  - [ ] Add swipe-to-close and backdrop click dismiss
  - [ ] Ensure mobile nav works in both landing page and authenticated layout

- [ ] 🔗 BLOCK: SEO & Social Meta Tags
  - [ ] Add `<meta name="description">` to `index.html`
  - [ ] Add Open Graph tags (`og:title`, `og:description`, `og:image`, `og:url`)
  - [ ] Add Twitter card meta tags
  - [ ] Create `robots.txt` and `sitemap.xml` in `web/public/`
  - [ ] Add proper favicon set (apple-touch-icon, favicon-32x32, favicon-16x16)
  - [ ] Replace `vite.svg` with Kutana K icon favicon

- [ ] 🔗 BLOCK: Billing Usage Endpoint
  - [ ] Implement `GET /v1/billing/usage` — returns `UsageRecordORM` data grouped by resource type and billing period
  - [ ] Update `BillingPage.tsx` to fetch real usage data (replace hardcoded `usedMinutes: 0`)
  - [ ] Add usage breakdown visualization (agent minutes, feed minutes, meeting count)
  - [ ] Set `STRIPE_WEBHOOK_SECRET` in Helm `values-secrets.yaml` (coordinate with Jonathan for prod value)

---

## April Release Sprint — Target: April 6-10, 2026

> P0 features enabling full multi-agent participation: turn management, meeting chat, MCP tools, and Claude Code channel integration.

- [x] 🔗 BLOCK: Security Infrastructure (P0) ✅
- [x] 🔗 BLOCK: Turn Management MCP Tools ✅
- [x] 🔗 BLOCK: start_speaking + MCP namespace + join capabilities ✅
- [x] 🔗 BLOCK: Chat & Status MCP Tools ✅
- [x] 🔗 BLOCK: Claude Code Channel Integration ✅
- [x] 🔗 BLOCK: kutana_start_speaking MCP Tool (P0) ✅
- [x] 🔗 BLOCK: TTS Pipeline — Gateway TTS Engine (P0) ✅

- [ ] 🔗 BLOCK: Agent Capability Declaration (P0)
  - [ ] Extend `kutana_join_meeting` with `audio_capability` parameter (`text_only`, `tts_enabled`, `voice`)
  - [ ] Extend `kutana_join_meeting` with `tts_voice_id` optional override parameter
  - [ ] Gateway routes audio based on declared capability at join time
  - [ ] Participant events include `audio_capability` field for visibility
  - [ ] Update OpenClaw plugin with new `audio_capability` parameter
  - [ ] Integration tests: each capability value routes audio correctly

- [ ] 🔗 BLOCK: Voice Agent Audio Sidecar (P0)
  - [ ] Add sidecar WebSocket endpoint to agent-gateway (`/v1/audio/{session_id}`)
  - [ ] Sidecar auth: Bearer JWT in Authorization header (same session JWT from join_meeting)
  - [ ] Frame format: raw PCM16 LE 16kHz mono, 20ms chunks (640 bytes)
  - [ ] Mixed-minus mixing: agent receives room audio minus its own stream
  - [ ] VADFilter wrapper: suppress silence frames from agent → STT pipeline
  - [ ] Continuous 20ms frame streaming from gateway to agent (silence-padded)
  - [ ] Integration tests: voice agent joins, sends audio, receives room audio, mixed-minus verified

- [ ] 🔗 BLOCK: MCP Tool Prefix Standardization (P0)
  - [ ] Rename all MCP tools from bare names to `kutana_` prefix (e.g., `join_meeting` → `kutana_join_meeting`)
  - [ ] Update OpenClaw plugin with renamed tools
  - [ ] Update example agents with new tool names
  - [ ] Update all integration tests to use `kutana_` prefix

- [ ] 🔗 BLOCK: Developer Onboarding Documentation (P0)
  - [ ] Write `docs/integrations/CLAUDE_CODE_CHANNEL.md` — end-to-end setup guide
  - [ ] Write `docs/integrations/VOICE_AGENT_QUICKSTART.md` — voice agent setup
  - [ ] Write `docs/integrations/TTS_AGENT_QUICKSTART.md` — TTS agent setup
  - [ ] Update example agent templates with new capability declaration + `kutana_` prefix
  - [ ] Add developer onboarding checklist to `docs/SETUP_GUIDE.md`

- [ ] 🔗 BLOCK: Frontend — Turn Management & Chat UI
  - [ ] Speaker queue panel (ordered list, current speaker highlighted, position indicators)
  - [ ] Hand-raise button for human participants in the meeting room
  - [ ] Meeting chat panel (send/receive messages, participant attribution, timestamps)
  - [ ] Participant list updated to show agent status (in queue, speaking, idle)
  - [ ] Real-time state updates via WebSocket events

- [ ] **🏁 Milestone M_APRIL: All 4 E2E scenarios pass + security gate**
  - [ ] Scenario A: 1 human + 1 agent
  - [ ] Scenario B: 2 humans + 1 agent
  - [ ] Scenario C: 1 human + multiple agents
  - [ ] Scenario D: multiple humans + multiple agents
  - [ ] Security gate: prompt injection rejected, cross-meeting access denied, rate limits enforced

---

## Phase 1: Core AI Pipeline

- [x] Wire STT provider into audio service lifespan
- [x] Implement Redis Streams consumer for transcript.segment.final events
- [x] Implement transcript segment windowing
- [x] Complete LLM-powered task extraction pipeline
- [x] Implement task persistence to PostgreSQL
- [x] Implement task.created / task.updated event emission
- [x] **🏁 Milestone M1: Audio → Transcript → Redis** ✅
- [ ] **🏁 Milestone M2: Redis → Task Extraction → PostgreSQL (integration test)**

---

## Phase 2: Agent Platform ✅ (complete 2026-03-07)

<details>
<summary>Phase 2 completed items (collapsed)</summary>

- [x] Design Agent Gateway WebSocket protocol
- [x] Implement Agent Gateway FastAPI service with WebSocket endpoint
- [x] Implement agent authentication
- [x] Implement capability negotiation
- [x] Implement audio stream routing
- [x] Implement agent presence management
- [x] **🏁 Milestone M3** ✅
- [x] 🔗 BLOCK: Participant Abstraction & Human Connection Path ✅
- [x] 🔗 BLOCK: Turn Management Infrastructure ✅
- [x] 🔗 BLOCK: Meeting Chat Infrastructure ✅
- [x] 🔗 BLOCK: Agent Modality Support (partial) ✅

</details>

- [ ] 🔗 BLOCK: Agent Gateway Polish
  - [ ] Implement multi-agent per meeting support
  - [ ] Implement audio stream routing (meeting audio → connected agents)
  - [ ] Implement structured data channel

- [ ] 🔗 BLOCK: Agent Registration & Credentials
  - [ ] Implement agent registration API
  - [ ] Implement agent API key generation and management
  - [ ] Implement per-agent rate limiting and usage tracking
  - [ ] Implement credential store (secure key storage, rotation)

- [ ] Refactor AudioBridge cross-service import (known tech debt)

---

## Post-April: Scheduled Agent Participation (F2.9)

- [ ] 🔗 BLOCK: F2.9-A — Observer Mode (MVP)
- [ ] 🔗 BLOCK: F2.9-B — Reporter Mode
- [ ] 🔗 BLOCK: F2.9-C — Active Mode
- [ ] 🔗 BLOCK: F2.9-D — Delegate Mode

---

## Tech Debt: kutana-core Cleanup

- [ ] Audit and clean up `kutana_core` post-managed-agents migration — see `internal-docs/development/kutana-core-audit.md` for the full audit and per-module recommendations (deprecate AgentSession, AgentConfig, AgentParticipant; consolidate agent-related ORM schemas)

---

## Phase 3: Meeting Intelligence & Agent Integration

- [ ] 🔗 BLOCK: Portable Message Bus Abstraction
- [ ] 🔗 BLOCK: Meeting Insight Stream
- [ ] 🔗 BLOCK: Custom Extractors & Cloud Providers
- [ ] 🔗 BLOCK: Agent Context Seeding
- [ ] 🔗 BLOCK: Model Tiering & Cost Architecture

---

## Future Phases (5–11)

> Phase 5: User Platform & Auth · Phase 6: Meeting Platform (WebRTC) · Phase 7: Memory & Intelligence · Phase 8: Cloud Deployment · Phase 9: Voice Output & Dialogue · Phase 10: Ecosystem & Integrations · Phase 11: Hardening

See prior version of this file for full sub-task breakdowns.

---

## Notes

### Milestone Reference

- **M1:** Audio → Transcript → Redis ✅
- **M2:** Redis → Task Extraction → PostgreSQL
- **M3:** Agent connects via Gateway ✅
- **M_APRIL:** All 4 multi-party E2E scenarios pass
- **M4:** MCP client joins a meeting via MCP tools
- **M5:** User signs up, creates workspace, subscribes
- **M6:** Browser-based meeting with agents and humans
- **M7+:** Full product with integrations and marketplace
- **M8:** Enterprise hardening and security review

### TASKLIST Lock Protocol

- **Start:** Add 🔒 to the item
- **Finish:** Replace `- [ ] 🔒` with `- [x]`
- Only the session that locked an item should unlock it
- **Milestone items (🏁)** — check off only when prerequisites pass
