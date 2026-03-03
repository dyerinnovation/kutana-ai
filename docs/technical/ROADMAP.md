# Convene AI — Feature Roadmap

> This document is structured for Claude Code to pick up individual features and implement them. Each feature includes context, acceptance criteria, and technical notes. The roadmap reflects Convene's pivot from a phone-dial-in meeting bot to an agent-first meeting platform with multiple meeting access methods, extensible agent architecture, and marketplace potential.

---

## Architecture Overview

```
convene-ai/
├── docs/                          # Product docs
│   ├── VISION.md                  # Product vision & business case
│   └── ROADMAP.md                 # This file
├── packages/
│   ├── convene-core/              # Domain models, events, interfaces
│   │   ├── models/                # Pydantic models for tasks, meetings, agents
│   │   ├── events/                # Event definitions (Redis Streams)
│   │   └── interfaces/            # Abstract base classes for providers
│   ├── convene-providers/         # STT, TTS, LLM provider implementations
│   │   ├── stt/                   # AssemblyAI, Deepgram, Whisper
│   │   ├── tts/                   # Cartesia, ElevenLabs
│   │   └── llm/                   # Anthropic, OpenAI, local models
│   └── convene-memory/            # Persistent memory layers
│       ├── working.py             # In-memory / Redis current meeting state
│       ├── short_term.py          # Recent meetings (PostgreSQL)
│       ├── long_term.py           # Vectorized summaries (pgvector)
│       └── structured.py          # Tasks, decisions (relational)
├── services/
│   ├── api-server/                # FastAPI REST + WebSocket API
│   ├── audio-service/             # Audio pipeline (Twilio, WebRTC, STT)
│   ├── task-engine/               # LLM-powered task extraction workers
│   ├── agent-gateway/             # Agent connection & routing (NEW)
│   ├── mcp-server/                # Model Context Protocol server (NEW)
│   └── worker/                    # Background jobs (notifications, integrations)
├── web/                           # Meeting client (React + LiveKit)
├── CLAUDE.md                      # Bootstrap prompt for Claude Code
├── pyproject.toml                 # Root workspace config (uv)
└── docker-compose.yml             # Local dev environment
```

### Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.12+ | Pipecat ecosystem, ML tooling, team familiarity |
| API Framework | FastAPI | Async-native, WebSocket support, Pydantic integration |
| Database | PostgreSQL 16 + pgvector | Single DB for relational + vector, proven at scale |
| Cache / Event Bus | Redis Streams | Lightweight pub/sub between services |
| Package Manager | uv | 10-100x faster than pip/Poetry |
| Linting | ruff | Fast, replaces flake8/isort/black |
| Type Checking | mypy (strict) | Catch bugs early with provider abstractions |
| Phone Integration | Twilio Programmable Voice | Dial-in to any meeting platform (optional/legacy) |
| WebRTC Server | LiveKit | Open-source SFU for browser conferencing |
| Meeting Client | React + LiveKit SDK | Real-time video/audio in browser |
| Agent Gateway | FastAPI WebSocket + gRPC | Agent connection endpoint |
| MCP Server | Python MCP SDK | Expose Convene as MCP server for Claude Desktop |
| STT (Primary) | AssemblyAI Universal-Streaming | $0.0025/min, built-in diarization |
| STT (Fallback) | Deepgram Nova-3 | $0.0077/min, lowest latency |
| TTS (Phase 5) | Cartesia Sonic-3 | 40-90ms TTFA, fastest available |
| LLM (Extraction) | Claude Sonnet / GPT-4.1-mini | Structured output for task extraction |
| Authentication | JWT + NextAuth.js (TBD) | OAuth + password auth |
| Billing | Stripe | Payment processing, subscriptions |
| Container | Docker Compose (dev), K8s/fly.io (prod) | Scalable deployment |

---

## Phase 1 — Foundation & Core AI (MOSTLY COMPLETE)

> Goal: Agent dials into meetings or joins via WebRTC, transcribes, extracts tasks, builds persistent memory.

### F1.1 — Project Scaffolding ✅
**Status**: Complete

**Context**: Set up the monorepo with uv workspaces, package structure, and local dev environment.

**Completed**:
- uv workspace with convene-core, convene-providers, convene-memory packages
- services/api-server, audio-service, task-engine, worker
- docker-compose.yml with PostgreSQL 16 + pgvector, Redis 7
- pyproject.toml with shared dev dependencies (ruff, mypy, pytest)
- Basic CI config (GitHub Actions)
- .env.example with documented environment variables
- Health check endpoints on all services

---

### F1.2 — Core Domain Models ✅
**Status**: Complete

**Context**: Define the data models that everything else builds on.

