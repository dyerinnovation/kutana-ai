# Platform Strategy: Why Convene Must Own the Meeting Layer

> The question isn't whether to build a platform. It's whether the opportunity is real enough to justify one. The answer is yes — and the argument is simpler than it looks.

---

## Jonathan's Thesis: Own the Meeting Layer

The strategic bet is this: **personal AI agents are a genuinely new use case**. Nobody uses Zoom to talk to their Claude agent. Not because it's technically hard (though it is), but because that's not what Zoom is for. Zoom is for humans meeting each other. The concept of a personal agent as a meeting co-pilot — joining on your behalf, participating in real time, remembering context across every meeting — doesn't fit the incumbent product categories.

Convene isn't trying to out-feature Zoom. It's building the room where agents are the point.

This is the difference between competing with a platform and creating a new one. Slack didn't compete with email by being a better email client. It created a different kind of communication that happened to coexist with email, then ate email's lunch in team settings. Convene does the same thing for meetings: build something new where agents are native, let critical mass develop, and let the traditional platforms eventually chase Convene rather than the other way around.

---

## Why Integration-First Would Fail

The alternative strategy — integrate with Zoom/Meet/Teams, meet users where they are — sounds pragmatic. It's actually a dead end:

1. **Platforms are actively hostile.** As documented in `why-platforms-havent-built-this.md`, the incumbent platforms are cracking down on bots. Recall.ai-style reverse engineering is fragile and legally risky. Building a product on a foundation that can be broken by a platform update is not a viable business.

2. **Integration puts Convene in a permanent second-class position.** Bot users aren't real participants. They can be blocked, rate-limited, or de-listed. There's no path from "tolerated bot" to "first-class platform participant" without the platform's cooperation — which they will never grant.

3. **Integration doesn't differentiate.** If Convene's value proposition is "join Zoom meetings," then Convene is competing with Otter.ai and Fireflies.ai on commodity features (notes, summaries, task extraction). That's a race to the bottom on pricing with no durable moat.

4. **The use case doesn't exist on incumbent platforms.** Multi-agent meetings, agent-to-agent collaboration, personal agents with persistent memory joining recurring standups — none of this is possible via bot workarounds. The agent-native use case requires a purpose-built platform to exist at all.

---

## The "Force Platforms to Integrate" Playbook

The model is Slack vs. email, not Slack vs. Gmail:

- Slack didn't try to make email better. It built a different thing.
- Developers adopted Slack first because it was better for collaboration.
- Enterprises followed because their developers were already there.
- Eventually, Slack became the standard for team messaging — and email clients added Slack integrations, not the other way around.

Convene's version of this playbook:

1. Build the platform that agent developers actually want. Make it the best place in the world to build an agent that participates in meetings.
2. Get the first 1,000 developers. Each developer building an agent on Convene is a force multiplier: their agent needs Convene, which means anyone who wants to meet with that agent needs Convene.
3. Build critical mass in the developer community until Convene is the de facto standard for agent-native meetings.
4. Let traditional platforms come to Convene with integration requests, not the other way around.

This is "force platforms to integrate by becoming the standard" — the same move Slack made when Microsoft eventually built the Teams/Slack integration.

---

## Target Audience: AI-Pilled Developers First

Convene is not a mass-market product in Phase 1. Mass-market adoption requires the kind of inertia and switching cost that takes years to build. The go-to-market wedge is the developer community — specifically, developers building personal agents.

**Why developers:**
- They are underserved. No platform makes it easy to build a meeting-capable agent.
- They are force multipliers. One developer's agent can be the reason 10 other people use Convene.
- They have high tolerance for rough edges if the core value proposition is strong.
- They are the opinion leaders for the next wave of enterprise adoption.
- They will build the ecosystem. Third-party agent templates, integrations, and use cases built by the community are more powerful than any feature roadmap.

**The math:**
- 1,000 developers, each with an agent that joins 5 meetings/week = 5,000 agent-meetings/week
- Each agent-meeting involves at least one other human participant who now knows Convene exists
- 20% organic referral rate → 1,000 new users/week at scale
- No paid acquisition needed in Phase 1

**The business philosophy:**
Many niche committed bases are more durable than one large casual base. A developer who has built their agent on Convene is deeply committed. They don't churn when a competitor appears. They advocate for Convene internally. They build integrations. Contrast with a casual notetaker user who switches to whatever has the best AI summary this week.

First mover on agent-native meetings for the developer community is the foundation of a durable business.

---

## Revenue Model: Developer-First Pricing

**Guiding principle:** The free tier must be generous enough that developers build real projects on it. Charge for scale, not for access.

**Tier structure:**

| Tier | Price | Target | Key limits |
|------|-------|--------|-----------|
| **Free** | $0 | Individual developers, tinkerers | 10 agent-meetings/month, 1 concurrent agent, community support |
| **Developer** | $29/mo | Serious builders, small teams | 100 agent-meetings/month, 5 concurrent agents, API access |
| **Team** | $79/user/mo | Companies deploying agents at work | Unlimited meetings, custom agents, RBAC, Slack/Linear integrations |
| **Enterprise** | Custom | Self-hosted, SLA, compliance | On-prem option, data sovereignty, custom SLA, dedicated support |

**Usage-based components (Developer tier and above):**
- Agent-session minutes: $0.02/minute (marginal cost ~$0.008, healthy margin)
- Additional STT minutes: $0.005/minute (pass-through + margin on Deepgram $0.0043/min)
- Additional TTS characters: $0.00002/char (pass-through + margin on Cartesia)

**Why generous free tier:**
The cost of a developer using Convene for free to build an agent is low (they're not running meetings 24/7). The value of that developer becoming an advocate, writing blog posts, and building in public is high. Don't charge for the thing that creates advocates.

---

## Recommendation

Own the platform. Become the standard for agent-native meetings. Let traditional platforms come to Convene.

The market opportunity is real ($3.5B → $21.5B), the timing is right (personal agents are just emerging), the incumbent platforms have structural reasons not to build this, and the developer community is primed for a tool like Convene.

The strategy isn't to fight Zoom. It's to build the category that Zoom can't — and won't — build.
