# Convene AI — Development Task List

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

## Phase 1: Core AI Pipeline

> Extract actionable tasks from meeting transcripts via LLM.

- [x] Wire STT provider into audio service lifespan (provider registry + config)
- [x] Implement Redis Streams consumer for transcript.segment.final events
- [x] Implement transcript segment windowing (3-5 min windows with overlap)
- [ ] Complete LLM-powered task extraction pipeline (wire LLM provider + extractor)
- [x] Implement task persistence to PostgreSQL (replace placeholder in extractor)
- [x] Implement task.created / task.updated event emission
- [x] **🏁 Milestone M1: Audio → Transcript → Redis (live dial-in test)** — see `docs/milestone-testing/M1_Live_Test.md`
- [ ] **🏁 Milestone M2: Redis → Task Extraction → PostgreSQL (integration test)**

---

## Phase 2: Agent Platform

> The core differentiator — AI agents as first-class meeting participants.

- [x] Design Agent Gateway WebSocket protocol (control messages, audio frames, data channels)
- [x] Implement Agent Gateway FastAPI service with WebSocket endpoint
- [x] Implement agent authentication (API key validation on connect)
- [x] Implement capability negotiation (listen, speak, push-ui, access-transcript)
- [x] Implement audio stream routing (agent → STT pipeline)
- [x] Implement agent presence management (join, leave, heartbeat, timeout)
- [x] **🏁 Milestone M3: Agent connects via Gateway, receives audio, sends transcript events** — verified 2026-03-02 (29 segments, Redis XLEN=31)

- [x] 🔗 BLOCK: Participant Abstraction & Human Connection Path
  - [x] Base Participant ABC (human + agent types) in convene-core (`participants/base.py`)
  - [x] Human WebSocket connection endpoint (`/human/connect`) — auto-joins, no capability negotiation
  - [x] HumanSessionHandler — speak + listen + transcribe by default, PCM16 audio forwarding
  - [x] ConnectionManager updated to accept both AgentSessionHandler and HumanSessionHandler
  - [x] MeetingRoomPage.tsx updated to use `/human/connect` (meeting_id in URL, no join_meeting message)
  - [ ] Participant registry per meeting (track connected participants, their type and capabilities)
  - [ ] Participant events on MessageBus (participant.joined, participant.left)
  - [ ] WebRTC/LiveKit integration for production human connections (Phase 5)

- [x] 🔗 BLOCK: Turn Management Infrastructure
  - [x] Define TurnManager ABC in convene-core (raise_turn, release_turn, get_queue, get_active_speaker)
  - [x] Implement RedisTurnManager provider (ordered queue, atomic operations, position tracking)
  - [x] Register TurnManager in provider registry
  - [x] WebSocket events for queue changes (speaker.queue.updated, speaker.changed)
  - [x] Broadcast turn state to all connected participants
  - [x] Auto-transition support (configurable timeout-based speaker advancement)
  - [x] Unit and integration tests for TurnManager

- [x] 🔗 BLOCK: Meeting Chat Infrastructure
  - [x] Define ChatStore ABC in convene-core (send_message, get_messages, subscribe)
  - [x] Implement RedisChatStore provider (message persistence + pub/sub delivery)
  - [x] Register ChatStore in provider registry
  - [x] WebSocket event delivery (chat.message.received)
  - [x] Chat history retrieval with pagination
  - [x] Unit and integration tests for ChatStore

- [ ] 🔗 BLOCK: Agent Gateway Polish
  - [ ] Implement multi-agent per meeting support
  - [ ] Implement audio stream routing (meeting audio → connected agents)
  - [ ] Implement structured data channel (metadata, context, real-time updates)

- [ ] 🔗 BLOCK: Agent Registration & Credentials
  - [ ] Implement agent registration API (name, capabilities, description, owner)
  - [ ] Implement agent API key generation and management
  - [ ] Implement per-agent rate limiting and usage tracking
  - [ ] Implement credential store (secure key storage, rotation)

- [ ] 🔗 BLOCK: Agent Modality Support
  - [ ] Implement Voice-to-Voice agent support (bidirectional audio streaming)
  - [ ] Implement Speech-to-Text agent support (listen + receive transcript feed)
  - [ ] Implement Text-only agent support (transcript feed, no audio)

- [ ] Refactor AudioBridge cross-service import (known tech debt — extract to shared package)