**Completed**:
- Meeting model (id, platform, dial_in_number, scheduled_at, participants, status)
- Participant model (id, name, email, speaker_id, role)
- Task model (id, meeting_id, description, assignee, due_date, priority, status, dependencies, source_utterance)
- Decision model (id, meeting_id, description, decided_by, participants_present)
- TranscriptSegment model (id, meeting_id, speaker_id, text, start_time, end_time, confidence)
- AgentConfig model (id, name, voice_id, system_prompt, capabilities)
- Pydantic v2 BaseModels with validators
- SQLAlchemy ORM models
- Alembic migration for initial schema

---

### F1.3 — Provider Abstraction Layer ✅
**Status**: Complete

**Context**: Abstract STT, TTS, and LLM providers behind interfaces.

**Completed**:
- STTProvider ABC with start_stream(), send_audio(), get_transcript(), close()
- TTSProvider ABC with synthesize(), get_voices()
- LLMProvider ABC with extract_tasks(), summarize(), generate_report()
- AssemblyAISTT implementation with streaming and diarization
- DeepgramSTT implementation
- AnthropicLLM implementation
- Provider registry pattern
- Automatic fallback logic

---

### F1.4 — Twilio Phone Integration ✅
**Status**: Complete (now optional/legacy)

**Context**: Original meeting access method. Still supported for dial-in scenarios but no longer primary.

**Completed**:
- Outbound Twilio calls to meeting dial-in numbers
- DTMF tone generation for meeting IDs/PINs
- Bidirectional audio streaming via Media Streams
- Audio format handling (μ-law 8kHz conversion)
- Call lifecycle management
- Concurrent meeting support
- Webhook endpoints for call status
- Meeting scheduling from URLs

**Note**: This remains functional for teams preferring phone dial-in, but new features prioritize WebRTC and agent gateway.

---

### F1.5 — Real-Time Transcription Pipeline 🟡
**Status**: Partially Complete

**Context**: Stream phone/WebRTC audio to STT provider, produce speaker-diarized transcript.

**Completed**:
- Audio pipeline (Twilio → STT)
- Real-time transcript segments via Redis Streams
- Speaker diarization
- Transcript storage in PostgreSQL
- Audio quality handling
- Lifecycle events (meeting.started, meeting.ended)
- Buffering and segment aggregation

**In Progress / TODO**:
- WebRTC audio pipeline (audio-service should accept WebRTC frames from LiveKit)
- Unified audio handling (Twilio + WebRTC through same STT infrastructure)

---

### F1.6 — Task Extraction Engine 🟡
**Status**: In Progress

**Context**: LLM-powered worker that extracts structured tasks from transcript.

**Acceptance Criteria**:
- [ ] Worker subscribes to `transcript.segment.final` events
- [ ] Batch processing: accumulate 3-5 minutes, then extract
- [ ] LLM prompt identifying action items, commitments, deadlines, owners, decisions
- [ ] Structured output as Pydantic Task and Decision models
- [ ] Deduplication logic
- [ ] Confidence scoring
- [ ] Post-meeting summary extraction
- [ ] Emit task.created, task.updated, decision.recorded events

**Technical Notes**:
- Sliding window with overlap (0-5 min, then 3-8, then 6-11, etc.)
- Two-stage extraction: classifier (identify commitments) + extractor (structured data)
- Include team context from memory system
- Use Claude with tool_use for structured extraction
- Cost optimization: Haiku for classification, Sonnet for extraction

---

### F1.7 — Memory System 🟡
**Status**: Scaffolded

**Context**: Four-layer memory that gives agents context across meetings.

**Acceptance Criteria**:
- [ ] **Working memory** (Redis): current meeting transcript, participants, task candidates
- [ ] **Short-term memory** (PostgreSQL): last 10 meetings per team, recent task statuses
- [ ] **Long-term memory** (pgvector): vectorized summaries, semantic search
- [ ] **Structured state** (PostgreSQL): tasks, decisions, participant history
- [ ] Memory context builder: assemble relevant context before meeting
- [ ] Automatic memory consolidation: working → short/long term after meeting
- [ ] Team detection: group meetings by recurring events or participant overlap

**Technical Notes**:
- pgvector with HNSW index for vector search
- Embedding model: text-embedding-3-small (OpenAI) or voyage-3-lite
- Meeting context window: open tasks, last summary, participant names
- Working memory TTL: 24 hours
- Short-term window: 30 days or last 10 meetings

---

### F1.8 — API Server (Backend Only)
**Status**: In Progress

**Context**: REST API for managing meetings, tasks, and agent configuration. Dashboard is separate (Phase 3).

