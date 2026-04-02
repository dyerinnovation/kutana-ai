# Kutana AI — Product Vision & Business Case

## The One-Liner

Kutana is the meeting platform built for AI agents — where humans and AI collaborate in real-time, agents connect via a native API, and every commitment is tracked across meetings with persistent memory.

---

## The Problem

Two converging problems create the opportunity:

### Problem 1: The Broken Accountability Loop

Every team has the same broken loop:

1. People have a meeting and make commitments
2. Someone (maybe) writes down action items
3. Those notes sit in a doc or Slack thread
4. At the next meeting, nobody remembers what was agreed
5. Repeat

The tools that exist today — Otter, Fireflies, tl;dv — solve step 2. They transcribe, summarize, and extract action items. But the output is a document. It sits in a dashboard nobody checks. The accountability loop never closes.

### Problem 2: AI Agents Can't Join Meetings

AI agents are proliferating — OpenAI's Operator, Anthropic's computer use, thousands of custom agents built on LangChain, CrewAI, and other frameworks. These agents can browse the web, write code, send emails, and manage projects. But they can't join a meeting.

Today's meeting platforms were built for humans. Getting an AI agent into a Zoom call requires hacks: Twilio phone dial-in (requires paid audio conferencing add-ons on the meeting platform), headless browser bots (fragile, resource-heavy, actively blocked by platforms), or third-party APIs like Recall.ai (adds cost and dependency). Every developer building a meeting-adjacent AI tool hits this same wall.

## The Insight

**Don't hack AI into platforms that resist it — build the platform where AI belongs.**

An agent-first meeting platform solves both problems simultaneously. AI agents connect natively via API, getting clean audio streams and structured context without any hacking. And because the platform is designed for AI participation, the accountability features (task extraction, persistent memory, progress reporting) work dramatically better than bolted-on tools ever could.

## The Vision

Kutana is an agent-first meeting platform that serves two audiences:

### For Teams: Meetings That Actually Drive Accountability

Kutana is where teams meet when they want AI that goes beyond transcription:

- **Built-in AI agents** extract tasks, decisions, and commitments in real-time — visible to all participants in a shared sidebar during the meeting
- **Persistent memory** spans across meetings — the AI never forgets a commitment, tracks progress, and reports status at the next standup
- **The agent speaks** to deliver progress reports, confirm commitments, and flag conflicts — it's a participant, not a passive recorder
- **Real-time collaboration surfaces** let participants see, edit, and assign tasks as they're detected — not after the meeting in a doc nobody reads

### For Developers: The Meeting Access Layer for AI Agents

Kutana is infrastructure that gives any AI agent the ability to participate in meetings:

- **Agent Gateway API** — WebSocket/gRPC endpoint where agents connect, authenticate, and declare capabilities (listen, speak, push UI updates)
- **Direct audio streams** — clean PCM/Opus audio in and out, no phone lines or browser automation
- **Structured data channels** — agents receive meeting metadata, participant info, agenda, and can push real-time content to the meeting sidebar
- **MCP Server** — any MCP-compatible AI assistant (Claude, custom agents) can join Kutana meetings through standard tool calls like `join_meeting`, `get_transcript`, `send_audio`
- **Python SDK** — `pip install kutana` and connect an agent in 10 lines of code
- **Multi-agent support** — multiple AI agents join a single meeting, each with different roles and capabilities

### The Phased Progression

**Phase 1 — Listen & Learn**: Built-in AI agents listen silently, extract tasks and commitments, and present them in a real-time sidebar and dashboard. Persistent memory is built across meetings.

**Phase 2 — Speak & Report**: Agents can speak during meetings to deliver progress updates, flag overdue items, and confirm new commitments.

**Phase 3 — Converse & Clarify**: Full multi-turn dialogue — agents answer questions, flag conflicts ("That deadline overlaps with what Sarah committed to on Thursday"), and suggest priorities.

**Phase 4 — Ecosystem & Orchestrate**: An agent marketplace where developers publish specialized agents. Teams compose their meeting experience by selecting agents: a Scrum facilitator, a decision tracker, a client meeting summarizer, a compliance monitor.

### Concrete Use Cases for the Agent API

- **OpenClaw** (openclaw.ai) — An open-source personal AI assistant could join your morning standup via Kutana's MCP server and deliver your task updates on your behalf when you're unavailable.

- **CoWork scheduled tasks** — Overnight build agents that implement roadmap items could call into morning standups via Kutana to report what was built, what tests passed, and what blockers were hit.

- **Sales coaching agents** — A sales team's AI coach joins client calls on Kutana, provides real-time suggestions in the sidebar (visible only to the rep), and generates follow-up action items.

- **CI/CD pipeline agents** — Join sprint demos to report deployment status, test coverage, and release notes — speaking directly to the team instead of posting to a Slack channel nobody reads.

- **Research agents** — Join project debriefs to share findings from overnight research, summarize competitive intel, or present data analysis through the meeting sidebar.

- **Compliance agents** — Monitor meetings for regulatory commitments, flag potential compliance issues in real-time, and generate audit-ready records.

---

## Why Now

Three converging forces make this the right time:

### 1. AI agents are proliferating — and they all need meeting access

OpenAI's Operator, Anthropic's computer use, thousands of custom agents. The AI agent market is projected to reach $43–53B by 2030 (38–46% CAGR). Every one of these agents eventually needs to participate in human meetings. No platform serves them today. The developers building these agents are hitting the exact problem Kutana solves.