---

## April Release Sprint — Target: April 6-10, 2026

> P0 features enabling full multi-agent participation: **security & trust infrastructure**, turn management, meeting chat, 8 new MCP tools, and Claude Code channel integration.
>
> **Prerequisites (Phase 2 above):** participant registry + events, turn manager, chat store, multi-agent gateway.
>
> **Timeline:** Week 1 (Mar 22–28) backend infra · Week 2 (Mar 29–Apr 4) MCP tools + channel + frontend · Week 3 (Apr 5–11) E2E testing + launch

- [ ] 🔗 BLOCK: Security Infrastructure (P0 — ships with April Release)
  - [ ] Prompt injection defense — `convene-core/security/sanitizer.py` utility; strip control sequences and role-injection patterns from all agent-submitted text before LLM context inclusion
  - [ ] Data isolation enforcement — all transcript/task/participant queries JOIN against `meeting_participants` filtered by `agent_id`; no cross-meeting reads via MCP tools or WebSocket events
  - [ ] Input sanitization — strict Pydantic schemas with max-length, allowed-character, and type constraints on all MCP tool inputs and WebSocket message payloads; reject + log invalid payloads
  - [ ] Rate limiting — Redis sliding-window counters per `{agent_id}:{window}`; applied via FastAPI `Depends()` on WebSocket connect, MCP tool routes, and REST API endpoints
  - [ ] Auth hardening — API key scope enforcement (keys scoped to `meeting_id` or `agent_id`), automatic expiry, refresh token rotation
  - [ ] API key audit log — append-only PostgreSQL table `api_key_events(key_id, event_type, actor_id, meeting_id, timestamp, metadata)`
  - [ ] Secure meeting defaults — new meetings default to private; meeting IDs use non-guessable format (`{uuid4_hex[:8]}-{random_token_6}`)
  - [ ] Content filtering — keyword/pattern blocklist on chat messages and task descriptions before storage and broadcast
  - [ ] Transcript access controls — `get_transcript` MCP tool enforces active session in requested `meeting_id`; 403 if not
  - [ ] Integration tests for all security controls (injection attempts, cross-meeting access, rate limit enforcement, scope violations)

- [x] 🔗 BLOCK: Turn Management MCP Tools
  - [x] `raise_hand` — request to speak, returns queue position
  - [x] `get_queue_status` — check speaker queue and current position
  - [x] `mark_finished_speaking` — signal done, promotes next in queue
  - [x] `cancel_hand_raise` — withdraw from speaker queue
  - [x] `get_speaking_status` — check if current session is active speaker
  - [x] Wire TurnManager into MCP server tools
  - [x] Integration tests for all 5 turn management tools

- [x] 🔗 BLOCK: Chat & Status MCP Tools
  - [x] `send_chat_message` — post a message to meeting chat
  - [x] `get_chat_messages` — read chat history with optional filters
  - [x] `get_meeting_status` — comprehensive meeting state (participants, queue, active speaker, recent chat)
  - [x] Wire ChatStore into MCP server tools
  - [ ] Integration tests for all 3 chat/status tools

- [ ] 🔗 BLOCK: Claude Code Channel Integration
  - [ ] Channel server endpoint for Claude Code session connections
  - [ ] Full participant access: turn management, chat, transcript read, task access
  - [ ] All 8 new MCP tools available through the channel connection
  - [ ] Sender gating via agent API keys (same auth path as agent-gateway)
  - [ ] Integration with agent-gateway session management
  - [ ] Package as Claude Code plugin / skill
  - [ ] Integration tests: Claude Code session joins, raises hand, sends chat

- [ ] 🔗 BLOCK: Frontend — Turn Management & Chat UI
  - [ ] Speaker queue panel (ordered list, current speaker highlighted, position indicators)
  - [ ] Hand-raise button for human participants in the meeting room
  - [ ] Meeting chat panel (send/receive messages, participant attribution, timestamps)
  - [ ] Participant list updated to show agent status (in queue, speaking, idle)
  - [ ] Real-time state updates via WebSocket events

- [ ] 🔗 BLOCK: April Release Examples & Docs
  - [ ] Update `examples/meeting-assistant-agent/` to use turn management + chat tools
  - [ ] Update OpenClaw plugin with new MCP tool definitions
  - [ ] Write Claude Code channel setup guide (`docs/integrations/CLAUDE_CODE_CHANNEL.md`)
  - [ ] Write multi-agent meeting tutorial
  - [ ] Finalize `docs/milestone-testing/M_APRIL_E2E_Test.md` scenario playbook