**Acceptance Criteria**:
- [x] `POST /meetings` — schedule a meeting
- [x] `GET /meetings` — list meetings with pagination/filters
- [x] `GET /meetings/{id}` — meeting detail with transcript, tasks, decisions
- [x] `GET /meetings/{id}/transcript` — full transcript with speakers
- [x] `GET /tasks` — list all tasks with filters
- [x] `PATCH /tasks/{id}` — update task
- [x] `GET /agents` — list configured agents
- [x] `POST /agents` — create/configure agent
- [ ] WebSocket endpoint for real-time transcript streaming
- [ ] Authentication (API key for MVP, OAuth later)

**Note**: Web dashboard moved to Phase 3 (F3.2). Phase 1 focuses on API.

---

## Phase 2 — Agent Gateway & MCP (NEW — THE CORE DIFFERENTIATOR)

> Goal: Build the agent-first architecture. Allow any AI agent to join meetings and access Convene's capabilities. Make agents composable and discoverable.

### F2.1 — Agent Gateway Service
**Status**: Pending

**Context**: The dedicated service that AI agents connect to. Replaces direct Twilio/audio integration for agents.

**Acceptance Criteria**:
- [ ] FastAPI service with WebSocket endpoint `ws://gateway/v1/connect`
- [ ] Agent authentication via API keys
- [ ] Capability negotiation on connect (listen, speak, push-ui, access-transcript)
- [ ] Audio stream routing: receive PCM/Opus from agents → STT pipeline
- [ ] Audio stream routing: receive mixed meeting audio → forward to agents
- [ ] Structured data channel for metadata, context, real-time updates
- [ ] Agent presence management (join, leave, heartbeat, timeout)
- [ ] Multi-agent per meeting support
- [ ] Rate limiting and connection management
- [ ] Health check and metrics endpoints

**Technical Notes**:
- JSON for control messages, binary for audio frames
- Protocol: establish WebSocket, negotiate capabilities, stream audio + metadata
- Agent heartbeat: expect ping every 30 seconds
- Meeting join: agent sends `{type: "join_meeting", meeting_id: "...", capabilities: ["listen", "speak"]}`
- Audio frame format: `{type: "audio", meeting_id: "...", timestamp: ..., frames: [...]}` with PCM16 @ 16kHz
- Implement gRPC as alternative for lower latency (stretch goal)
- Store agent connections in Redis with TTL

---

### F2.2 — MCP Server for Meeting Access
**Status**: Pending

**Context**: Expose Convene as an MCP server so any MCP-compatible AI assistant (Claude, custom clients) can join meetings.

**Acceptance Criteria**:
- [ ] MCP server implementation using Python MCP SDK
- [ ] Tools exposed:
  - `list_meetings` — upcoming/active meetings the agent has access to
  - `join_meeting` — connect to active meeting, receive audio/transcript
  - `leave_meeting` — disconnect
  - `get_transcript` — current or historical meeting transcript
  - `get_tasks` — tasks from current/past meetings
  - `send_message` — text message to meeting sidebar
  - `send_audio` — TTS audio to meeting
  - `get_participants` — list humans + agents
  - `get_meeting_context` — agenda, history, open tasks
  - `create_task` — manually create task for meeting
- [ ] Resources exposed:
  - `meeting://{id}` — meeting details
  - `meeting://{id}/transcript` — live transcript stream
  - `meeting://{id}/tasks` — meeting tasks
- [ ] Authentication via API key (MCP server config)
- [ ] Documentation with examples for Claude Desktop, Claude Code, custom clients

**Technical Notes**:
- MCP server internally connects to Agent Gateway as an agent
- Keeps architecture clean: MCP is a protocol adapter, Gateway is the engine
- Server runs as a separate service or embedded in api-server
- Use official `mcp` Python package (Anthropic maintained)
- Expose at `stdio://` for Claude Desktop, `http://localhost:3000` for local dev

---

### F2.3 — Agent Python SDK
**Status**: Pending

**Context**: Package the agent connection protocol into a pip-installable SDK.

**Acceptance Criteria**:
- [ ] Published to PyPI as `convene-ai`
- [ ] Async-first API (asyncio)
- [ ] `ConveneAgent` class with:
  - `connect(meeting_url, api_key)` — establish gateway connection
  - `join_meeting(meeting_id)` — join active meeting
  - `on_transcript(callback)` — listen for transcript segments
  - `send_audio(audio_frames)` — send audio to meeting
  - `push_update(data)` — send JSON data to sidebar
  - `leave_meeting()` — disconnect
- [ ] Audio stream helpers (PCM encoding/decoding, resampling)
- [ ] Event-driven architecture (callbacks for transcript, tasks, participants)
- [ ] Type hints throughout, Pydantic models for data
- [ ] Comprehensive documentation and examples
- [ ] Example agents: basic listener, task tracker, speaking agent

**Technical Notes**:
- Support Python 3.9+
- Use asyncio + websockets for connection management
- Provide audio utilities for common formats (WAV, MP3, WebM)
- Publish to PyPI with automatic builds on tag
- Include example agents in `/examples/` subdirectory

