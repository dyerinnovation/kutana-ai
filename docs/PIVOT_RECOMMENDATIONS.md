# Convene AI — Pivot Recommendations: Agent-First Meeting Platform

> This document analyzes each existing strategy doc, identifies what needs to change for the pivot from "phone-dial-in meeting bot" to "agent-first meeting platform," and proposes new TASKLIST phases covering the user-facing product (signup, billing, agent marketplace, etc.) that are currently missing.

---

## Part 1: Document-by-Document Analysis

### VISION.md — Needs Major Rewrite

**What's still valid:**
- The core problem statement (meetings → commitments → no accountability) remains true
- The phased progression (listen → speak → converse → orchestrate) still applies
- The insight about AI being a participant, not a transcriber, is strengthened by the pivot
- The "Giving Agents a Seat at the Table" section is prophetic — it described the pivot before you made the decision
- Market size estimates are still directionally correct

**What needs to change:**

The one-liner needs to shift from "dials into your meetings" to "the meeting platform built for AI agents." The current framing positions Convene as a tool that bolts onto existing platforms. The new framing positions it as the platform itself.

The "Why Now" section lists three forces — voice AI latency, phone dial-in, and market stuck in transcription. The phone dial-in argument needs to be replaced. The new "why now" is that AI agents are proliferating (OpenAI Operator, Anthropic computer use, thousands of custom agents) and they all need a way to join meetings. No platform serves them. Convene fills that gap.

The business case section needs a dual-audience framing. The current doc only addresses teams who want smarter meetings. The pivot adds a second, arguably more important audience: developers building AI agents who need meeting access infrastructure. This is the Twilio-like API play.

The revenue model needs a usage-based tier for the developer API alongside the per-seat model for teams. The current pricing ($19/seat, $39/seat) works for the team product but doesn't capture the developer infrastructure revenue.

Unit economics need updating. Twilio costs drop significantly (or disappear) since you're running your own WebRTC media server. STT/LLM costs remain. New costs appear: WebRTC infrastructure (LiveKit hosting), bandwidth for video/audio streams, and the Agent Gateway service compute.

The competitive moat section should add "platform ownership" — unlike bolted-on tools, Convene owns the meeting environment. No risk of Zoom blocking your bot or Teams changing their API. And the agent ecosystem network effect: the more agents that support Convene, the more valuable it is for teams, and vice versa.

**Recommended action:** Full rewrite preserving the problem statement, insight, and phased progression. Restructure around two audiences (developers and teams) and the platform thesis.

---

### ROADMAP.md — Needs Structural Overhaul

**What's still valid:**
- F1.2 (Core Domain Models) — models carry forward with extensions
- F1.3 (Provider Abstraction) — the ABC pattern is fundamental to the new architecture too
- F1.5 (Real-Time Transcription Pipeline) — the STT pipeline is reusable
- F1.6 (Task Extraction Engine) — works as-is, just receives audio from new sources
- F1.7 (Memory System) — this is a key differentiator, unchanged
- F1.8 (API Server) — needs expansion but the foundation carries over
- F1.10 (Slack Integration) — still relevant for the team product
- Phase 2 (Speak & Report) — still applies, just over WebRTC instead of Twilio
- Phase 3 (Converse & Clarify) — unchanged
- Phase 4 (Specialize & Orchestrate) — unchanged and actually more natural on an owned platform

**What needs to change:**

F1.1 (Project Scaffolding) is done but needs additions for the new services (Agent Gateway, WebRTC integration, Meeting Web Client).

F1.4 (Twilio Phone Integration) shifts from being the core meeting access method to being one optional integration. The primary access methods become: (a) humans via browser/WebRTC and (b) agents via the Agent Gateway API. Twilio could still exist as a bridge for agents that want to patch into external meetings (Zoom, Teams) via phone, but it's no longer the main path.

