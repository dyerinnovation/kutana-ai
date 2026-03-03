# Convene AI — Development Task List

> This file is the task queue for both manual and scheduled development sessions.
> The daily build sprint picks the next unchecked, unlocked item and implements it.
>
> **Legend:**
> - `[ ]` — Not started (eligible for scheduled pickup)
> - `[x]` — Completed
> - `🔒` — Locked (Jonathan is working on this — skip it)

---

## Phase 1A: Foundation — Monorepo & Domain Models (Steps 1-2)

- [x] Initialize uv workspace with root pyproject.toml
- [x] Create package directory structure (convene-core, convene-providers, convene-memory)
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
- [x] Implement event definitions (convene-core/events/definitions.py)
- [x] Create SQLAlchemy 2.0 ORM models for all domain entities
- [x] Set up Alembic configuration with async support
- [x] Create initial Alembic migration

## Phase 1B: Provider Interfaces & Implementations (Step 3)

- [x] Implement STTProvider abstract base class
- [x] Implement TTSProvider abstract base class
- [x] Implement LLMProvider abstract base class
- [x] Implement AssemblyAI streaming STT provider (WebSocket + speaker diarization)
- [x] Implement Deepgram STT provider (alternative provider)
- [x] Implement Anthropic LLM provider (Claude tool_use for structured extraction)
- [x] Implement provider registry with factory pattern
- [x] Write integration tests for provider registry

## Phase 1C: Twilio Audio Pipeline (Step 4)

- [x] Implement MeetingDialer (outbound call + DTMF meeting code entry)
- [x] Implement TwilioHandler (FastAPI WebSocket for Media Streams)
- [x] Implement AudioPipeline (μ-law 8kHz → PCM16 16kHz transcoding)
- [x] Implement Redis Streams publisher for transcript segments
- [x] Implement meeting end detection (silence threshold + hangup handling)
- [x] Implement graceful cleanup and audio buffering on STT failure
- [x] Write end-to-end test for audio pipeline with mock Twilio

## Phase 1D: Task Extraction & Memory (Step 5)

- [x] Wire STT provider into audio service lifespan (provider registry + config)
- [x] Implement Redis Streams consumer for transcript.segment.final events
- [ ] Implement transcript segment windowing (3-5 min windows with overlap)
- [ ] Complete LLM-powered task extraction pipeline (wire LLM provider + extractor)
- [ ] Implement task persistence to PostgreSQL (replace placeholder in extractor)
- [ ] Implement task.created / task.updated event emission
- [x] **🏁 Milestone M1: Audio → Transcript → Redis (live dial-in test)** — see `docs/milestone-testing/M1_Live_Test.md`
- [ ] **🏁 Milestone M2: Redis → Task Extraction → PostgreSQL (integration test)**
- [ ] Implement working memory layer (Redis hash per active meeting)
- [ ] Implement short-term memory layer (recent meeting queries)
- [ ] Implement long-term memory layer (pgvector embeddings of meeting summaries)
- [ ] Implement structured state layer (task/decision indexes)
- [ ] Implement memory context builder (assembles relevant context for LLM)

## Phase 1E: API & Dashboard (Step 6)

- [ ] Wire meeting CRUD routes to PostgreSQL (replace placeholder data)
- [ ] Wire task CRUD routes to PostgreSQL (replace placeholder data)
- [ ] Implement agent config routes
- [ ] Implement meeting orchestration — POST /meetings/{id}/dial triggers Twilio call
- [ ] Implement meeting summary generation on meeting.ended event
- [ ] Implement TTS audio synthesis endpoint — GET /meetings/{id}/summary/audio
- [ ] Implement WebSocket endpoint for live transcript streaming
- [ ] Implement API authentication middleware
- [ ] Implement CORS and rate limiting middleware
- [ ] Create OpenAPI schema documentation
- [ ] Scaffold React dashboard (Vite + React + Tailwind)
- [ ] Implement meeting list view (upcoming, active, completed)
- [ ] Implement live transcript view for active meetings
- [ ] Implement task board (kanban: pending, in progress, done, blocked)
- [ ] Implement meeting detail view (transcript + extracted tasks)

## Telephony Roadmap

