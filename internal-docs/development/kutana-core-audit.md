# kutana-core Audit — Post-Managed-Agents Migration

**Date:** 2026-04-09  
**Context:** Following the migration to Anthropic Managed Agents, some kutana-core modules that served the old self-hosted agent infrastructure are partially or fully obsolete. This audit documents every module, its current usage, and a keep/refactor/deprecate recommendation.

---

## Overview

`packages/kutana-core` is the foundational domain model and service interface layer for Kutana AI. It contains:

- **Domain models** — Pydantic-based models for meetings, participants, tasks, decisions, transcripts, and more
- **Database layer** — SQLAlchemy ORM models and async session management
- **Event definitions** — Domain events for inter-service communication via Redis Streams
- **Provider interfaces** — Abstract base classes defining contracts for LLM, STT, TTS, chat store, and turn management
- **Extraction pipeline** — Entity extraction framework with deduplicator, batch collector, and SDK utilities
- **Feeds integration** — Channel adapters for bidirectional MCP and channel-based integrations
- **Utilities** — Encryption, messaging abstractions, and participant base classes

The migration to Anthropic Managed Agents has fundamentally changed how agents connect and participate. Previously, the system maintained custom agent infrastructure (WebSocket gateway, AgentSession/AgentConfig models, AgentParticipant abstractions). Now, agent lifecycle is delegated to Anthropic Managed Agents, which consolidates authentication, session management, and execution into a hosted service.

---

## Module Reference

### models/

| Module | Description | Used By | Recommendation |
|--------|-------------|---------|----------------|
| `models/meeting.py` | Meeting domain model with lifecycle status (SCHEDULED, ACTIVE, COMPLETED, FAILED) | api-server, worker | **KEEP** |
| `models/task.py` | Task with priority, status, transition validation (PENDING → IN_PROGRESS → DONE; BLOCKED state) | api-server, task-engine, worker | **KEEP** |
| `models/decision.py` | Decision recorded during a meeting with participants and rationale | extraction pipeline | **KEEP** |
| `models/transcript.py` | TranscriptSegment with speaker, timecode, confidence score | audio-service, task-engine, agent-gateway | **KEEP** |
| `models/participant.py` | Participant domain model (Host, Participant, Agent, Observer roles) | event definitions | **KEEP** |
| `models/user.py` | User domain model for account management | api-server | **KEEP** |
| `models/chat.py` | ChatMessage with semantic type (TEXT, QUESTION, ACTION_ITEM, DECISION) | mcp-server, agent-gateway | **KEEP** |
| `models/room.py` | Room for meeting participants, with LiveKit integration | database (ORM) | **KEEP** |
| `models/feed.py` | Feed configuration models (FeedCreate, FeedRead, FeedUpdate) | api-server, worker | **KEEP** |
| `models/turn.py` | Turn management domain models (QueueEntry, QueueStatus, SpeakingStatus, HandRaisePriority) | agent-gateway | **KEEP** |
| `models/agent.py` | AgentConfig: voice ID, system prompt, capabilities, protocol version | api-server (legacy routes) | **DEPRECATE** — agent configuration is now owned by Anthropic Managed Agents; remove once legacy routes are cleaned up |
| `models/agent_session.py` | AgentSession domain model; ConnectionType enum (WEBRTC, AGENT_GATEWAY, PHONE) | agent-gateway (legacy) | **DEPRECATE** — sessions now managed by Anthropic; AGENT_GATEWAY connection type is obsolete |

### database/

| Module | Description | Used By | Recommendation |
|--------|-------------|---------|----------------|
| `database/base.py` | SQLAlchemy DeclarativeBase for ORM inheritance | all services | **KEEP** |
| `database/session.py` | create_engine(), create_session_factory(), get_session() async generators | api-server, task-engine | **KEEP** |
| `database/models.py` (non-agent schemas) | MeetingORM, TaskORM, ParticipantORM, TranscriptSegmentORM, DecisionORM, FeedORM, UserORM, etc. | all services | **KEEP** |
| `database/models.py` (AgentConfigORM, AgentSessionORM) | ORM persistence for legacy agent configuration and sessions | agent-gateway (legacy) | **DEPRECATE** — remove after agent-gateway migrates away from local session tracking |