F1.8 (API Server & Dashboard) needs to be split into multiple features: the API server becomes the central orchestrator for meeting rooms and participants. The dashboard becomes the Meeting Web Client — a full browser-based conferencing UI, not just a task/transcript viewer.

F1.9 (Calendar Integration) — less critical in the new model since you own the meeting platform. Users create meetings directly in Convene. Calendar integration becomes about syncing Convene meetings *to* their calendar, not scraping dial-in info from calendar events.

**New features needed (not in current roadmap):**
- Agent Gateway Service (WebSocket/gRPC endpoint for agent connections)
- WebRTC Media Server integration (LiveKit)
- Meeting Web Client (browser-based video/audio conferencing)
- Agent SDK (Python package for building Convene-compatible agents)
- User authentication and workspace management
- Billing and subscription management
- Agent marketplace / registry
- Developer portal and API documentation

**Recommended action:** Keep the existing feature specs that are still valid, add new feature specs for the platform components, and restructure the phase ordering to reflect the pivot. The new Phase 1 should focus on the Agent Gateway (the core differentiator) before building the human-facing meeting UI.

---

### COMPETITIVE_ANALYSIS.md — Needs Reframing

**What's still valid:**
- Market sizing numbers are still useful
- Competitor profiles (Otter, Fireflies, MeetGeek, etc.) are accurate
- The differentiation matrix is still largely true

**What needs to change:**

The competitive frame shifts. The current doc positions Convene against transcription tools (Otter, Fireflies) and meeting AI features (Zoom Companion, Copilot). Those are still relevant competitors for the team-facing product, but the pivot introduces a new competitive category: meeting infrastructure for AI agents.

New competitors to analyze:
- **Recall.ai** — Moves from "Tier 4: Infrastructure" to direct competitor. They provide meeting bot infrastructure. Convene's pitch is that instead of hacking bots into platforms that resist them, use a platform that welcomes agents natively. Recall.ai's $250M valuation and customer list (HubSpot, Calendly) validates the market but also shows the demand.
- **LiveKit / Daily.co** — WebRTC infrastructure providers. They're enabling layers, not direct competitors, but worth analyzing as potential partners or build-vs-buy decisions.
- **Zoom, Teams, Google Meet** — No longer just platforms Convene connects to. They become competitors in the meeting platform space. Convene's differentiation is agent-first design vs. their human-first (agent-hostile) design.
- **Recall.ai + any AI startup** — The combination of Recall.ai infrastructure + any AI meeting product is effectively what Convene offers in one integrated package. The integrated approach has advantages (lower latency, better UX, single billing) but the unbundled approach has flexibility.

The differentiation matrix needs a new row: "Native agent API" — Convene is the only one with a purpose-built agent connection protocol. Every other tool requires workarounds (phone dial-in, browser bots, or Recall.ai as a middleman).

The risk section needs a new entry: "Building a meeting platform is a massive engineering undertaking." Mitigations include LiveKit handling the hard WebRTC/SFU work, starting with audio-only meetings (simpler than full video), and the existing codebase providing the AI pipeline that would take competitors months to build.

**Recommended action:** Add a new section for the "Agent Infrastructure" competitive category. Update the differentiation matrix. Add platform competitors. Revise the risk section.

---

### GO_TO_MARKET.md — Needs Significant Revision

**What's still valid:**
- Phase 0 (consulting validation) is still smart
- The developer-first launch strategy is even more relevant with the pivot
- In-meeting virality mechanics still apply (even more so when you own the platform)
- Channel strategy (HN, Product Hunt, Twitter, LinkedIn) is unchanged
- Revenue projection structure is useful, numbers need adjusting

**What needs to change:**

The core GTM thesis needs to account for the two-sided market. The current doc assumes one growth loop: agent joins meeting → non-users see it → they sign up. The pivot creates two loops:

Loop 1 (Developer side): Developer builds an AI agent → needs meeting access → finds Convene API → integrates → their agent joins Convene meetings → more meetings happen on Convene.

