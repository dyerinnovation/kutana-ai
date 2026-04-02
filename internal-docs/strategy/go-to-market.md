# Kutana AI — Go-to-Market Strategy

---

## Core GTM Thesis

Kutana is pivoting from a meeting bot to an **agent-first meeting platform**. This unlocks two growth loops that reinforce each other:

**Growth Loop 1 (Developer-Centric):**
Developer builds an AI agent → needs reliable meeting access for the agent → discovers Kutana API/MCP server → integrates Kutana into their agent's workflow → agent joins Kutana meetings natively → their agent gains access to a growing network of meetings → visibility increases → more teams adopt Kutana to use these agents.

**Growth Loop 2 (Team-Centric):**
Team tries Kutana for built-in AI features (task tracking, persistent memory, meeting assistant) → discovers the value of smart meeting intelligence → loves the outcome (less wasted meetings, more accountability) → invites more team members → entire org moves meetings to Kutana → agents from Loop 1 are now available to this team at no additional friction.

The insight remains: **the product markets itself inside every meeting it joins.** But by owning the platform, we control the entire experience. Every meeting on Kutana is a controlled, curated moment where AI value is showcased perfectly. An agent speaking a progress report is more memorable and convincing than any marketing dollar could buy.

The trust component remains critical. Meeting AI faces a serious legitimacy problem (Otter's lawsuit, user distrust). Kutana grows through the same viral mechanism while positioning as the ethical, consent-first, developer-friendly alternative.

---

## Phase 0: Validate Before Building (Weeks 1–4)

### Sell the Service, Build the Product

Before writing any code beyond the MVP, validate demand by offering the core Kutana workflow as a manual consulting service:

1. **Attend client meetings** (or review their recordings/transcripts)
2. **Extract tasks and commitments** using Claude/GPT
3. **Deliver a structured brief** before their next meeting: completed items, open items, blocked items, conflicts
4. **Iterate on the format** based on what teams actually find useful

**Pricing**: $500–1,500/month per team for weekly meeting analysis. This is cheap enough for startups and small enough to be expensed without procurement.

**Goal**: 3–5 paying consulting clients. This validates:
- Do teams actually want cross-meeting task tracking?
- Will they let an AI (even a human-assisted one) into their meeting workflow?
- What meeting types benefit most? (Standups? Sprint planning? All-hands?)
- What output format do they actually use? (Slack? Dashboard? Email?)

Revenue from this phase ($1,500–7,500/month) offsets development costs and provides real usage data to inform product decisions.

---

## Phase 1: Dual-Track Launch — Developers & Teams (Months 1–3)

### Developer Track: "AI Agents Can't Join Meetings"

**Target Persona**: AI/ML engineers, LLM app developers, AI startup founders — people building agents and workflows.

**Core Problem**: Developers have built sophisticated AI agents for reasoning, task automation, and decision-making, but these agents are locked out of the largest information-sharing forum in enterprise software: meetings. They can read transcripts, but they can't participate in real time, ask clarifying questions, or be held accountable for their outputs.

**Kutana Solves**: Agents become first-class meeting participants via Kutana's API and MCP server. A developer integrates Kutana once and their agent gains:
- Reliable meeting access (no platform lock-in)
- Real-time transcription and context
- The ability to speak and influence outcomes
- Meeting memory that persists across conversations

**Launch Activities**:

1. **Developer documentation and quickstart**:
   - API reference (async Python SDK, REST endpoints)
   - MCP server documentation and examples
   - Five-minute quickstart: "Connect your agent to Kutana in 5 lines of code"
   - Hosted docs with interactive examples

2. **Python SDK on PyPI**:
   - `pip install kutana-ai` — the frictionless entry point
   - Includes async helpers, type hints, example agents
   - Open-source on GitHub with MIT license

3. **Example agents**:
   - A basic standup tracker (reads transcript, extracts tasks, posts to Slack)
   - A meeting assistant that tracks decisions and flags conflicts
   - A voice agent that speaks progress reports
   - All examples runnable in <10 minutes

4. **MCP Server documentation**:
   - List Kutana in official MCP server directories
   - Integration with Anthropic's tool registry
   - Docs on how to register a custom agent with Kutana

5. **Developer community**:
   - Discord server for agent builders
   - GitHub discussions for questions and feedback
   - Monthly "agent showcase" — developers demo agents they've built

6. **Content strategy**:
   - Blog series: "AI Agents Can't Join Meetings (Yet)"
   - Technical deep-dives: "Building a multi-agent meeting system," "Using tool_use for real-time task extraction"
   - SEO targets: "AI agent meeting access," "LLM agent real-time collaboration," "MCP server for meetings"

**Expected Outcome**: 50–100 developers integrate Kutana. Each integration drives teams to adopt Kutana to access those agents. Developer virality amplifies team adoption.

---

### Team Track: "The Meeting Platform Where AI Actually Works"

**Target Persona**: Technical founder / Engineering lead at a 10–50 person startup. Same as before.

**Core Problem**: Teams run 20+ meetings per week, capture 0 insights, and action items are forgotten by EOD. Existing meeting tools (Otter, Fireflies) produce transcripts nobody reads. Teams need a platform where meeting data is automatically structured, tracked, and actioned.

**Kutana Solves**: Kutana is a meeting platform (not a bot overlay). Teams host meetings on Kutana, and every meeting automatically extracts tasks, maintains persistent memory, and integrates into the team's workflow. Plus: agents from Loop 1 are available as first-class participants.

**Launch Activities**:

1. **Soft launch** (Week 1–2):
   - Deploy Phase 1 MVP (listen + extract, no speaking yet)
   - Convert consulting clients to product
   - Invite 10–20 founders from personal network for beta
   - Aggressive feedback collection

2. **HN Launch** (Week 3):
   - "Show HN: I tried to get my AI agent into a Zoom call. So I built a meeting platform where agents are first-class participants."
   - Emphasize the architectural choice (phone dial-in for universality + API for agent integration)
   - Highlight the vision (AI that never forgets a promise)
   - Open-source one component (task extraction prompts, meeting URL parser, Twilio utilities)

3. **Product Hunt Launch** (Week 4):
   - Tuesday launch for max visibility
   - Leverage early users for Day 1 momentum
   - Meeting AI category performs exceptionally well on PH

4. **Content flywheel** (Week 5–6):
   - Founder blog: "What I learned building a platform for AI agents in meetings"
   - Technical blog: "How to extract action items with Claude using tool_use"
   - Why phone dial-in is superior to platform SDKs
   - These serve dual purpose: SEO credibility + developer narrative

### Channels (Ranked by Expected ROI)

1. **In-meeting virality** — every meeting the agent joins, 3–10 people see it. The free tier must be generous (100 agent-minutes/month, 5 meetings) to encourage wide adoption.

2. **Agent framework ecosystems** — LangChain, CrewAI, AutoGen. Get Kutana listed in their integration docs. Developer-to-developer word-of-mouth.

3. **MCP ecosystem** — Listed in MCP server registries, Anthropic's tool registry, and other AI framework integrations.

4. **PyPI / npm** — SDK distribution channel. "I searched for 'meeting' on PyPI and found Kutana."

5. **Hacker News / Reddit** — Technical founders live here. Ongoing participation in r/startups, r/SaaS, r/ChatGPT, r/LocalLLMs.

6. **Twitter/X founder community** — Build in public. Share metrics, architecture decisions, agent examples.

7. **Product Hunt** — One-time launch event with sustained tail.

8. **LinkedIn** — Secondary channel for engineering managers at mid-market.

9. **Open-source community** — Release the core connection protocol and SDKs as open-source. Community contributions amplify reach.

10. **Zoom App Marketplace** — Even though Kutana uses phone dial-in, a marketplace listing provides discovery and legitimacy.

11. **SEO / Content Marketing** — Target keywords: "AI agent meeting platform," "AI meeting assistant," "meeting action item tracker," "AI for standups."

### What NOT to Spend Money On (Yet)

- Paid advertising (Google, LinkedIn Ads) — CAC is too high for early stage
- Sales team — sell founder-to-founder for the first 100 customers
- PR agencies — organic HN/PH/Twitter outperforms paid PR
- Conference sponsorships — too expensive per lead for solo founder
- Influencer marketing — not authentic to the developer/founder audience

---

## Phase 2: Mid-Market Expansion (Months 4–8)

### Target Persona Expands: Engineering Manager / VP of Product at $10M–$500M company

This persona:
- Manages 3–5 teams running standups and planning meetings
- Frustrated that action items from meetings never get tracked
- Has budget ($1K–5K/month range is easy to approve)
- Evaluates tools based on integration quality and team-wide adoption
- Found Kutana because a direct report started using it OR an agent they want to access requires Kutana

### Key Activities

**Integrations as growth levers**: Slack and Linear/Jira integrations are table stakes. Every Slack notification from Kutana is a mini-advertisement. Every Linear ticket auto-created from a meeting commitment demonstrates value.

**Team-level onboarding**: Shift from individual signup to team onboarding. "Add Kutana to your team's recurring meetings" — one-click setup for all standup/planning meetings.

**Case studies from Phase 1 users**: Quantified results — "Team X reduced meeting time by 20% and increased task completion rate by 35% after 8 weeks with Kutana."

**Self-serve annual plans**: Offer 20% discount for annual billing.

**Agent marketplace**: As agents from Loop 1 prove valuable, showcase them on Kutana's marketplace. "Install these 3 agents to your Kutana workspace."

---

## Phase 3: Voice Agent Launch (Months 6–10)

### The "Agent Speaks" Moment

When the agent can speak in meetings, GTM shifts dramatically. This is a "show, don't tell" product.

**Demo video as primary asset**: Record a real standup where Kutana's agent reports on last meeting's tasks. Video goes on landing page, Twitter, LinkedIn, Product Hunt update, HN.

**"Kutana just spoke in my meeting" viral moment**: Genuine surprise creates organic social posts, Slack messages, word-of-mouth.

**Gated access to speaking features**: Launch voice features as waitlist or invite-only tier. Creates urgency, controls quality, generates social proof.

---

## Pricing (Updated for Two-Sided Market)

| Tier | Price | Target | Key Features |
|---|---|---|---|
| Free | $0 | Developers prototyping, teams evaluating | 100 agent-minutes/month, 5 meetings, listen + extract, no integrations |
| Developer | $0.05–0.10 per agent-minute (usage-based) | AI/ML engineers shipping agents | Unlimited API calls, MCP server support, agent marketplace access, 5 team members for testing |
| Pro | $29/seat/month | Small teams (<10) | Unlimited meetings, persistent memory, task tracking, Slack integration, up to 10 seats |
| Team | $49/seat/month | Growing teams (10–50) | All of Pro + speaking agent, cross-team task tracking, analytics dashboard, agent installation, up to 100 seats |
| Enterprise | Custom ($79+/seat) | 100+ seats | All of Team + SSO, audit logs, dedicated support, custom agents, data residency, on-premise option |

**Key principle**: Do NOT cap by minutes. Users hate minute caps (Otter's #1 complaint). Differentiate on features and team size, not artificial limits.

**Developer API economics**: Assume 10–20 developers each running agents in 5–10 meetings/month. At $0.075/agent-minute, this is $75–150/developer/month, offsetting infrastructure costs while remaining cheap for the developer.

---

## Revenue Projections (Conservative)

| Month | Team MRR | Developer API MRR | Total MRR | Customers (teams) | Developers |
|---|---|---|---|---|---|
| 3 | $2,000 | $500 | $2,500 | 5 | 8 |
| 6 | $8,000 | $3,000 | $11,000 | 25 | 35 |
| 9 | $25,000 | $8,000 | $33,000 | 70 | 90 |
| 12 | $60,000 | $18,000 | $78,000 | 150 | 200 |
| 18 | $150,000 | $45,000 | $195,000 | 350 | 450 |
| 24 | $350,000 | $120,000 | $470,000 | 700 | 1,000 |

These are deliberately conservative. The meeting AI viral loop, once established, compounds faster than most B2B SaaS. Developer API revenue scales with agent adoption, creating a new revenue stream independent of team seat growth.

---

## Distribution Channels (Detailed)

### Agent Framework Ecosystems
- LangChain integration docs (Kutana as a "tool" for agents)
- CrewAI examples (multi-agent meeting coordination)
- AutoGen setup guides
- Getting listed in these frameworks' official docs is a distribution multiplier.

### PyPI / npm
- `pip install kutana-ai` is the entry point for developers
- SDK distribution is self-service discovery
- High-quality README and examples drive adoption

### MCP Ecosystem
- List in official MCP server registries
- Anthropic's tool directory
- Other AI framework tool registries
- Every listing is a potential integration point

### Open-Source Strategy
- Release Python SDK as MIT-licensed open-source
- Release connection protocol and agent examples as open-source
- Community contributions and feedback drive product improvement
- Builds goodwill in the AI community

### Recall.ai Partnership Opportunity
- Recall.ai has existing customers paying for meeting bot access
- Partnership: "Use Recall for recording, Kutana for agent coordination"
- Or: "Migrate your Recall workflows to Kutana's agent-first platform"
- Existing customer relationships accelerate adoption

### Developer Relations
- Sponsor AI/ML conferences (not expenses, partnerships)
- Host "Agent Summit" — virtual meetup for Kutana agent builders
- Feature developer stories on blog and social
- Quarterly "State of Kutana Agents" report

---

## Key Metrics to Track

**Leading indicators** (product-market fit signals):
- Meeting join success rate
- Task extraction accuracy
- Free → paid conversion rate (target: 5–8% for teams, 15–20% for developers)
- Meetings per team per week (engagement depth)
- Time to "aha moment" — meetings before converting
- Developer SDK adoption rate (PyPI downloads, GitHub stars)
- Number of unique agents running on Kutana

**Lagging indicators** (business health):
- Team MRR and growth rate
- Developer API MRR and growth rate
- Net revenue retention (target: >110% for teams, >120% for developer API)
- CAC payback period (target: <3 months organic)
- Churn rate (target: <5% monthly for Pro, <3% for Team/Enterprise)

**Virality metrics**:
- Meetings with non-users present (exposure events)
- Signup rate from meeting exposure (viral coefficient)
- Agent discovery → installation rate (developer virality)
- Cross-team agent usage (agents as growth vector)

---

## Competitive Positioning

### For Developer Teams / AI Engineers

**Kutana AI** is the agent-first meeting platform. While other tools make transcripts, Kutana makes agents first-class meeting participants. Build an agent once, access every meeting via Kutana's API or MCP server — no platform lock-in, no SDK hacks. Your agents gain real-time visibility, can speak and influence decisions, and maintain persistent memory across conversations. **Unlike closed-garden solutions** (Zoom, Teams bots) that lock you into one platform, **Kutana agents work everywhere** because they dial in via phone and coordinate via APIs.

### For Engineering Teams / Startup Founders

**Kutana AI** is the meeting platform where AI actually works. Teams start using Kutana because they need smarter meetings (automatic task tracking, persistent memory, action item accountability). They stay because the platform becomes the source of truth for what everyone committed to. As your team grows, the Kutana agent marketplace provides off-the-shelf assistants to unlock even more value. **Unlike transcription tools** (Otter, Fireflies) that produce documents nobody reads, **Kutana is a real platform** where tasks are tracked, memory persists, and agents help teams ship faster.
