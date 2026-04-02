# Kutana AI — Pivot to Agent-First Meeting Platform

## Prompt for Claude Code Planning Session

Copy everything below the line and paste it into Claude Code to trigger a planning session.

---

I want to pivot Kutana AI from a "phone-dial-in meeting bot" to an **agent-first meeting platform** — a meeting service built from the ground up where AI agents are first-class participants, not bolted-on bots.

### The Problem

Today's meeting platforms (Zoom, Teams, Google Meet) were built for humans. Getting an AI agent into these meetings requires hacks: Twilio phone dial-in (requires paid audio conferencing add-ons), headless browser bots (fragile, resource-heavy), or third-party APIs like Recall.ai (adds cost and dependency). As AI agents become more common (OpenAI's Operator, Anthropic's computer use, custom agents), more developers will hit this same wall.

### The Vision

Kutana becomes the meeting platform where:
1. **AI agents connect via a native Agent API** — direct audio/data streams, no phone lines or browser hacking
2. **Humans join via browser** — standard WebRTC-based video/audio meeting experience
3. **Agents are visible participants** — shown in the participant list with their capabilities and current status
4. **Structured context is available natively** — agenda, participant roles, documents, and meeting metadata are accessible to agents via API, not inferred from conversation
5. **Real-time collaboration surfaces** — agents can push live updates (extracted tasks, decisions, summaries) into a shared sidebar that all participants see
6. **Multi-agent support** — multiple AI agents can join a single meeting, each with different roles (note-taker, fact-checker, project tracker)

### What We Keep from Current Kutana

The existing codebase has significant value that carries forward:
- **kutana-core**: Domain models (Meeting, Task, Decision, Participant, TranscriptSegment), event definitions, database models — all still relevant
- **kutana-providers**: STT, TTS, and LLM provider abstractions and implementations — these become the processing backbone
- **kutana-memory**: Four-layer memory system — this is a differentiator, agents that remember across meetings
- **task-engine**: Redis Streams consumer infrastructure, event-driven architecture — this pattern stays
- **Audio pipeline expertise**: μ-law transcoding, STT streaming, audio buffering — reusable for the new audio infrastructure

### What Changes

1. **New: WebRTC Media Server** — replaces Twilio as the audio/video backbone. Handles human participants joining via browser and routes audio streams. Options: LiveKit (open-source, self-hostable), Janus, or mediasoup.

2. **New: Agent Gateway Service** — a dedicated service that AI agents connect to. Provides:
   - WebSocket or gRPC endpoint for agent connections
   - Direct audio stream (PCM/Opus) in and out — no phone line needed
   - Structured data channel for metadata, context, and real-time updates
   - Authentication and capability negotiation (can this agent listen? speak? push UI updates?)

3. **New: Meeting Web Client** — a browser-based meeting UI (React) where humans join meetings. Includes:
   - Standard video/audio conferencing via WebRTC
   - Participant list showing both humans and AI agents
   - Shared sidebar for agent-generated content (live tasks, decisions, summaries)
   - Meeting controls (mute, invite agent, view agent status)

4. **Modified: Audio Service** — instead of receiving audio from Twilio Media Streams, it receives audio from the WebRTC media server and the Agent Gateway. The STT pipeline stays the same.

5. **Modified: API Server** — expanded to handle meeting room creation, participant management (humans + agents), and real-time state. Becomes the central orchestrator.

6. **Kept: Task Engine, Memory System, Providers** — these work as-is, consuming events from the new audio sources.

### Architecture Sketch

```
Human (Browser)                    AI Agent (any framework)
      │                                    │
      │ WebRTC                             │ WebSocket/gRPC
      ▼                                    ▼
┌─────────────┐                   ┌─────────────────┐
│  WebRTC     │◄─── audio ───────►│  Agent Gateway   │
│  Media      │    routing        │  Service          │
│  Server     │                   │  (auth, streams,  │
│  (LiveKit)  │                   │   data channels)  │
└──────┬──────┘                   └────────┬──────────┘
       │                                   │
       │         audio streams             │
       ▼                                   ▼
┌──────────────────────────────────────────────┐
│              Audio Service                    │
│  (STT streaming, transcoding, buffering)      │
└──────────────────┬───────────────────────────┘
                   │ Redis Streams events
                   ▼
┌──────────────────────────────────────────────┐
│              Task Engine                      │
│  (extraction, dedup, persistence)             │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────┐
│     API Server + Memory System                │
│  (meeting state, tasks, decisions, history)    │
└──────────────────────────────────────────────┘
```

### Phased Approach

**Phase A: Agent Gateway MVP** — Build the Agent Gateway service so AI agents can connect, send audio, and receive transcripts/events. Test with our existing Kutana task extraction agent as the first client. No human-facing UI yet — use existing meeting audio piped through the gateway.

**Phase B: WebRTC Integration** — Add LiveKit (or similar) for browser-based human participants. Humans can create and join meetings. Audio from human participants flows through the same pipeline.

**Phase C: Meeting Web Client** — Build the React-based meeting UI with video, participant list, and the agent sidebar showing real-time extracted tasks/decisions.

**Phase D: Agent SDK** — Package the agent connection protocol into a Python SDK that any developer can use to build agents that join Kutana meetings. Publish documentation and examples.

### Constraints

- Keep Python 3.12+, uv workspaces, async-first, strict typing — all existing conventions from CLAUDE.md
- Keep the event-driven architecture via Redis Streams
- Keep provider abstraction (STT/TTS/LLM behind ABCs)
- Reuse existing domain models where possible, extend as needed
- LiveKit is the preferred WebRTC option (open-source, good Python SDK, built for programmable video)
- The Agent Gateway must be protocol-agnostic enough that agents built with any framework (LangChain, CrewAI, raw API calls, computer use agents) can connect

### What I Need

Create a detailed implementation plan that:
1. Assesses impact on every existing package and service
2. Proposes the new service architecture (Agent Gateway, WebRTC integration)
3. Defines the Agent API contract (how agents connect, authenticate, send/receive audio and data)
4. Updates the TASKLIST.md with new phases while preserving completed work
5. Identifies what from Phase 1D-1E can be reused vs. needs modification
6. Recommends which WebRTC media server to use and why
7. Estimates relative complexity of each phase

Start by reading the existing claude_docs/ for full context on current patterns, then develop the plan.