Loop 2 (Team side): Team tries Convene for its built-in AI features → loves the task tracking and memory → invites more team members → meetings move to Convene → agents from Loop 1 are available.

The Phase 1 launch strategy needs a "developer beta" track. This means: API documentation site, quickstart guide, example agent code, a Python SDK published to PyPI, and a free tier with enough agent-minutes for prototyping. The narrative shifts from "I built an AI that joins your standups" to "I built a meeting platform where AI agents are first-class participants — here's the SDK."

Pricing needs the usage-based developer tier:
- **Free**: 100 agent-minutes/month, 5 meetings — prototyping
- **Developer**: ~$0.05–0.10/agent-minute, WebSocket/gRPC agent connections, structured data feeds
- **Team**: $20–50/seat/month — the end-user product with built-in AI features
- **Platform**: Custom pricing for companies running high-volume agents through Convene

The "What NOT to Spend Money On" section should add: don't build a full video conferencing UI before the agent API is proven. The agent API is the differentiator. The meeting UI can start minimal (audio-only, basic screen) and improve iteratively.

New distribution channels to add:
- **Agent framework ecosystems** — LangChain, CrewAI, AutoGen, Semantic Kernel. Get listed in their docs as the recommended meeting integration.
- **PyPI / npm** — The SDK itself is a distribution channel. Every `pip install convene` is a potential customer.
- **Open-source community** — Open-source the agent SDK and connection protocol. Let the community build integrations. This is how Twilio, Stripe, and LiveKit grew.
- **Partnership with Recall.ai customers** — Companies already using Recall.ai to get bots into meetings might prefer a platform that does it natively. Target their customer list.

**Recommended action:** Restructure around the two-sided market. Add developer GTM track. Update pricing. Add new distribution channels.

---

### README.md — Needs Complete Rewrite

The README currently describes Convene as "a voice-first AI agent that dials into your meetings via phone." This needs to become a description of the agent-first meeting platform. The architecture diagram needs updating to show the new services (Agent Gateway, WebRTC, Meeting Client). The "Architecture Decision: Phone Dial-In" section needs to become "Architecture Decision: Agent-First Platform" explaining why Convene owns the meeting environment instead of bolting onto existing platforms.

---

### CLAUDE.md — Needs Updates

The root CLAUDE.md needs to reflect new services in the architecture section, updated environment variables (LiveKit config, Agent Gateway config), and new packages if any are added. The "What NOT to Do" section should be updated — "Don't use platform-specific meeting SDKs" is still true, but the reasoning changes from "we use phone dial-in" to "we own the meeting platform."

---

## Part 2: Missing TASKLIST Phases — User-Facing Product

The current TASKLIST is entirely backend-focused. There's nothing about how a user signs up, pays, manages their workspace, adds agents, or views their meeting history through a real product interface. Below are the phases that need to be added.

### Phase 2A: User Authentication & Workspace Management

This is the foundation for everything user-facing. Without it, there's no product.

- [ ] Design database schema for users, workspaces, and memberships
- [ ] Implement user registration (email + password, email verification)
- [ ] Implement login / logout with JWT token management
- [ ] Implement OAuth login (Google, GitHub) for faster onboarding
- [ ] Implement workspace creation (a workspace is one team/org)
- [ ] Implement workspace invitations (invite by email, accept/decline)
- [ ] Implement role-based access control (owner, admin, member)
- [ ] Implement user profile management (name, avatar, notification preferences)
- [ ] Implement workspace settings (name, default meeting preferences)
- [ ] Implement API key generation for developer access
- [ ] **Milestone: A user can sign up, create a workspace, and invite team members**

### Phase 2B: Billing & Subscription Management

Revenue requires a way to pay. This should be built early so you can validate willingness to pay.