- [ ] **🏁 Milestone M_APRIL: All 4 E2E scenarios pass + security gate** — see `docs/milestone-testing/M_APRIL_E2E_Test.md`
  - [ ] Scenario A: 1 human + 1 agent (turn management + chat end-to-end)
  - [ ] Scenario B: 2 humans + 1 agent (multi-human, single agent)
  - [ ] Scenario C: 1 human + multiple agents (agent coordination, turn queue)
  - [ ] Scenario D: multiple humans + multiple agents (full multi-party)
  - [ ] Security gate: prompt injection attempt rejected, cross-meeting access denied, rate limits enforced

---

## Phase 3: Meeting Intelligence & Agent Integration

> Portable messaging layer, real-time meeting insights, and Claude Code channel integration.

- [ ] 🔗 BLOCK: Portable Message Bus Abstraction
  - [ ] Define MessageBus ABC (publish, subscribe, ack) in convene-core
  - [ ] Implement RedisStreamsMessageBus provider (wrap existing Redis code)
  - [ ] Register in provider registry
  - [ ] Migrate existing services to MessageBus interface
  - [ ] Integration tests for message bus abstraction

- [ ] 🔗 BLOCK: Meeting Insight Stream
  - [ ] Define Entity schema (Pydantic models: task, decision, question, entity_mention, key_point, blocker, follow_up)
  - [ ] Define Extractor ABC and register in provider registry
  - [ ] Implement built-in LLM extractor using existing LLM provider abstraction
  - [ ] Build batch collector (subscribe to transcript, buffer, trigger extraction)
  - [ ] Build entity deduplicator
  - [ ] Build insight publisher (publish to meeting.*.insights topics)
  - [ ] Configuration: batch window, confidence thresholds
  - [ ] Pipeline integration tests

- _(Claude Code Channel Integration moved to April Release Sprint — see above)_

- [ ] 🔗 BLOCK: Custom Extractors & Cloud Providers
  - [ ] Document Extractor ABC, publish SDK/example
  - [ ] Implement extractor hot-loading (runtime registration)
  - [ ] Implement SQSMessageBus (AWS SNS+SQS)
  - [ ] Implement PubSubMessageBus (GCP Cloud Pub/Sub)
  - [ ] Implement NATSMessageBus (self-hosted NATS JetStream)
  - [ ] Deployment config templates per cloud provider
  - [ ] Cross-provider integration tests

- [ ] 🔗 BLOCK: Agent Context Seeding
  - [ ] Define context document schema (Pydantic models for platform context, meeting context, meeting recap)
  - [ ] Create `convene-ai-platform.md` template — fixed platform-level context for agents
  - [ ] Implement as MCP Resources: `convene://platform/context` (static), `convene://meeting/{id}/context` (template with change notifications)
  - [ ] Build MeetingContextGenerator — populates meeting context from calendar invite, attendees, agenda
  - [ ] Build MeetingRecapGenerator — creates meeting-recap from Insight Stream snapshots for late joiners
  - [ ] Implement as MCP Tools: `get_meeting_recap` (on-demand recap fetch), `get_entity_history` (filtered entity query)
  - [ ] Integrate context seeding with Claude Code Channel (instructions + initial notifications)
  - [ ] Integrate context seeding with Gemini Live API (system_instruction field)
  - [ ] Add context refresh — recap updates every extraction batch
  - [ ] Tests for context generation and recap accuracy