---

### F2.4 — Agent Authentication & Registration
**Status**: Pending

**Context**: Manage agent identities, capabilities, and API keys.

**Acceptance Criteria**:
- [ ] Agent registration API (name, capabilities, description, owner, webhook_url)
- [ ] API key generation and management
- [ ] OAuth2 alternative for production agents
- [ ] Agent capability declaration and enforcement
- [ ] Per-agent rate limiting and usage tracking
- [ ] Agent directory (list agents, their capabilities, owner)
- [ ] Deactivate/revoke agent keys

**Acceptance Criteria Detail**:
- [ ] `POST /agents/register` — register new agent
- [ ] `GET /agents` — list registered agents
- [ ] `GET /agents/{agent_id}` — agent details
- [ ] `POST /agents/{agent_id}/keys` — generate API key
- [ ] `DELETE /agents/{agent_id}/keys/{key_id}` — revoke key
- [ ] `PATCH /agents/{agent_id}` — update agent metadata
- [ ] Rate limit: 100 concurrent connections per agent by default

**Technical Notes**:
- Store agent metadata in PostgreSQL
- API keys in secure hash (bcrypt)
- Capability names: "listen", "speak", "access_transcript", "modify_tasks", "send_messages"
- Enforce capabilities at gateway connection time

---

## Phase 3 — Meeting Platform (WebRTC + Browser UI)

> Goal: Build the web-based meeting platform. Browser participants join via WebRTC, see live collaboration surfaces, receive real-time task updates.

### F3.1 — LiveKit Integration
**Status**: Pending

**Context**: Self-hosted WebRTC SFU for browser conferencing.

**Acceptance Criteria**:
- [ ] LiveKit server deployment (Docker / self-hosted)
- [ ] Room creation and management via LiveKit API
- [ ] Token generation for browser participants
- [ ] Audio routing: LiveKit room → Audio Service → STT pipeline
- [ ] Audio routing: Agent Gateway audio → LiveKit room (agent speech)
- [ ] Meeting lifecycle: create room, admit participants, end meeting, cleanup
- [ ] Recording support via LiveKit Egress API
- [ ] Participant list with status (human, agent, muted, etc.)

**Technical Notes**:
- Deploy LiveKit as Docker container or K8s pod
- API keys for secure access: generate tokens with meeting_id, participant_id, capabilities
- Audio composition: mix all participant audio into single stream for STT
- Agent audio injection: LiveKit SFU forwards agent audio back to room

---

### F3.2 — Meeting Web Client
**Status**: Pending

**Context**: React app for browser-based meeting participation.

**Acceptance Criteria**:
- [ ] React app using LiveKit React SDK
- [ ] Video/audio conferencing with controls (mute, camera, screen share)
- [ ] Meeting join flow (link-based, authenticated)
- [ ] Participant list showing humans and agents with status
- [ ] Meeting lobby / waiting room
- [ ] Responsive design (desktop + tablet)
- [ ] Meeting invite link generation
- [ ] Fullscreen mode for video
- [ ] Network quality indicator
- [ ] Meeting timer

**Technical Notes**:
- Use LiveKit React SDK (`@livekit/react`)
- Host in `/web/` directory, build with Vite
- Integrate with F4.1 auth system (JWT tokens)
- Share component state via Context API
- Use WebSocket to api-server for real-time updates (transcripts, tasks)

---

### F3.3 — Real-Time Collaboration Sidebar
**Status**: Pending

**Context**: Agent-generated content visible during meetings.

**Acceptance Criteria**:
- [ ] Sidebar visible to all participants (desktop view)
- [ ] Live task extraction feed (tasks appear in real-time)
- [ ] Live decision log
- [ ] Agent activity feed (what each agent is doing)
- [ ] Collaborative task editing (mark done, reassign, add notes)
- [ ] Meeting context panel (previous open items, relevant history)
- [ ] Participant presence indicators
- [ ] Sidebar width toggleable
- [ ] Expandable task cards with details

**Technical Notes**:
- Use WebSocket from web client to api-server for real-time updates
- Emit task.created, decision.recorded events from task-engine
- Publish events to Redis pub/sub, api-server subscribes and pushes to WebSocket clients
- Component: TaskFeed, DecisionLog, AgentActivityFeed, MeetingContext
- Styling: Tailwind CSS, consistent with Slack/Notion design

---

### F3.4 — Meeting Management
**Status**: Pending

**Context**: Create, schedule, invite, and review meetings.

**Acceptance Criteria**:
- [ ] Meeting creation (title, time, participants, recurrence)
- [ ] Meeting invitation system (email invites with join links)
- [ ] Recording controls and consent management
- [ ] Meeting history view (past meetings, transcripts, tasks)
- [ ] Meeting detail view (transcript replay, task timeline)
- [ ] Calendar sync (Google Calendar, Outlook push)
- [ ] Recurring meeting support
- [ ] Meeting status (scheduled, in_progress, ended)

