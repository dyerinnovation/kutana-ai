# Plan: Pivot Convene AI to Agent-First Meeting Platform

**Date:** 2026-03-01
**Status:** Planning

## Context

Convene AI is currently built as a "phone-dial-in meeting bot" — an AI agent that dials into meetings via Twilio, transcribes, and extracts tasks. The pivot transforms it into an **agent-first meeting platform** where AI agents are first-class participants connecting via native APIs, and humans join via browser WebRTC.

**Why pivot:** Today's meeting platforms (Zoom, Teams, Meet) were built for humans. Getting AI agents into meetings requires hacks — Twilio dial-in, headless browser bots, or third-party APIs. As AI agents proliferate, Convene can become the meeting infrastructure layer where agents connect natively.

**What's built (Phases 1A-1C complete, 149 tests passing):**
- Domain models, events, provider abstractions (9 providers), Twilio audio pipeline, Redis Streams event publishing, StreamConsumer, memory system scaffold

---

## 1. Impact Assessment

### Packages

| Package | Verdict | Details |
|---------|---------|---------|
| **convene-core** | EXTEND | Add `Room`, `AgentSession` models. Make `Meeting.dial_in_number/meeting_code` optional. Add 6 new events. Add ORM models. |
| **convene-providers** | NO CHANGE | All 9 providers work as-is. STT receives PCM16 bytes regardless of transport. |
| **convene-memory** | NO CHANGE | All 4 layers operate on domain models, not transport protocols. |

### Services

| Service | Verdict | Details |
|---------|---------|---------|
| **audio-service** | MAJOR REFACTOR | Extract mulaw transcoding to codec module. Add `process_pcm16()` for direct PCM input. Twilio handler kept but deprecated. |
| **api-server** | EXTEND | Add room CRUD, token generation, participant management, LiveKit client wrapper. Existing routes stay. |
| **task-engine** | NO CHANGE | Consumes Redis Streams events regardless of audio source. |
| **worker** | MINOR EXTEND | Add handlers for new event types (AgentJoined, RoomCreated, etc.). |

### New Components

| Component | Type | Description |
|-----------|------|-------------|
| **agent-gateway** | Service (`services/agent-gateway/`) | WebSocket gateway for AI agent connections. Auth, bidirectional audio/data, LiveKit bridge. |
| **meeting-client** | React app (`clients/meeting-client/`) | Browser meeting UI with WebRTC via LiveKit. |
| **convene-sdk** | Package (`packages/convene-sdk/`) | Python SDK for building agents that connect to Convene meetings. |

### Deprecated (soft)

| Component | Status |
|-----------|--------|
| `twilio_handler.py` | Kept but deprecated. Twilio becomes optional legacy path. |
| `meeting_dialer.py` | Kept but deprecated. |
| Telephony Roadmap | Deprioritized. |

---

## 2. WebRTC Server: LiveKit

**Recommendation: LiveKit** over Janus/mediasoup.

**Key reasons:**
1. **Python-first agent framework** — `livekit-agents` is purpose-built for AI agents joining rooms as participants
2. **Token-based auth with granular grants** — maps directly to capability negotiation
3. **Room management API** — clean async Python client (`LiveKitAPI`)
4. **Per-track audio egress** — route individual participant audio to STT pipeline
5. **Built-in data channels** — structured messaging alongside audio
6. **Self-hostable** — single Go binary, Docker image, Helm chart; also has managed cloud option

---

## 3. Agent Gateway Architecture

**Purpose:** Entry point for AI agents that don't use LiveKit SDK directly. Provides simple WebSocket protocol accessible from any framework.

**Why separate from LiveKit:** Not all agent frameworks can run WebRTC. A WebSocket protocol is universally accessible. The gateway bridges between simple agent protocol and LiveKit rooms.

```
services/agent-gateway/
  src/agent_gateway/
    main.py                    # FastAPI + WebSocket endpoint /agent/connect
    settings.py                # AgentGatewaySettings (redis_url, jwt_secret, livekit_*)
    protocol.py                # Pydantic message schemas
    auth.py                    # JWT validation, API key management
    connection_manager.py      # Registry of active agent sessions
    agent_session.py           # Per-agent lifecycle (audio routing, event forwarding)
    livekit_bridge.py          # Bridges agent into LiveKit room as participant
    event_relay.py             # Redis Streams -> agent WebSocket forwarding
    audio_adapter.py           # Receives PCM from agents, forwards to AudioPipeline
```