- [ ] Integrate Stripe for payment processing
- [ ] Implement subscription plans (Free, Developer, Team, Platform)
- [ ] Implement usage tracking (agent-minutes, meeting count, storage)
- [ ] Implement usage-based billing metering for the developer tier
- [ ] Implement plan upgrade/downgrade flows
- [ ] Implement billing dashboard (current plan, usage, invoices, payment method)
- [ ] Implement free tier limits enforcement (meeting caps, agent-minute caps)
- [ ] Implement trial period logic (14-day free trial of Team tier)
- [ ] Implement Stripe webhook handlers (payment success, failure, subscription changes)
- [ ] **Milestone: A user can subscribe to a paid plan and see their usage**

### Phase 2C: Meeting Creation & Management UI

Users need a way to create, schedule, and join meetings through Convene's own interface.

- [ ] Implement meeting creation flow (title, time, participants, recurrence)
- [ ] Implement meeting invitation system (email invites with join links)
- [ ] Implement meeting lobby / waiting room
- [ ] Implement meeting join flow for browser participants (WebRTC)
- [ ] Implement meeting controls UI (mute, camera, screen share, leave, end)
- [ ] Implement participant list showing humans and AI agents
- [ ] Implement meeting recording controls (start/stop, consent prompt)
- [ ] Implement meeting history view (past meetings, transcripts, extracted tasks)
- [ ] Implement meeting detail view (transcript replay, task timeline, decisions)
- [ ] Implement calendar sync (push Convene meetings to Google Calendar / Outlook)
- [ ] **Milestone: A team can create, join, and review meetings entirely within Convene**

### Phase 2D: Agent Marketplace & Management

This is the developer-facing product — where AI agents get registered, configured, and added to meetings.

