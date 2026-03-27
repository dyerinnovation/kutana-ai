# Managed Agents

Managed agents are pre-built AI agents available directly in the Convene dashboard. No code, no configuration files — just select an agent, assign it to a meeting, and Convene handles the rest.

## Available Agents

### Meeting Summarizer

Produces rolling meeting summaries every 5 minutes during a meeting and a final comprehensive summary when the meeting ends.

**Category:** Summarization
**Produces:** Key discussion points, decisions made, overall meeting summary
**Best for:** Keeping remote team members in the loop, post-meeting recaps

### Action Item Tracker

Listens for commitments, assignments, and deadlines during the meeting and extracts them as structured tasks.

**Category:** Productivity
**Produces:** Task list with assignees, deadlines, and context
**Best for:** Ensuring nothing falls through the cracks after a meeting

### Decision Logger

Captures decisions as they are made during the meeting, including the context and rationale behind each decision.

**Category:** Documentation
**Produces:** Decision log with context, participants involved, and timestamps
**Best for:** Audit trails, onboarding new team members, revisiting past decisions

### Code Discussion Tracker

Extracts code-related topics, technical decisions, and references to specific files, functions, or systems discussed during the meeting.

**Category:** Engineering
**Produces:** Technical discussion summary, code references, architecture decisions
**Best for:** Engineering standups, architecture reviews, sprint planning

## How to Activate

1. Go to **Dashboard → Agents → Templates**
2. Browse the available managed agents
3. Click **Activate** on the agent you want
4. Choose which meetings it should join:
   - **All meetings** — the agent joins every meeting you create
   - **Tagged meetings** — the agent only joins meetings with a specific tag
   - **Manual** — you assign the agent to individual meetings
5. The agent is now active and will join meetings automatically

## API Key Requirements

| Tier | API Key | Cost |
|------|---------|------|
| Free | You provide your own Anthropic API key in Settings | Free |
| Pro / Business | Included with your plan | Included in subscription |
| Enterprise | Dedicated key management | Custom pricing |

## Output

Managed agent output appears in two places:

- **During the meeting**: Real-time output in the meeting sidebar under the agent's name
- **After the meeting**: Full output in the meeting recap page, organized by agent

## See Also

- [Connecting Agents Overview](/docs/connecting-agents/overview) — Custom vs managed agents
- [Custom Agents](/docs/connecting-agents/custom-agents/mcp-quickstart) — Build your own agent