**Technical Notes**:
- API endpoints in F1.8, UI in dashboard (F4.3)
- Email invites via background worker
- Recording consent: checkbox on join, logged in audit trail
- Calendar sync: background job polling every 5 minutes or webhook
- Transcript replay: scrubber seeking through transcript segments

---

## Phase 4 — User Platform (Auth, Billing, Dashboard)

> Goal: Multi-tenant platform with user accounts, workspaces, subscriptions, and full dashboard UI.

### F4.1 — User Authentication & Workspaces
**Status**: Pending

**Context**: Enable multi-user and multi-team scenarios.

**Acceptance Criteria**:
- [ ] User registration (email + password)
- [ ] Email verification
- [ ] OAuth login (Google, GitHub)
- [ ] JWT token management (short-lived access + refresh tokens)
- [ ] Workspace creation (one team/org per workspace)
- [ ] Workspace invitations (email)
- [ ] Role-based access (owner, admin, member)
- [ ] User profile management
- [ ] API key generation for developer access
- [ ] Session management (logout, revoke tokens)

**Technical Notes**:
- Use bcrypt for password hashing
- JWT stored in secure HTTP-only cookies
- OAuth via NextAuth.js or similar
- Workspace isolation: all queries filtered by workspace_id
- Store workspace_id in JWT claims for authorization
- Rate limit signup: 5 per IP per hour

---

### F4.2 — Billing & Subscriptions (Stripe)
**Status**: Pending

**Context**: Monetize via subscription plans.

**Acceptance Criteria**:
- [ ] Stripe integration for payment processing
- [ ] Subscription plans: Free, Developer, Pro, Team, Enterprise
- [ ] Usage tracking (agent-minutes, meetings, storage)
- [ ] Usage-based billing for Developer tier
- [ ] Plan upgrade/downgrade
- [ ] Billing dashboard (plan, usage, invoices, payment method)
- [ ] Free tier limit enforcement
- [ ] 14-day trial for Team tier
- [ ] Stripe webhook handlers

**Plan Details**:

| Plan | Price | Agent-Minutes/mo | Meetings | Users |
|------|-------|------------------|----------|-------|
| Free | $0 | 100 | 5 | 1 |
| Developer | $0.05–0.10/agent-min | Usage-based | 50 | 5 |
| Pro | $29/seat/month | 1,000 | Unlimited | 10 |
| Team | $49/seat/month | 5,000 | Unlimited | 100 |
| Enterprise | Custom | Custom | Custom | Custom |

**Technical Notes**:
- Stripe Products and Prices created in Dashboard
- Webhook: `payment_intent.succeeded`, `customer.subscription.updated`, `customer.subscription.deleted`
- Rate limiting: check plan on every gateway connection, deny if over quota
- Usage metering: track agent-minutes via Redis, report to Stripe
- Overage handling: Team tier gets 5% overage grace, then throttles

---

### F4.3 — Workspace Dashboard
**Status**: Pending

**Context**: Central UI for managing meetings, tasks, team, and settings.

**Acceptance Criteria**:
- [ ] Dashboard home (upcoming meetings, recent activity, task overview)
- [ ] Task board (kanban: pending, in progress, done, blocked)
- [ ] Task detail view (source meeting, assignee, timeline)
- [ ] Team member view (commitments, completion rate)
- [ ] Meeting analytics (frequency, duration, extraction rate)
- [ ] Notification center (task assignments, overdue items)
- [ ] Search (meetings, transcripts, tasks, decisions)
- [ ] Data export (CSV, JSON)
- [ ] Settings (workspace, team, billing, integrations)
- [ ] Meeting history with filtering

**Technical Notes**:
- React SPA using Vite
- React Router for navigation
- State management: Zustand or React Context
- Components: DashboardHome, TaskBoard, MeetingList, TeamView, SettingsPanel
- Charts: use Recharts or Chart.js for analytics
- Export: server-side generation via worker service

---

## Phase 5 — Voice Output & Dialogue

> Goal: Agent can speak during meetings, confirm tasks in real-time, and maintain conversation.

### F5.1 — TTS Integration
**Context**: Add text-to-speech so the agent can speak back through the meeting.

**Acceptance Criteria**:
- [ ] `CartesiaTTS` provider implementation (primary)
- [ ] `ElevenLabsTTS` provider implementation (fallback)
- [ ] Audio format conversion: TTS output → PCM 16kHz (for WebRTC/Twilio)
- [ ] Streaming TTS: begin playback before full response generated
- [ ] Configurable voice selection per agent
- [ ] Volume normalization to match other participants
- [ ] Voice caching for common phrases