- [ ] Design agent registration model (name, capabilities, auth, owner)
- [ ] Implement agent registration API (developers register their agents)
- [ ] Implement agent authentication (API keys or OAuth for agent connections)
- [ ] Implement agent capability declaration (listen, speak, push-ui, access-transcript)
- [ ] Implement agent connection protocol documentation (interactive API docs)
- [ ] Implement built-in agents (Convene's own task tracker, note taker, standup facilitator)
- [ ] Implement agent marketplace UI (browse available agents, see descriptions, reviews)
- [ ] Implement "Add agent to meeting" flow (select from marketplace or connect custom)
- [ ] Implement agent status dashboard (connected, active, error states, usage)
- [ ] Implement agent permissions management (which meetings can this agent join?)
- [ ] Implement agent analytics (how often used, which meetings, performance metrics)
- [ ] Publish Python SDK to PyPI (`pip install convene`)
- [ ] Create developer portal with quickstart guides and example agents
- [ ] **Milestone: A developer can register an agent, connect it to a meeting, and receive audio/events**

### Phase 2E: Real-Time Collaboration Surfaces

This is what makes meetings on Convene better than meetings on Zoom — the AI-generated content is visible to everyone in real-time.

- [ ] Implement shared meeting sidebar (visible to all participants during meeting)
- [ ] Implement live task extraction feed in sidebar (tasks appear as detected)
- [ ] Implement live decision log in sidebar
- [ ] Implement agent activity feed (what each agent is doing/detecting)
- [ ] Implement collaborative task editing (mark as done, reassign, add notes — during meeting)
- [ ] Implement meeting summary generation (auto-generated at meeting end)
- [ ] Implement post-meeting action items email/Slack notification
- [ ] Implement meeting context panel (previous meeting's open items, relevant history)
- [ ] **Milestone: During a meeting, participants can see AI-generated tasks and interact with them in real-time**

### Phase 2F: Dashboard & Analytics

The persistent workspace experience — what users see between meetings.

- [ ] Implement workspace dashboard (upcoming meetings, recent activity, task overview)
- [ ] Implement task board view (kanban: pending, in progress, done, blocked)
- [ ] Implement task detail view (source meeting, assignee, timeline, related discussions)
- [ ] Implement team member view (each person's commitments, completion rate)
- [ ] Implement meeting analytics (frequency, duration, task extraction rate)
- [ ] Implement agent performance analytics (extraction accuracy, user satisfaction)
- [ ] Implement notification center (task assignments, overdue items, meeting reminders)
- [ ] Implement search (across meetings, transcripts, tasks, decisions)
- [ ] Implement data export (CSV, JSON for tasks and meeting data)
- [ ] **Milestone: A workspace has a fully functional dashboard with task tracking and analytics**

### Phase 2G: Integrations

Connect Convene to the tools teams already use.

- [ ] Implement Slack integration (meeting summaries, task notifications, slash commands)
- [ ] Implement Linear integration (bidirectional task sync)
- [ ] Implement Jira integration (bidirectional task sync)
- [ ] Implement GitHub integration (link tasks to PRs, detect references in meetings)
- [ ] Implement Notion integration (push meeting summaries and task tables)
- [ ] Implement webhook API (generic event push for custom integrations)
- [ ] Implement Zapier / Make triggers (meeting.ended, task.created, etc.)
- [ ] **Milestone: Tasks extracted in Convene meetings automatically appear in the team's project management tool**

### Phase 2H: Platform Hardening

Before scaling, the platform needs to be production-ready.

- [ ] Implement rate limiting on all API endpoints
- [ ] Implement request validation and input sanitization
- [ ] Implement comprehensive error handling and user-friendly error messages
- [ ] Implement audit logging (who did what, when)
- [ ] Implement data retention policies and deletion (GDPR compliance)
- [ ] Implement meeting recording consent management
- [ ] Implement SSO (SAML/OIDC) for enterprise customers
- [ ] Implement admin panel for workspace owners (user management, billing, settings)
- [ ] Implement monitoring and alerting (service health, error rates, latency)
- [ ] Implement automated backups and disaster recovery
- [ ] Write deployment documentation (Docker, Kubernetes, cloud provider guides)
- [ ] **Milestone: Platform passes security review and is ready for enterprise pilots**

---

## Part 3: Recommended Phase Ordering

Given the pivot, here's the recommended order of work:

**Keep building (current Phase 1D):** Finish task extraction and memory — this is the core AI value regardless of how audio enters the system. Complete the remaining items: transcript windowing, LLM extraction pipeline, task persistence, memory layers.

**Next: Agent Gateway MVP (new Phase 2A-Auth + Agent Gateway from pivot prompt):** Build user auth and the Agent Gateway simultaneously. The gateway is the core differentiator. Test with your own task extraction agent as the first client.

**Then: WebRTC + Meeting UI (Phase 2C):** Add LiveKit for browser-based meetings. Build the minimal meeting UI. Now humans and agents can meet on Convene.

**Then: Billing (Phase 2B):** Add Stripe billing once there's a product to charge for.

**Then: Agent Marketplace (Phase 2D) + Collaboration Surfaces (Phase 2E):** These make the platform sticky.

**Then: Dashboard (Phase 2F) + Integrations (Phase 2G):** The full product experience.

**Finally: Platform Hardening (Phase 2H):** Before enterprise pilots.

---

## Part 4: Summary of Changes Needed

| Document | Change Level | Action |
|----------|-------------|--------|
| VISION.md | Major rewrite | Reframe around agent-first platform, dual audience, new revenue model |
| ROADMAP.md | Structural overhaul | Keep valid features, add platform features, reorder phases |
| COMPETITIVE_ANALYSIS.md | Significant additions | Add agent infrastructure category, new competitors, update matrix |
| GO_TO_MARKET.md | Significant revision | Two-sided market, developer GTM track, new pricing, new channels |
| README.md | Complete rewrite | New product description, architecture, getting started |
| CLAUDE.md | Moderate updates | New services, environment variables, conventions |
| TASKLIST.md | Major additions | Add Phases 2A through 2H covering all user-facing product work |
| BOOTSTRAP_REFERENCE.md | No change | Historical reference, keep as-is |