- [ ] 🔗 BLOCK: Model Tiering & Cost Architecture
  - [ ] Integrate Claude Agent SDK for all LLM operations
  - [ ] Design tiered model strategy: Claude Haiku (entity extraction), Claude Sonnet (recaps, agent dialogue), Claude Opus (premium analysis)
  - [ ] Implement LLM provider selection per task type (extraction vs. summarization vs. dialogue)
  - [ ] Launch STT: Deepgram Nova-2 (diarization included, real-time streaming, $0.0043/min)
  - [ ] Enterprise STT: self-hosted faster-whisper + pyannote.audio (GPU compute, data sovereignty — Phase D only)
  - [ ] TTS provider cost modeling and selection
  - [ ] Speaker diarization integration (segment and label audio by speaker)
  - [ ] Usage metering and subscription/volume billing hooks
  - [ ] Configuration: per-meeting model overrides, default tiers per plan
  - [ ] Stripe integration: products and pricing for 4 tiers (Free, Pro $29/mo, Business $79/mo, Enterprise custom)
  - [ ] Stripe Checkout / billing portal integration in web frontend
  - [ ] Stripe webhook handler for subscription lifecycle (created, updated, cancelled, payment_failed)
  - [ ] Usage-based metering: track meeting minutes, extraction calls, agent sessions per billing period
  - [ ] Stripe usage records API integration for metered billing components
  - [ ] Subscription middleware: gate features by plan tier (entity types, diarization, custom extractors, model selection)
  - [ ] Free tier limits enforcement (5 meetings/month, basic extraction, no diarization)
  - [ ] Billing dashboard in web frontend (current plan, usage, invoices)

- [ ] 🔗 BLOCK: Subscription & Billing Infrastructure
  - [ ] Stripe SDK integration (stripe-python for API server)
  - [ ] Subscription plans configuration (products, prices, features matrix)
  - [ ] Customer and subscription management (create customer on signup, link to Convene user)
  - [ ] Checkout flow: upgrade/downgrade/cancel via Stripe billing portal
  - [ ] Webhook endpoint for Stripe events (invoice.paid, customer.subscription.updated, etc.)
  - [ ] Usage metering service: count meeting minutes, LLM calls, STT minutes per user per period
  - [ ] Plan enforcement middleware: check user's plan before allowing premium features
  - [ ] Grace period and dunning handling for failed payments
  - [ ] Admin dashboard: revenue metrics, subscriber counts, churn tracking
  - [ ] Tests for billing flows and plan enforcement

- Plan only (no implementation): Dynamic entity discovery based on conversation content

---

## Phase 4: MCP Server & Agent SDK

> Developer GTM wedge — make it trivial for any AI agent to join a Convene meeting.

- [ ] 🔗 BLOCK: MCP Server
  - [ ] Implement MCP server using Python MCP SDK
  - [ ] Implement MCP tools: list_meetings, join_meeting, leave_meeting
  - [ ] Implement MCP tools: get_transcript, get_tasks, send_message, send_audio
  - [ ] Implement MCP tools: get_participants, get_meeting_context, create_task
  - [ ] Implement MCP resources: meeting://{id}, meeting://{id}/transcript, meeting://{id}/tasks
  - [ ] Write MCP server documentation and examples

- [ ] 🔗 BLOCK: Agent SDK
  - [ ] Create Agent Python SDK (ConveneAgent class, async API, audio helpers)
  - [ ] Publish SDK to PyPI as `convene-ai`
  - [ ] Write SDK documentation and example agents (Claude Agent SDK + OpenClaw examples)

- [ ] **🏁 Milestone M4: MCP client (Claude) joins a meeting and extracts tasks via MCP tools**

---

## Phase 5: User Platform & Auth

> User-facing product — sign up, create workspaces, manage agents.

- [ ] 🔗 BLOCK: Authentication
  - [ ] Design database schema for users, workspaces, and memberships
  - [ ] Implement user registration (email + password, email verification)
  - [ ] Implement login / logout with JWT token management
  - [ ] Implement OAuth login (Google, GitHub)
  - [ ] Implement session management and token refresh

- [ ] 🔗 BLOCK: Workspaces
  - [ ] Implement workspace creation and settings
  - [ ] Implement multi-tenant data isolation
  - [ ] Implement role-based access control (owner, admin, member)
  - [ ] Implement workspace invitations (invite by email, accept/decline)

- [ ] 🔗 BLOCK: Agent Management UI
  - [ ] Implement agent registration portal
  - [ ] Implement agent credential generation UI
  - [ ] Implement agent assignment to meetings
  - [ ] Implement agent permission management

- [ ] 🔗 BLOCK: Billing
  - [ ] Integrate Stripe for payment processing
  - [ ] Implement subscription plans (Free, Developer, Pro, Team, Enterprise)
  - [ ] Implement usage tracking (agent-minutes, meeting count, storage)
  - [ ] Implement usage-based billing metering for Developer tier
  - [ ] Implement plan upgrade/downgrade flows
  - [ ] Implement billing dashboard (current plan, usage, invoices, payment method)
  - [ ] Implement free tier limit enforcement
  - [ ] Implement Stripe webhook handlers (payment success/failure, subscription changes)