**Technical Notes**:
- Cartesia outputs PCM — no additional conversion needed
- ElevenLabs supports streaming via chunked API
- Pre-generate common phrases for instant playback
- Audio mixing: blend agent audio with meeting audio
- Implement audio ducking: lower meeting volume slightly when agent speaks

---

### F5.2 — Standup Report Generation
**Context**: Before a standup, agent prepares a spoken progress report based on task memory.

**Acceptance Criteria**:
- [ ] Detect standup/recurring meetings from calendar metadata
- [ ] Pre-meeting context assembly: open tasks, completed, blocked items
- [ ] LLM-generated natural-language report (conversational, not robotic)
- [ ] Report structure: completed → in-progress → blocked → new items
- [ ] Configurable verbosity: brief (30s), standard (1-2m), detailed (3+m)
- [ ] Report preview in dashboard for editing
- [ ] Timing: wait for natural pause or explicit cue before speaking

**Technical Notes**:
- LLM prompt producing conversational speech, not bullet points
- Include confidence scores — don't report uncertain items
- Example: "Since Tuesday, we wrapped up three items: API migration, docs update, staging deploy. Two still open — proposal draft hasn't started, credentials issue is blocking data pipeline."
- Pre-generate report 5 minutes before meeting, cache in Redis

---

### F5.3 — Speaking Interaction Protocol
**Context**: Define when and how the agent speaks. Critical UX — poor timing ruins trust.

**Acceptance Criteria**:
- [ ] Scheduled speaking (designated times: start of standup, end of meeting)
- [ ] Cued speaking (when directly addressed)
- [ ] Wake word detection ("Convene" or "Hey Convene" in transcript)
- [ ] Silence detection (only speak during pauses >2 seconds)
- [ ] Interruption handling (stop if someone starts talking)
- [ ] Speaking indicator ("This is Convene" before first utterance)
- [ ] Brevity mode (all unprompted speech <30 seconds)
- [ ] Mute option ("Convene, mute" or "Convene, be quiet")

**Technical Notes**:
- VAD (Voice Activity Detection) on inbound stream
- Use Silero VAD — runs locally, ~10ms latency
- Configurable per team: some want active participation, others minimal
- Log all speaking decisions for analytics and tuning

---

### F5.4 — Real-Time Task Confirmation
**Context**: When agent detects a commitment, optionally speak to confirm it.

**Acceptance Criteria**:
- [ ] Real-time confidence scoring on detected commitments
- [ ] Optional speaking confirmation ("Sarah, you're taking API docs by Friday?")
- [ ] Handle corrections ("No, that's John's item")
- [ ] Confirmation mode settings (always, ambiguous only, never)
- [ ] Visual confirmation via Slack thread
- [ ] Task creation on confirmation

**Technical Notes**:
- Real-time extraction needs speed — use Haiku
- Keep confirmations <10 seconds
- Queue confirmations — don't interrupt active speaker
- Batch if 3+ tasks identified in quick succession

---

### F5.5 — Multi-Turn Dialogue Engine
**Context**: Move from single utterances to sustained conversation with context.

**Acceptance Criteria**:
- [ ] Conversation state machine (idle → listening → thinking → speaking → listening)
- [ ] Context window (last 5 minutes of transcript + full task state)
- [ ] Multi-turn follow-ups ("What about the other items?")
- [ ] Graceful exit (detect when conversation moved on, return to listening)
- [ ] Parallel processing (continue transcribing while formulating response)

**Technical Notes**:
- Use Pipecat pipeline for voice interaction loop
- Turn detection: VAD + semantic end-of-turn detection
- Latency budget: <1.5 seconds (end of user speech to start of agent speech)
- System prompt defining agent personality and meeting role

---

### F5.6 — Conflict & Dependency Detection
**Context**: Agent proactively identifies conflicts between commitments.

**Acceptance Criteria**:
- [ ] Scheduling conflicts ("Sarah has API review AND client demo Thursday")
- [ ] Dependency chains ("Deploy blocked until migration done (John owns)")
- [ ] Overcommitment detection ("Marcus has 7 items due this week")
- [ ] Optional proactive alerting in planning meetings
- [ ] Dependency graph visualization in dashboard

**Technical Notes**:
- Run analysis in post-meeting batch job
- Query task graph for cycles and critical paths
- Alert threshold: >5 items due in same week for one person

---

### F5.7 — Meeting Facilitation
**Context**: Agent actively facilitates structured meetings (standups, retros, planning).

