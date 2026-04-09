# Managed Agents

Managed agents are pre-built AI agents available directly in the Kutana dashboard. No code, no configuration files — just select an agent, assign it to a meeting, and Kutana handles the rest.

## Available Agents

### Basic Tier

These agents are included with all plans.

#### Meeting Notetaker

Captures detailed, timestamped notes throughout the meeting, organized by topic with speaker attribution.

**Category:** Productivity
**Produces:** Chronological meeting notes with speaker attribution, topic headers, and inline action callouts
**Best for:** Teams who need a complete record of what was discussed

#### Meeting Summarizer

Produces rolling meeting summaries every 5 minutes during a meeting and a final comprehensive summary when the meeting ends.

**Category:** Summarization
**Produces:** Key discussion points, decisions made, action items, overall meeting summary
**Best for:** Keeping remote team members in the loop, post-meeting recaps

---

### Pro Tier

These agents require a Pro plan or higher.

#### Action Item Tracker

Listens for commitments, assignments, and deadlines during the meeting and extracts them as structured tasks in real time.

**Category:** Productivity
**Produces:** Task list with assignees, deadlines, priority levels, and context
**Best for:** Ensuring nothing falls through the cracks after a meeting

#### Decision Logger

Captures decisions as they are made during the meeting, including the context, rationale, alternatives considered, and stakeholders involved.

**Category:** Documentation
**Produces:** Decision log with context, participants involved, and timestamps
**Best for:** Audit trails, onboarding new team members, revisiting past decisions

#### Standup Facilitator

Actively guides daily standup meetings — prompts each participant for their update, tracks blockers, and keeps the meeting within the time box.

**Category:** Productivity
**Produces:** Structured standup summary table (Yesterday / Today / Blockers per person), blocker follow-ups
**Best for:** Teams who want consistent, time-boxed standups without a human facilitator

#### Code Discussion Tracker

Extracts code-related topics, technical decisions, and references to specific files, functions, or systems discussed during the meeting.

**Category:** Engineering
**Produces:** Technical discussion digest with code references, architecture decisions, and technical debt items
**Best for:** Engineering standups, architecture reviews, sprint planning

---

### Business Tier

These agents require a Business plan. Business-tier agents can be customized with organizational SOPs (Standard Operating Procedures) that are prepended to their instructions at activation time.

#### Sprint Retro Coach

Facilitates sprint retrospective meetings using structured frameworks (Start/Stop/Continue, 4Ls, Mad/Sad/Glad). Guides the team through each phase, collects feedback, and helps commit to improvement actions.

**Category:** Engineering
**Produces:** Categorized retro feedback (Start/Stop/Continue), themed patterns, committed improvement actions
**Best for:** Scrum teams who want consistent, well-facilitated retrospectives

#### Sprint Planner

Assists with sprint planning by guiding backlog review, facilitating estimation, tracking capacity, and building a coherent sprint plan with committed items.

**Category:** Engineering
**Produces:** Sprint plan with goal, estimated items, owners, capacity summary, and risk flags
**Best for:** Teams who want structured sprint planning with real-time tracking

#### User Interviewer

Conducts structured user research interviews — asks open-ended questions, probes for deeper insights, captures verbatim quotes, and produces a structured interview report.

**Category:** Research
**Produces:** Interview report with key findings, pain points, opportunities, and notable quotes
**Best for:** Product teams conducting user research at scale

#### Initial Interviewer

Conducts structured initial candidate interviews with consistent evaluation criteria. Tracks responses, captures communication quality indicators, and produces a structured scorecard.

**Category:** HR
**Produces:** Candidate scorecard with question-by-question evaluation and overall assessment
**Best for:** Standardizing initial candidate screens across interviewers

## How to Activate

1. Go to **Dashboard → Agents → Templates**
2. Browse the available managed agents
3. Click **Activate** on the agent you want
4. Choose which meetings it should join:
   - **All meetings** — the agent joins every meeting you create
   - **Tagged meetings** — the agent only joins meetings with a specific tag
   - **Manual** — you assign the agent to individual meetings
5. The agent is now active and will join meetings automatically

## Tier Requirements

| Tier | Agents Included | SOP Customization |
|------|----------------|-------------------|
| Basic | Meeting Notetaker, Meeting Summarizer | No |
| Pro | All Basic agents + Action Item Tracker, Decision Logger, Standup Facilitator, Code Discussion Tracker | No |
| Business | All Pro agents + Sprint Retro Coach, Sprint Planner, User Interviewer, Initial Interviewer | Yes |
| Enterprise | All Business agents + custom agent development | Yes |

## Output

Managed agent output appears in two places:

- **During the meeting**: Real-time output in the meeting sidebar under the agent's name
- **After the meeting**: Full output in the meeting recap page, organized by agent

## See Also

- [Connecting Agents Overview](/docs/connecting-agents/overview) — Custom vs managed agents
- [Custom Agents](/docs/connecting-agents/custom-agents/mcp-quickstart) — Build your own agent