---

## 4. Agent API Contract

### Authentication
- **API Key Auth:** Agent developer gets `api_key` + `api_secret`, creates JWT, passes as query param on WebSocket connect
- **Room Token Auth (LiveKit-native):** Agent requests token from `POST /api/v1/rooms/{name}/tokens`, connects directly to LiveKit

### WebSocket Protocol (`ws://gateway:8003/agent/connect?token=<jwt>`)

**Agent -> Server:**
- `join_meeting` — meeting_id + capabilities list
- `audio_data` — base64 PCM16 16kHz mono
- `data` — structured data (channel + payload)
- `leave_meeting` — disconnect

**Server -> Agent:**
- `joined` — confirmation with room_name, participants, granted capabilities
- `transcript` — real-time TranscriptSegment
- `audio` — meeting audio (if subscribed)
- `event` — domain events from Redis Streams
- `participant_update` — join/leave notifications
- `error` — error with code + message

### Capabilities: `listen`, `speak`, `transcribe`, `extract_tasks`, `data_only`

---

## 5. Domain Model Changes

### New Models
- **`Room`** — id, name (unique), meeting_id, livekit_room_id, status (pending/active/closed), max_participants
- **`AgentSession`** — id, agent_config_id, meeting_id, room_name, connection_type, capabilities, status (connecting/active/disconnected)
- **`ConnectionType`** enum — webrtc, agent_gateway, phone

### Modified Models
- **`Meeting`** — `dial_in_number` and `meeting_code` become optional; add `room_id`, `room_name`, `meeting_type`
- **`Participant`** — add `connection_type`, `agent_config_id`, `OBSERVER` role
- **`AgentConfig`** — add `agent_type`, `protocol_version`, `default_capabilities`, `max_concurrent_sessions`

### New Events
- `room.created`, `agent.joined`, `agent.left`, `participant.joined`, `participant.left`, `agent.data`

### New ORM Models + Alembic Migration
- `RoomORM`, `AgentSessionORM` tables
- Alter `meetings` table (nullable dial-in fields, add room columns)

---

## 6. Phased Implementation

### Phase P-A: Agent Gateway MVP (10-14 dev-days, Medium risk)

**A.1: Domain Model Extensions (1-2 days)**
- Create `models/room.py`, `models/agent_session.py`
- Modify `meeting.py`, `participant.py`, `agent.py`
- Add 6 new events to `events/definitions.py`
- Add `RoomORM`, `AgentSessionORM` to `database/models.py`
- Alembic migration
- Tests for new/modified models and events

**A.2: Agent Gateway Service Scaffold (2-3 days)**
- New workspace member `services/agent-gateway/`
- `main.py` with FastAPI, `/health`, WebSocket `/agent/connect`
- `protocol.py` with all Pydantic message schemas
- `auth.py` with JWT validation
- `connection_manager.py` for session registry
- `agent_session.py` for per-agent lifecycle

**A.3: Audio Service Refactor (2-3 days)**
- Extract mulaw transcoding to `codecs.py`
- Create `AudioAdapter` ABC + `AgentGatewayAudioAdapter`
- Add `process_pcm16()` to `AudioPipeline` (skips transcoding)
- Keep `process_audio()` as wrapper for Twilio backward compat

**A.4: Event Relay (1-2 days)**
- `event_relay.py` — consumer group `agent-gateway` on `convene:events`
- Routes events to agent sessions by meeting_id + capabilities

**A.5: Integration Tests (2 days)**
- Protocol, auth, connection manager unit tests
- E2E: agent connect -> audio -> transcript -> relay

**Milestone M-A:** Agent connects via WebSocket, sends audio, receives transcript events

### Phase P-B: WebRTC Integration (8-12 dev-days, Medium-High risk)

**B.1: LiveKit Infrastructure (1-2 days)**
- Add LiveKit to docker-compose.yml
- `livekit.yaml` configuration
- Env vars: `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`

**B.2: Room Management (2-3 days)**
- `LiveKitClient` wrapper in api-server
- Room CRUD routes (`/api/v1/rooms`)
- Token generation route (`/api/v1/rooms/{name}/tokens`)