- [ ] **🏁 Milestone M5: User signs up, creates workspace, subscribes to paid plan**

---

## Phase 6: Meeting Platform (WebRTC + Browser UI)

> Humans join meetings via browser — the other side of the two-sided platform.

- [ ] 🔗 BLOCK: LiveKit Integration
  - [ ] Deploy LiveKit server (Docker, local dev configuration)
  - [ ] Implement LiveKit room creation and management
  - [ ] Implement token generation for browser participants
  - [ ] Implement audio routing: LiveKit room → Audio Service STT pipeline
  - [ ] Implement audio routing: Agent Gateway audio → LiveKit room (agent speech)

- [ ] 🔗 BLOCK: Web Client
  - [ ] Scaffold React meeting web client (Vite + React + LiveKit SDK + Tailwind)
  - [ ] Implement meeting join flow (link-based, authenticated)
  - [ ] Implement video/audio controls (mute, camera, screen share, leave)
  - [ ] Implement participant list (humans + AI agents with status indicators)
  - [ ] Implement meeting lobby / waiting room

- [ ] 🔗 BLOCK: Real-Time Collaboration
  - [ ] Implement real-time collaboration sidebar (task feed, decision log, agent activity)
  - [ ] Implement collaborative task editing during meeting (mark done, reassign, notes)
  - [ ] Implement meeting context panel (previous meeting tasks, relevant history)

- [ ] Implement meeting management (create, schedule, invite, history, recordings)
- [ ] Implement meeting lifecycle management (create, admit, end, cleanup)

- [ ] **🏁 Milestone M6: Team creates a meeting, humans join via browser, agent joins via Gateway, tasks extracted in real-time**

---

## Phase 7: Memory & Intelligence

> Persistent memory is the competitive moat — agents that remember everything across meetings.

- [ ] 🔗 BLOCK: Memory System
  - [ ] Implement working memory layer (Redis hash per active meeting)
  - [ ] Implement short-term memory layer (recent meeting queries via SQL)
  - [ ] Implement long-term memory layer (pgvector embeddings of meeting summaries)
  - [ ] Implement structured state layer (task/decision indexes)

- [ ] Implement memory context builder (assembles relevant context for LLM)
- [ ] Implement cross-meeting task accumulation and conflict detection
- [ ] Implement meeting summary generation on meeting.ended event

---

## Phase 8: Cloud Deployment & STT

> Production deployment on AWS/GCP with native cloud STT providers.

- [ ] 🔗 BLOCK: Kubernetes & Helm Deployment (DGX Spark / K3s)
  - [ ] Create Helm charts for all Convene AI services
  - [ ] Kubernetes resource definitions (Deployments, Services, ConfigMaps, Secrets)
  - [ ] K3s deployment guide for DGX Spark
  - [ ] GPU-enabled pod spec for self-hosted Whisper STT
  - [ ] Horizontal pod autoscaling configuration

- [ ] 🔗 BLOCK: Cloud Infrastructure
  - [ ] Dockerize all services with multi-stage builds
  - [ ] Create Kubernetes deployment manifests (or ECS/Cloud Run)
  - [ ] Implement auto-scaling policies
  - [ ] Set up monitoring (Prometheus/Grafana) and alerting

- [ ] 🔗 BLOCK: Cloud STT Providers
  - [ ] Implement AWS Transcribe STT provider (registered in provider registry)
  - [ ] Implement GCP Speech-to-Text STT provider (registered in provider registry)

- [ ] Implement automated backups and data retention policies

---

## Phase 9: Voice Output & Dialogue

> Speaking agents — bidirectional audio for agents that talk in meetings.

- [x] Implement Cartesia TTS provider
- [x] Implement ElevenLabs TTS provider

- [ ] 🔗 BLOCK: TTS Pipeline
  - [ ] Implement bidirectional audio pipeline (meeting → STT + TTS → meeting)
  - [ ] Implement standup report generation (pre-meeting context assembly, LLM report)

- [ ] Implement speaking interaction protocol (cued speaking, silence detection, interruption handling, VAD)
- [ ] Implement multi-turn dialogue engine (conversation state machine, context window)
- [ ] Implement real-time task confirmation (speak to confirm commitments)

---