### events/

| Module | Description | Used By | Recommendation |
|--------|-------------|---------|----------------|
| `events/definitions.py` | 22 event types: MeetingStarted, TaskCreated, ParticipantJoined, AgentJoined, HandRaised, SpeakerChanged, TranscriptSegmentFinal, etc. | all services | **KEEP** |

### messaging/

| Module | Description | Used By | Recommendation |
|--------|-------------|---------|----------------|
| `messaging/abc.py` | MessageBus ABC: publish(), subscribe(), unsubscribe(), ack(), close() | all services (TYPE_CHECKING) | **KEEP** |
| `messaging/types.py` | Message, MessageHandler, Subscription dataclass | all services (TYPE_CHECKING) | **KEEP** |

### interfaces/

| Module | Description | Used By | Recommendation |
|--------|-------------|---------|----------------|
| `interfaces/chat_store.py` | ChatStore ABC: send_message(), get_messages(), clear_meeting() | agent-gateway | **KEEP** |
| `interfaces/turn_manager.py` | TurnManager ABC: raise_hand(), get_queue_status(), mark_finished_speaking(), etc. | agent-gateway | **KEEP** |
| `interfaces/llm.py` | LLMProvider ABC: extract_tasks(), summarize(), generate_report() | task-engine (TYPE_CHECKING) | **KEEP** |
| `interfaces/stt.py` | STTProvider ABC: start_stream(), send_audio(), get_transcript(), close() | audio-service (TYPE_CHECKING) | **KEEP** |
| `interfaces/tts.py` | TTSProvider ABC: synthesize_stream(), synthesize_batch(), list_voices(), get_cost_per_char() | agent-gateway (TYPE_CHECKING) | **KEEP** |

### extraction/

| Module | Description | Used By | Recommendation |
|--------|-------------|---------|----------------|
| `extraction/abc.py` | Extractor ABC: extract() method; name and entity_types properties | task-engine | **KEEP** |
| `extraction/types.py` | 7 entity types: TaskEntity, DecisionEntity, QuestionEntity, EntityMentionEntity, KeyPointEntity, BlockerEntity, FollowUpEntity | task-engine | **KEEP** |
| `extraction/collector.py` | BatchCollector: buffers transcript segments, fires extractors on window timeout | task-engine | **KEEP** |
| `extraction/deduplicator.py` | EntityDeduplicator: in-memory registry per meeting, filters duplicates by similarity | task-engine | **KEEP** |
| `extraction/loader.py` | ExtractorLoader: hot-loads custom Extractor implementations from entry points | optional feature | **KEEP** (low priority) |
| `extraction/sdk.py` | SimpleExtractor base class, extractor() decorator, make_* factory functions | SDK / third-party | **KEEP** (low priority) |

### feeds/

| Module | Description | Used By | Recommendation |
|--------|-------------|---------|----------------|
| `feeds/adapters.py` | ChannelAdapter ABC, MCPChannelAdapter (HTTP), ClaudeCodeChannelAdapter (stdio), ADAPTER_REGISTRY, build_adapter() | worker | **KEEP** |

### participants/

| Module | Description | Used By | Recommendation |
|--------|-------------|---------|----------------|
| `participants/base.py` | Participant ABC, HumanParticipant (browser), AgentParticipant (gateway), DEFAULT_CAPABILITIES | minimal direct use | **DEPRECATE** — AgentParticipant represents the old WebSocket gateway model; HumanParticipant still somewhat relevant but underused |

### Utilities

| Module | Description | Used By | Recommendation |
|--------|-------------|---------|----------------|
| `encryption.py` | encrypt_value(), decrypt_value() using Fernet (AES-128-CBC + HMAC-SHA256) | api-server, worker | **KEEP** |

---

## Usage by Service