### 2. Voice AI latency has crossed the "natural conversation" threshold

Sub-300ms STT (Deepgram, AssemblyAI), sub-100ms TTS (Cartesia), and ~320ms LLM time-to-first-token combine for <800ms total round-trip — below the threshold where conversation feels natural. This makes a speaking AI meeting participant viable for the first time.

### 3. The market is stuck in "transcription mode"

A dozen well-funded competitors (Otter at $100M ARR, Fireflies at $1B valuation) are competing on who can transcribe and summarize meetings better. This is a commodity race. The leap from passive transcription to active participation — and from bolted-on tool to native platform — is the next inflection point.

### 4. MCP creates a universal agent protocol

The Model Context Protocol (MCP) is emerging as the standard way AI assistants interact with tools and services. By exposing Kutana as an MCP server, every MCP-compatible agent gets meeting access without custom integration work. This dramatically lowers the barrier for the agent ecosystem.

---

## Business Case

### Target Markets

**Primary: Developers building AI agents**
Developers at startups and enterprises building AI-powered tools that need meeting access. They currently resort to Twilio dial-in, headless browser bots, or Recall.ai. Kutana's Agent API and MCP server give them a purpose-built solution. Think of this as the "Twilio for meetings" play — infrastructure that other products build on.

**Secondary: Mid-market teams ($10M–$500M revenue)**
Teams with 20–200 employees where meeting accountability is a real workflow gap. They adopt Kutana for the built-in AI features (task extraction, memory, progress reporting) and stay for the platform.

**Tertiary: AI-native startups and agencies**
10–50 person teams that are already AI-forward, manage multiple projects, and need automated status tracking across concurrent engagements.

### Market Size

| Market | 2025 Size | Growth (CAGR) | 2030 Projection |
|---|---|---|---|
| AI Meeting Assistants | $2.5–3.7B | 25–35% | $7–20B |
| AI Agents (broad) | $5–8B | 38–46% | $43–53B |
| Voice AI Agents | $2–3B | ~35% | $8–12B |

Kutana sits at the intersection of all three. The agent infrastructure market (developer API) has no direct equivalent today — Recall.ai ($250M valuation) is the closest proxy, but they provide access to other platforms' meetings rather than owning the meeting environment.

### Revenue Model

**Developer API (usage-based)**:
- Free tier: 100 agent-minutes/month, 5 meetings — enough to prototype
- Developer: ~$0.05–0.10 per agent-minute, WebSocket/gRPC/MCP connections, structured data feeds
- Platform: Custom pricing for high-volume agent deployments

**Team Product (per-seat)**:
- Free: 5 meetings/week, built-in task extraction, basic dashboard
- Pro ($29/seat/month): Persistent memory, integrations (Slack, Linear, Jira), speaking agent
- Team ($49/seat/month): Multi-agent support, cross-team tracking, analytics, custom agent personas
- Enterprise (custom, $79+/seat): SSO, audit logs, data residency, dedicated support, on-premise deployment

**Important pricing principle**: No minute caps. Users hate minute caps — it's the #1 complaint about Otter and Fireflies. Kutana is unlimited meetings at every seat-based tier, with differentiation on features and team size.

### Unit Economics

| Cost Component | Per Meeting Hour |
|---|---|
| WebRTC infrastructure (LiveKit) | ~$0.05–0.15 |
| STT (streaming) | ~$0.15 |
| LLM (task extraction) | ~$0.05–0.10 |
| TTS (when agent speaks) | ~$0.05 |
| Compute (API, Gateway, Workers) | ~$0.10 |
| **Total COGS** | **~$0.40–0.55** |

By owning the meeting platform and using an open-source WebRTC server (LiveKit), COGS drops significantly compared to the original Twilio-based architecture (~$1.43/hour). At $29/seat/month with 20 meeting-hours/seat/month, COGS is ~$8–11/seat — yielding 62–72% gross margins, approaching traditional SaaS economics.

### Competitive Moat

1. **Platform ownership eliminates integration risk**: Unlike bolted-on tools, Kutana can't be blocked by Zoom updating their API or Teams cracking down on bots. You own the meeting environment.

2. **Two-sided network effects**: More agents on the platform → more value for teams. More teams on the platform → more incentive for developers to build agents. This flywheel is very hard to replicate.

3. **Persistent memory creates switching costs**: Once the agent knows your team's commitment history, project dependencies, and communication patterns, switching means losing institutional memory.

4. **Agent ecosystem moat**: As developers build agents for Kutana's API, the platform accumulates a marketplace of specialized agents. Each agent makes the platform more valuable. Competitors would need to attract both developers AND users simultaneously.

5. **MCP-first positioning**: By being the first meeting platform to support MCP, Kutana becomes the default meeting integration for the entire MCP ecosystem.

---

## The Founding Thesis

The meeting is where human work and AI work converge. Every commitment, decision, and status update passes through a meeting. By building the platform purpose-designed for that convergence — where AI agents connect as naturally as humans do — Kutana becomes the operating layer for AI-augmented teams.

The compound effects are what matter: every meeting Kutana hosts makes its agents smarter about your team, your commitments, and your patterns. The platform that never forgets a promise — and has the agents to enforce it — closes the gap between conversation and execution.

Kutana doesn't compete with Zoom on video quality or with Otter on transcription accuracy. It competes on a different axis entirely: it's the only meeting platform where AI agents are first-class participants, and the only AI meeting tool that owns the environment its agents operate in.