- [ ] Evaluate SIP trunk providers (Telnyx, Vonage) for cost reduction
- [ ] Implement managed phone number provisioning (users don't touch Twilio)

## Phase 1F: Voice Output

- [x] Implement Cartesia TTS provider
- [x] Implement ElevenLabs TTS provider
- [ ] Implement bidirectional audio pipeline (Twilio → STT + TTS → Twilio)
- [ ] Implement agent speaking logic (when to interject, progress reports)
- [ ] Implement voice activity detection for turn-taking
- [ ] **🏁 Milestone M2: Live demo — real meeting, real STT/LLM, TTS readback**

## Phase 2: Agent Gateway & MCP (The Core Differentiator)

- [x] Design Agent Gateway WebSocket protocol (control messages, audio frames, data channels)
- [x] Implement Agent Gateway FastAPI service with WebSocket endpoint
- [x] Implement agent authentication (API key validation on connect)
- [x] Implement capability negotiation (listen, speak, push-ui, access-transcript)
- [x] Implement audio stream routing (agent → STT pipeline)
- [ ] Implement audio stream routing (meeting audio → connected agents)
- [ ] Implement structured data channel (metadata, context, real-time updates)
- [x] Implement agent presence management (join, leave, heartbeat, timeout)
- [ ] Implement multi-agent per meeting support
- [ ] Implement MCP server using Python MCP SDK
- [ ] Implement MCP tools: list_meetings, join_meeting, leave_meeting
- [ ] Implement MCP tools: get_transcript, get_tasks, send_message, send_audio
- [ ] Implement MCP tools: get_participants, get_meeting_context, create_task
- [ ] Implement MCP resources: meeting://{id}, meeting://{id}/transcript, meeting://{id}/tasks
- [ ] Write MCP server documentation and examples
- [ ] Create Agent Python SDK (ConveneAgent class, async API, audio helpers)
- [ ] Publish SDK to PyPI as `convene-ai`
- [ ] Write SDK documentation and example agents
- [ ] Implement agent registration API (name, capabilities, description, owner)
- [ ] Implement agent API key generation and management
- [ ] Implement per-agent rate limiting and usage tracking
- [ ] **🏁 Milestone M3: Agent connects via Gateway, receives audio, sends transcript events**
- [ ] **🏁 Milestone M4: MCP client (Claude) joins a meeting and extracts tasks via MCP tools**

## Phase 3: User Authentication & Billing

- [ ] Design database schema for users, workspaces, and memberships
- [ ] Implement user registration (email + password, email verification)
- [ ] Implement login / logout with JWT token management
- [ ] Implement OAuth login (Google, GitHub)
- [ ] Implement workspace creation and settings
- [ ] Implement workspace invitations (invite by email, accept/decline)
- [ ] Implement role-based access control (owner, admin, member)
- [ ] Implement user profile management
- [ ] Implement API key generation for developer access
- [ ] Integrate Stripe for payment processing
- [ ] Implement subscription plans (Free, Developer, Pro, Team, Enterprise)
- [ ] Implement usage tracking (agent-minutes, meeting count, storage)
- [ ] Implement usage-based billing metering for Developer tier
- [ ] Implement plan upgrade/downgrade flows
- [ ] Implement billing dashboard (current plan, usage, invoices, payment method)
- [ ] Implement free tier limit enforcement
- [ ] Implement Stripe webhook handlers (payment success/failure, subscription changes)
- [ ] **🏁 Milestone M5: User signs up, creates workspace, subscribes to paid plan**

## Phase 4: Meeting Platform (WebRTC + Browser UI)

- [ ] Deploy LiveKit server (Docker, local dev configuration)
- [ ] Implement LiveKit room creation and management
- [ ] Implement token generation for browser participants
- [ ] Implement audio routing: LiveKit room → Audio Service STT pipeline
- [ ] Implement audio routing: Agent Gateway audio → LiveKit room (agent speech)
- [ ] Implement meeting lifecycle management (create, admit, end, cleanup)
- [ ] Scaffold React meeting web client (Vite + React + LiveKit SDK + Tailwind)
- [ ] Implement meeting join flow (link-based, authenticated)
- [ ] Implement video/audio controls (mute, camera, screen share, leave)
- [ ] Implement participant list (humans + AI agents with status indicators)
- [ ] Implement meeting lobby / waiting room
- [ ] Implement real-time collaboration sidebar (task feed, decision log, agent activity)
- [ ] Implement collaborative task editing during meeting (mark done, reassign, notes)
- [ ] Implement meeting context panel (previous meeting tasks, relevant history)
- [ ] Implement meeting creation flow (title, time, participants, recurrence)
- [ ] Implement meeting invitation system (email invites with join links)
- [ ] Implement meeting recording controls and consent management
- [ ] Implement meeting history view (past meetings, transcripts, tasks)
- [ ] Implement meeting detail view (transcript replay, task timeline, decisions)
- [ ] **🏁 Milestone M6: Team creates a meeting, humans join via browser, agent joins via Gateway, tasks extracted in real-time**

## Phase 5: Dashboard & Integrations

- [ ] Implement workspace dashboard (upcoming meetings, recent activity, task overview)
- [ ] Implement task board view (kanban: pending, in progress, done, blocked)
- [ ] Implement task detail view (source meeting, assignee, timeline)
- [ ] Implement team member view (commitments, completion rate)
- [ ] Implement meeting analytics (frequency, duration, extraction rate)
- [ ] Implement notification center (task assignments, overdue items, meeting reminders)
- [ ] Implement search (across meetings, transcripts, tasks, decisions)
- [ ] Implement data export (CSV, JSON)
- [ ] Implement Slack integration (summaries, task notifications, slash commands)
- [ ] Implement Linear integration (bidirectional task sync)
- [ ] Implement Jira integration (bidirectional task sync)
- [ ] Implement GitHub integration (link tasks to PRs)
- [ ] Implement Notion integration (push meeting summaries and task tables)
- [ ] Implement webhook API (generic event push for custom integrations)
- [ ] Implement Zapier / Make triggers (meeting.ended, task.created, etc.)
- [ ] Implement calendar sync (push Convene meetings to Google Calendar / Outlook)
- [ ] **🏁 Milestone M7: Full product experience — dashboard, integrations, analytics**

## Phase 6: Agent Marketplace & Voice

- [ ] Design agent marketplace data model (listings, reviews, installations)
- [ ] Implement agent marketplace UI (browse, search, install agents)
- [ ] Implement agent publishing workflow for developers
- [ ] Implement agent reviews and ratings
- [ ] Implement pre-built agent personas (Standup Agent, Decision Tracker, Client Meeting Agent)
- [ ] Implement TTS integration (Cartesia primary, ElevenLabs fallback)
- [ ] Implement bidirectional audio pipeline (meeting audio → STT + TTS → meeting audio)
- [ ] Implement standup report generation (pre-meeting context assembly, LLM report)
- [ ] Implement speaking interaction protocol (cued speaking, silence detection, interruption handling)
- [ ] Implement real-time task confirmation (speak to confirm commitments)
- [ ] Implement voice activity detection for turn-taking
- [ ] **🏁 Milestone M8: Agent speaks in a live meeting, marketplace has 3+ published agents**

## Phase 7: Advanced AI & Platform Hardening

- [ ] Implement multi-turn dialogue engine (conversation state machine, context window)
- [ ] Implement conflict & dependency detection (scheduling conflicts, overcommitment)
- [ ] Implement meeting facilitation (standup prompts, time boxing, agenda tracking)
- [ ] Implement rate limiting on all API endpoints
- [ ] Implement comprehensive error handling and user-friendly error messages
- [ ] Implement audit logging (who did what, when)
- [ ] Implement data retention policies and deletion (GDPR compliance)
- [ ] Implement SSO (SAML/OIDC) for enterprise
- [ ] Implement admin panel for workspace owners
- [ ] Implement monitoring, alerting, and automated backups
- [ ] Write deployment documentation (Docker, Kubernetes, cloud guides)
- [ ] Load testing and capacity planning
- [ ] **🏁 Milestone M9: Platform passes security review, ready for enterprise pilots**

---

## Notes

### Milestone Reference

- **M1 & M2:** Foundation phases (Phase 1D, 1F) — audio pipeline and voice output
- **M3 & M4:** Agent Gateway and MCP integration (Phase 2)
- **M5:** User auth and billing (Phase 3)
- **M6:** Browser-based meeting platform (Phase 4)
- **M7:** Dashboard and third-party integrations (Phase 5)
- **M8:** Agent marketplace and voice output (Phase 6)
- **M9:** Advanced AI and enterprise hardening (Phase 7)

### CoWork Edit Protocol

**Task selection:** CoWork picks the first unchecked (`- [ ]`), unlocked (no 🔒) item in the current phase.

**Completion registration:**
1. Check off the item: `- [ ]` → `- [x]`
2. Append an entry to `docs/PROGRESS.md` (never overwrite previous entries)
3. Update `docs/HANDOFF.md` with shift-change notes

**Branch naming:** `scheduled/YYYY-MM-DD-{slug}` (e.g., `scheduled/2026-02-27-pydantic-models`)

**Lock protocol:** Only Jonathan adds or removes 🔒. CoWork must never lock or unlock items.

**Quality gate:** All of the following must pass before checking off an item:
- `uv run ruff check .` — no lint errors
- `uv run mypy --strict .` — no type errors
- `uv run pytest -x -v` — all tests pass

If quality checks fail after 3 fix attempts, document the failure in PROGRESS.md, note it as a blocker in HANDOFF.md, and stop. Do not check off the item.