**B.3: LiveKit Audio Adapter (2-3 days)**
- `LiveKitAudioAdapter` joins rooms as hidden service participant
- Subscribes to audio tracks, forwards PCM16 to AudioPipeline
- Per-track -> per-speaker transcript events

**B.4: LiveKit Bridge in Agent Gateway (1-2 days)**
- `LiveKitBridge` represents agent as LiveKit room participant
- Publishes agent audio as track, relays data channels

**B.5: Participant Tracking (1-2 days)**
- Participant list routes (live via LiveKit API + DB)
- Mute/kick controls

**Milestone M-B:** Human + agent in same LiveKit room with live transcript

### Phase P-C: Meeting Web Client (10-15 dev-days, Medium risk)

**C.1: Project Setup (1-2 days)**
- Vite + React + TypeScript + Tailwind under `clients/meeting-client/`
- `@livekit/components-react`, `@livekit/client`, `zustand`

**C.2: Core Components (3-4 days)**
- `MeetingRoom.tsx` — main container
- `VideoGrid.tsx` — video tiles, agent visual treatment
- `ParticipantList.tsx` — roles, connection types, audio indicators
- `TranscriptPanel.tsx` — live auto-scrolling transcript
- `AgentSidebar.tsx` — extracted tasks, decisions, summaries

**C.3: LiveKit Integration (2-3 days)**
- `useLiveKit` hook for room connection
- `JoinScreen` with camera/mic preview, device selection

**C.4: Transcript WebSocket (1 day)**
- `ws://api-server/api/v1/meetings/{id}/transcript` endpoint
- Redis pub/sub channel for low-latency browser delivery

**Milestone M-C:** Full browser meeting with agent + transcript sidebar

### Phase P-D: Agent SDK (5-8 dev-days, Low risk)

**D.1: Package Structure (1-2 days)**
- `packages/convene-sdk/` with minimal deps (websockets, pydantic, PyJWT)

**D.2: Core Classes (2-3 days)**
- `ConveneClient` — main entry (async context manager)
- `MeetingSession` — send/receive audio and data, event iterator

**D.3: Examples (1-2 days)**
- `basic_listener.py`, `task_extractor.py`, `langchain_agent.py`, `crewai_agent.py`

**Milestone M-D:** SDK installable, basic_listener works end-to-end

---

## 7. TASKLIST.md Update Strategy

- **Preserve** all completed Phase 1A-1C items (no changes)
- **Keep** remaining Phase 1D-1E items (they're transport-agnostic, still needed)
- **Insert** new Phase P-A through P-D after Phase 1E, before Phase 2
- **Modify** Phase 2 Voice Output to use LiveKit instead of Twilio bidirectional
- **Strikethrough** Telephony Roadmap section (deprioritized)

---

## 8. Reuse Analysis

**Overall: ~90% of existing code reused or extended. Only ~244 lines of Twilio-specific code deprecated.**

| Category | Reuse |
|----------|-------|
| Domain models | 95% (extend) |
| Events | 100% (add new) |
| Interfaces/ABCs | 100% |
| Providers (9) | 100% |
| Memory system | 100% |
| Stream consumer | 100% |
| Task extractor/dedup | 100% |
| Audio pipeline | 70% (refactor) |
| Event publisher | 90% |
| API routes | 85% |
| Twilio handler/dialer | 0% (deprecated) |

---

## 9. Complexity Summary

| Phase | Days | Risk | Notes |
|-------|------|------|-------|
| P-A: Agent Gateway | 10-14 | Medium | Protocol design is critical — affects SDK |
| P-B: WebRTC/LiveKit | 8-12 | Medium-High | New technology, learning curve |
| P-C: Web Client | 10-15 | Medium | New codebase (React/TS), can parallelize |
| P-D: Agent SDK | 5-8 | Low | Thin wrapper over P-A protocol |
| **Total** | **33-49** | | |

**Parallelization:** Phase 1D remaining + P-A can run in parallel. P-C frontend can start once P-B routes exist. P-D can start once P-A protocol stabilizes.

---

## Open Questions

1. Should remaining Phase 1D items (task extraction, memory wiring) be completed in parallel with Phase P-A, or paused?
2. LiveKit Cloud for dev vs self-hosted from day 1?
3. Keep Twilio as a supported fallback path, or fully deprecate?
4. Phase P-A first target: test with existing Convene task extraction agent, or build a simple test agent?