**Acceptance Criteria**:
- [ ] Standup facilitation (prompt each participant for update)
- [ ] Time boxing ("We're at 12 minutes — wrap up?")
- [ ] Agenda tracking ("Covered 1-2, moving to 3")
- [ ] Parking lot ("Off-topic — add to parking lot?")
- [ ] Retro facilitation (went-well, didn't-go-well, actions)

---

## Phase 6 — Ecosystem & Integrations

> Goal: Expand Convene's capabilities through integrations and a marketplace for agents.

### F6.1 — Agent Marketplace
**Context**: Discover, install, and configure pre-built agent personas.

**Acceptance Criteria**:
- [ ] Agent marketplace UI (browse, search, install)
- [ ] Agent publishing workflow for developers
- [ ] Agent reviews and ratings
- [ ] Pre-built agent personas:
  - Standup Agent (conducts standups, reports progress)
  - Decision Tracker (logs decisions, flags conflicts)
  - Client Meeting Agent (professional tone, meeting summary)
  - Action Item Bot (focuses purely on task extraction)
- [ ] Agent configuration per workspace
- [ ] One-click installation

**Technical Notes**:
- Agents are published as YAML manifests + Python SDK usage examples
- Marketplace data in PostgreSQL (agent_marketplace table)
- Installation: store agent config in workspace
- Agents run as separate services or as LLM instructions (TBD)

---

### F6.2 — Integrations
**Context**: Deep integrations with project management and developer tools.

**Acceptance Criteria**:
- [ ] Linear: create/update issues from extracted tasks, bidirectional sync
- [ ] Jira: same as Linear
- [ ] GitHub: link tasks to PRs, detect "closes #123" in discussions
- [ ] Notion: push meeting summaries and task tables
- [ ] Asana: task sync
- [ ] Zapier/Make: generic webhook integrations
- [ ] Webhooks API: custom integrations

**Technical Notes**:
- Each integration as separate module in services/worker/
- Bidirectional sync: Convene → tool and tool → Convene
- Task mapping: Convene task_id linked to external issue_id
- Webhook: `task.created`, `task.updated`, `task.completed` events
- OAuth for SaaS integrations, API key for self-hosted

---

### F6.3 — Analytics & Insights
**Context**: Meta-analysis across meetings to surface team patterns.

**Acceptance Criteria**:
- [ ] Meeting effectiveness score (tasks completed vs. created ratio)
- [ ] Commitment reliability (per-person completion rate)
- [ ] Meeting frequency optimization ("This could be async")
- [ ] Time analysis (status updates vs. decisions vs. discussion)
- [ ] Team dashboard with trends over time
- [ ] Individual dashboards (my commitments, completion rate)

**Technical Notes**:
- Run analysis in daily batch job
- Store metrics in PostgreSQL `metrics` table
- Visualize with Recharts or similar
- Benchmark against industry norms (if available)

---

### F6.4 — Calendar Integration
**Context**: Automatically detect meetings from calendar and schedule agent dial-ins.

**Acceptance Criteria**:
- [ ] Google Calendar OAuth integration
- [ ] Extract dial-in info from calendar event body
- [ ] Auto-schedule agent to join meeting
- [ ] Support recurring meetings
- [ ] Manual override per meeting
- [ ] `GET /calendar/upcoming` endpoint
- [ ] 5-minute polling or webhook push

**Technical Notes**:
- Google Calendar API v3 with OAuth2
- Parse URLs from event descriptions (regex for zoom.us, meet.google.com, teams.microsoft.com)
- Store calendar events with dial_in_extracted status
- Zoom URLs: meeting ID in path, dial-in numbers in body
- Teams: conference ID in meeting body

---

### F6.5 — Slack Integration
**Context**: Push updates to Slack. This is where most teams interact with Convene.

**Acceptance Criteria**:
- [ ] Slack bot posts meeting summaries to configured channel
- [ ] Task notifications (new, overdue, status change)
- [ ] `/convene tasks` — show open tasks
- [ ] `/convene meetings` — show upcoming meetings
- [ ] Thread-based updates (one Slack thread per meeting)
- [ ] Interactive buttons (mark done, snooze, reassign)
- [ ] DM notifications for assigned tasks

**Technical Notes**:
- Use Slack Bolt (Python SDK)
- App manifest for easy installation
- Store Slack team_id and channel mappings in PostgreSQL
- Rate limiting: batch messages, respect Slack API limits
- Message format: rich blocks with buttons

---

## Phase 7 — Platform Hardening

> Goal: Security, compliance, and operational maturity.

### F7.1 — Security & Compliance
**Context**: Production-grade security and regulatory compliance.

**Acceptance Criteria**:
- [ ] Rate limiting (API, WebSocket, agent gateway)
- [ ] Input sanitization and validation
- [ ] Error handling (no leaks of stack traces, etc.)
- [ ] Audit logging (who did what, when, from where)
- [ ] GDPR compliance (data retention, deletion, export)
- [ ] Recording consent management
- [ ] SSO (SAML/OIDC) for enterprise
- [ ] Admin panel for workspace owners
- [ ] Encryption at rest for sensitive data

**Technical Notes**:
- Rate limiting: use Redis-backed sliding window
- Audit log to PostgreSQL with JSON changes
- Data retention: 90 days default, configurable
- Recording consent: checkbox on join, stored in database
- Admin panel: UI for user management, feature flags, audit logs

---

### F7.2 — Infrastructure & Operations
**Context**: Deployment, monitoring, and reliability.

**Acceptance Criteria**:
- [ ] Monitoring and alerting (Prometheus + Grafana or DataDog)
- [ ] Automated backups and DR (PostgreSQL, Redis)
- [ ] Deployment docs (Docker, K8s, cloud guides)
- [ ] Load testing and capacity planning
- [ ] Graceful degradation (if STT fails, buffer audio for retry)
- [ ] Health checks on all services
- [ ] Automated scaling policies (K8s HPA)

**Technical Notes**:
- Export metrics: service latency, error rates, queue depths
- Alerts: high error rate (>1%), high latency (>1s p95), queue backlog
- Backup strategy: PostgreSQL daily snapshots, 30-day retention
- K8s manifests for production deployment
- Document runbook for common issues

---

## Implementation Priority

For a solo founder or small team building with Claude Code, the recommended implementation order is:

1. **F1.6** — Complete task extraction (in progress)
2. **F1.7** — Memory system (scaffolded)
3. **F2.1** — Agent Gateway (core differentiator)
4. **F2.2** — MCP Server
5. **F2.3** — Agent SDK
6. **F2.4** — Agent Auth
7. **F4.1** — User Auth & Workspaces
8. **F3.1** — LiveKit Integration
9. **F3.2** — Meeting Web Client
10. **F3.3** — Real-Time Collaboration Sidebar
11. **F3.4** — Meeting Management
12. **F4.2** — Billing & Subscriptions
13. **F4.3** — Workspace Dashboard
14. **F5.1** — TTS Integration
15. **F5.2** — Standup Report Generation
16. **F5.3** — Speaking Interaction Protocol
17. **F5.4** — Real-Time Task Confirmation
18. **F5.5** — Multi-Turn Dialogue Engine
19. **F5.6** — Conflict & Dependency Detection
20. **F5.7** — Meeting Facilitation
21. **F6.1** — Agent Marketplace
22. **F6.2** — Integrations (Linear, Jira, GitHub, Notion, Asana)
23. **F6.3** — Analytics & Insights
24. **F6.4** — Calendar Integration
25. **F6.5** — Slack Integration
26. **F7.1** — Security & Compliance
27. **F7.2** — Infrastructure & Operations

**Phase 1 MVP (Core AI + Foundation)**: Items 1-2, ~2-3 weeks

**Phase 2 MVP (Agent-First Platform)**: Items 3-6, ~3-4 weeks

**Phase 3 MVP (Meeting Platform)**: Items 7-11, ~4-5 weeks

**Phase 4 MVP (User Platform)**: Items 12-13, ~2-3 weeks

---

## Key Milestones

- **Week 2**: Task extraction and memory system working end-to-end
- **Week 5**: Agent Gateway running, first external agent connected
- **Week 8**: Web client in browser, WebRTC meetings working
- **Week 10**: Multi-user auth and workspace isolation
- **Week 12**: Basic billing and subscription management
- **Week 14**: TTS and agent speech in meetings
- **Week 20**: Agent marketplace and ecosystem integrations

---

## Architecture Decisions

### Why Agent Gateway instead of direct service integration?

The Agent Gateway is the key architectural innovation. Instead of each agent needing to know about Twilio, LiveKit, STT pipelines, etc., agents connect to a single well-defined gateway. This decouples agent logic from infrastructure details and makes it trivial to:
- Add new meeting modalities (future: web, desktop app, AR)
- Scale agents independently from media
- Test agents locally
- Run agents in different languages/frameworks

### Why MCP?

MCP exposes Convene's capabilities to Claude and other AI systems that already understand the protocol. This is instant integration with Claude Desktop, Claude Code, and any future MCP client. It's a force multiplier for adoption.

### Why separate Agent SDK vs. MCP?

- **SDK**: For agents you're building yourself, or embedding in your app. Full control, lower latency.
- **MCP**: For leveraging Claude directly as an agent, no code required. Immediate value.

Both point to the same Agent Gateway internally.

### Why LiveKit?

Open-source, self-hostable, and designed for this exact use case (multi-participant, scalable). Gives us full control without vendor lock-in.

### Why three auth layers (F1.8 API key, F4.1 user JWT, F2.4 agent API key)?

- **API Key (F1.8)**: for testing and machine-to-machine integrations before user accounts exist
- **User JWT (F4.1)**: human users with workspaces and roles
- **Agent API Key (F2.4)**: agents authenticating at the gateway, independent of user

Each solves a different trust boundary.