## Phase 10: Ecosystem & Integrations

> Third-party integrations and the agent marketplace.

- [ ] 🔗 BLOCK: Integrations
  - [ ] Implement Slack integration (summaries, task notifications, slash commands)
  - [ ] Implement Linear integration (bidirectional task sync)
  - [ ] Implement Jira integration (bidirectional task sync)
  - [ ] Implement GitHub integration (link tasks to PRs)
  - [ ] Implement Notion integration (push meeting summaries and task tables)
  - [ ] Implement webhook API (generic event push for custom integrations)
  - [ ] Implement Zapier / Make triggers (meeting.ended, task.created, etc.)

- [ ] Implement calendar sync (Google Calendar, Outlook)
- [ ] Implement Agent Marketplace (browse, install, rate agents)

- [ ] 🔗 BLOCK: Existing Meeting Platform Integration (adoption accelerator — post-April)
  - [ ] Design MeetingPlatformAdapter ABC (join, leave, receive_audio, send_audio, get_participants)
  - [ ] Implement ZoomAdapter via Zoom Meeting SDK (transcription bot entry point)
  - [ ] Implement GoogleMeetAdapter (via Meet bot or Google Meet API)
  - [ ] Implement TeamsAdapter via Teams Bot Framework SDK
  - [ ] Define adoption path: start as transcription bot → graduate users to native Convene meetings
  - [ ] Dashboard prompt: "Join this meeting in Convene instead" UX flow

- [ ] **🏁 Milestone M7+: Full product experience — integrations, marketplace, analytics**

---

## Phase 11: Hardening

> Security, performance, and enterprise readiness.

- [ ] Implement rate limiting on all API endpoints
- [ ] Implement comprehensive input validation
- [ ] Implement audit logging (who did what, when)
- [ ] Implement data retention policies and deletion (GDPR compliance)
- [ ] Implement SSO (SAML/OIDC) for enterprise
- [ ] Load testing and capacity planning
- [ ] Write deployment documentation (Docker, Kubernetes, cloud guides)
- [ ] **🏁 Milestone M8: Platform passes security review, ready for enterprise pilots**

---

## Notes

### Milestone Reference

- **M1:** Audio → Transcript → Redis (Phase 1C/1D) ✅
- **M2:** Redis → Task Extraction → PostgreSQL (Phase 1)
- **M3:** Agent connects via Gateway, receives audio, sends transcript events (Phase 2) ✅
- **M_APRIL:** All 4 multi-party E2E scenarios pass — turn management, chat, multi-agent, Claude Code channel (April Release Sprint)
- **M4:** MCP client joins a meeting via MCP tools (Phase 4)
- **M5:** User signs up, creates workspace, subscribes to paid plan (Phase 5)
- **M6:** Browser-based meeting with agents and humans (Phase 6)
- **M7+:** Full product experience with integrations and marketplace (Phase 10)
- **M8:** Enterprise hardening and security review (Phase 11)

### CoWork Edit Protocol

**Task selection:** CoWork picks the first unchecked (`- [ ]`), unlocked (no 🔒) item or block (`🔗 BLOCK:`) in the current phase.

**Block mode:** When the selected item is a `🔗 BLOCK:`, CoWork enters block mode:
1. Work through sub-tasks in order, running quality checks after each
2. If a sub-task fails after 3 fix attempts, document and stop (partial block is OK)
3. Check off the entire block only when all sub-tasks pass
4. If a block has >5 sub-tasks and quality checks pass on the first N, commit progress and continue

**Completion registration:**
1. Check off the item (or block + all sub-tasks): `- [ ]` → `- [x]`
2. Append an entry to `docs/PROGRESS.md` (never overwrite previous entries)
3. Update `docs/HANDOFF.md` with shift-change notes

**Branch naming:** `scheduled/YYYY-MM-DD-{slug}` (e.g., `scheduled/2026-02-27-pydantic-models`)

**Lock protocol:** Only Jonathan adds or removes 🔒. CoWork must never lock or unlock items.

**Quality gate:** All of the following must pass before checking off an item:
- `uv run ruff check .` — no lint errors
- `uv run mypy --strict .` — no type errors
- `uv run pytest -x -v` — all tests pass

If quality checks fail after 3 fix attempts, document the failure in PROGRESS.md, note it as a blocker in HANDOFF.md, and stop. Do not check off the item.