| Service | Core Dependency | Legacy Dependency | Notes |
|---------|----------------|-------------------|-------|
| api-server | models.*, database.*, events.*, encryption | AgentConfigORM (legacy routes) | Core service; heavy domain model usage |
| task-engine | extraction.*, events.*, database.models, models.transcript | none | Extraction pipeline is fully current |
| audio-service | events.definitions, interfaces.stt, models.transcript | none | Clean; no legacy coupling |
| agent-gateway | events.definitions, interfaces.*, models.chat, models.turn | AgentSessionORM, AgentConfig | Mixed; legacy agent session tracking alongside new Managed Agents integration |
| worker | database.models, encryption, feeds.*, models.* | none | Clean; no legacy coupling |
| mcp-server | models.chat | none | Minimal dependency |

---

## Legacy Code Identified (Pre-Managed-Agents)

### 1. AgentSession and AgentConfig Models
- **Files**: `models/agent_session.py`, `models/agent.py`, `database/models.py` (AgentSessionORM, AgentConfigORM)
- **Status**: Partially deprecated
- **Why**: Anthropic Managed Agents now handles agent lifecycle, session creation, and capability negotiation. The `AGENT_GATEWAY` connection type in `ConnectionType` is particularly obsolete.
- **Action**: Remove once agent-gateway migrates away from local session tracking; keep `ConnectionType.WEBRTC` and `ConnectionType.PHONE` if those connection types remain relevant.

### 2. AgentParticipant / Participant ABC
- **File**: `participants/base.py`
- **Status**: Legacy pattern
- **Why**: Represents the old self-hosted agent connection model (WebSocket via agent-gateway). Agents now participate via Anthropic infrastructure.
- **Action**: Remove `AgentParticipant`. Review whether `HumanParticipant` and the `Participant` ABC provide value; if not directly used, remove entirely.

### 3. ParticipantJoined / AgentJoined Events with agent_config_id
- **File**: `events/definitions.py`
- **Status**: Still used but semantics have shifted
- **Action**: Keep for now; clarify in docstrings that agent join/leave is now delegated to Anthropic Managed Agents. Remove `agent_config_id` field from events when agent-gateway cleanup is done.

---

## Recommendations Summary

| Category | Modules | Action | Urgency |
|----------|---------|--------|---------|
| Core Domain | models/meeting, task, decision, transcript, participant, user, chat, room, turn | KEEP | — |
| Database | database/base, session, models (non-agent) | KEEP | — |
| Events | events/definitions | KEEP | — |
| Messaging | messaging/abc, messaging/types | KEEP | — |
| Interfaces | interfaces/* | KEEP | — |
| Extraction | extraction/abc, types, collector, deduplicator | KEEP | — |
| Extraction SDK | extraction/loader, extraction/sdk | KEEP (low priority) | — |
| Feeds | feeds/adapters | KEEP | — |
| Utilities | encryption.py | KEEP | — |
| **Legacy Agent** | models/agent_session, models/agent, participants/base | **DEPRECATE** | HIGH |
| **Legacy ORM** | database/models (AgentConfigORM, AgentSessionORM) | **DEPRECATE** | HIGH |

---

## Recommended Next Steps

1. **Deprecation notices** — Add `# DEPRECATED: post-managed-agents migration` comments in `models/agent_session.py`, `models/agent.py`, `participants/base.py`, and the agent ORM classes in `database/models.py`.

2. **agent-gateway audit** — Identify all uses of `AgentSessionORM` and `AgentConfig` in `services/agent-gateway/`; replace with Managed Agents API calls or remove entirely.

3. **Remove AGENT_GATEWAY from ConnectionType** — This enum value is an artifact of the old self-hosted gateway; simplify to WEBRTC and PHONE.

4. **Drop ORM schemas in a migration** — Once all code references are removed, create an Alembic migration to drop the `agent_sessions` and `agent_configs` tables.

5. **Remove participants/base.py** — Once all imports are cleaned up, delete the file.

6. **Re-enable kutana-core tests** — After cleanup, remove the `--ignore=packages/kutana-core/tests` workaround from `pyproject.toml` and fix the `uv sync` / src-layout import issue properly.
