# Market Landscape: AI Agents in Meetings

> Research compiled March 2026. Market size data from industry analyst reports.

## Overview

The meeting AI market is fragmented across four distinct categories — none of which solve the core problem Kutana addresses: open, multi-agent, first-class participation with turn management.

**Market size:** $3.5B in 2025, projected $21.5B by 2033 (CAGR ~25%).

---

## Category 1: Passive Recorders

These tools join meetings as a "notetaker bot" — they observe and transcribe, but cannot interact, speak, or respond in real time.

| Product | Model | Price | Notes |
|---------|-------|-------|-------|
| **Otter.ai** | Subscription | $15–30/mo | Real-time captions, post-meeting summary, action items |
| **Fireflies.ai** | Subscription | $18–29/mo | Transcript search, CRM sync, topic tracking |
| **Fathom** | Freemium | $15–30/mo | Clip highlights, Salesforce/HubSpot push |

**Key limitation:** These bots are observers only. They cannot speak, ask clarifying questions, or respond to participants in real time. They are fundamentally post-processing tools, not participants.

**What they get right:** Transcription quality is solid. Post-meeting summaries are valuable. They've proven users want AI in meetings.

**What they miss:** The agent cannot act during the meeting. There's no interaction layer. No turn management. No multi-agent scenario.

---

## Category 2: Infrastructure Providers

These companies provide the plumbing — APIs and SDKs for building meeting bots or adding AI to video infrastructure.

### Recall.ai
- Unified bot API for Zoom, Google Meet, and Microsoft Teams
- Provides a "bot user" that joins via screen share + virtual microphone injection
- Handles platform-specific quirks (admission dialogs, reconnect, audio capture)
- **Pricing:** Usage-based, typically $0.15–0.50/meeting-hour at scale
- **Key limitation:** Reverse-engineered workarounds. Fragile. Zoom has actively cracked down on bot accounts since 2024. Every platform update risks breakage. Bot users are second-class citizens — platforms detect and block them.

### LiveKit Agents
- Open-source WebRTC infrastructure (Apache 2.0)
- LiveKit Agents SDK adds AI pipeline support: STT → LLM → TTS loop
- Supports Deepgram, OpenAI, ElevenLabs out of the box
- **What it is:** Infrastructure for building voice AI apps, not a meeting platform
- **What it lacks:** No meeting room abstraction. No turn management. No multi-agent coordination. You build everything yourself.
- Kutana uses LiveKit as its WebRTC SFU — we build the agent-native layer on top.

### Daily.co
- Embedded video SDK with bot/server-side participant support
- Developer-friendly: REST API for room creation, server-side video track injection
- **Pricing:** $0.004/participant-minute + additional for recording
- **Niche:** Primarily used for building custom video apps (telehealth, customer support) rather than general meeting platforms

---

## Category 3: AI-Native Meeting Tools

These are purpose-built products where AI is central to the experience, typically targeting sales and revenue teams.

| Product | Focus | Price | Agent capability |
|---------|-------|-------|-----------------|
| **Gong** | Revenue intelligence | $1,400+/seat/year | Post-meeting analysis only; no live agents |
| **Chorus (ZoomInfo)** | Sales coaching | Enterprise pricing | Transcript + coaching cards; no live participation |
| **Read.ai** | Meeting copilot | $29.75/mo | Engagement scoring, attention tracking; passive observer |
| **MeetGeek** | Automated notes | $15–29/mo | Template-based summaries, CRM sync; notetaker pattern |

**Pattern:** These tools are all post-processing plays. Even the most advanced (Gong) is a recording + analytics product — no real-time agent participation.

The "meeting copilot" framing is misleading. These tools surface information to a human; they don't act as meeting participants themselves.

---

## Category 4: Agent Frameworks with Meeting Capability

Recent additions to the LLM ecosystem that enable voice/audio AI agents — but not meeting-aware participation.

### OpenAI Realtime API
- Bidirectional voice over WebSockets
- Low-latency speech-to-speech with GPT-4o
- No meeting concept: raw audio I/O only
- Requires significant scaffolding to build meeting behavior (turn management, participant awareness, context)

### Google ADK (Agent Development Kit) — Voice Mode
- Voice agent framework with Google's STT/TTS pipeline
- Designed for customer service / interactive voice response patterns
- No meeting room abstraction; no multi-agent coordination

### Claude Agent SDK (Anthropic)
- MCP-based tool use for agents
- Supports persistent sessions, memory, tool integration
- **What it enables:** Agents that use Kutana's MCP server to join meetings as first-class participants
- **What it lacks natively:** Audio I/O is not built in — Kutana provides the audio bridge via agent-gateway

---

## The Gap Nobody Has Filled

| Capability | Passive Recorders | Recall.ai | LiveKit Agents | Realtime APIs | **Kutana** |
|-----------|:-----------------:|:---------:|:--------------:|:-------------:|:-----------:|
| Works across platforms | ✓ | ✓ | — | — | Native |
| First-class participant | — | Partial | ✓ | ✓ | ✓ |
| Multi-agent support | — | — | Manual | Manual | ✓ Built-in |
| Turn management | — | — | Manual | Manual | ✓ Built-in |
| Any agent framework | — | — | Limited | Limited | ✓ Open |
| Open platform | — | — | Infrastructure | Infrastructure | ✓ |
| Stable (no API hacks) | ✓ | — | ✓ | ✓ | ✓ |

**Key finding:** No product on the market today offers an open platform where any AI agent from any provider joins as a first-class participant with built-in turn management and multi-agent coordination. The closest approaches either require reverse-engineering platform APIs (fragile) or building everything from scratch on raw WebRTC infrastructure (high effort, no meeting semantics).

Kutana is the first meeting platform designed with AI agents as first-class participants from day one.
