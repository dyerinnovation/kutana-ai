# Managed Agents

Managed agents are pre-built AI agents available directly in the Kutana dashboard. No code, no configuration files -- select an agent, assign it to a meeting, and Kutana handles the rest.

Each managed agent is a Claude-powered AI that joins your meeting as a participant, monitors the conversation, and performs its specific role using the Kutana MCP tools.

## Available Agents

### Meeting Notetaker

Takes detailed notes during meetings and extracts action items automatically. Organizes notes by topic and posts structured updates to the meeting chat.

**Category:** Productivity
**Capabilities:** Transcription, task extraction, action items
**Best for:** Keeping meeting records organized, capturing action items with assignees

### Technical Scribe

Captures technical decisions, architecture discussions, and engineering context. Uses precise technical language and tracks code references and follow-up engineering tasks.

**Category:** Engineering
**Capabilities:** Transcription, task extraction, summarization
**Best for:** Engineering standups, architecture reviews, sprint planning, technical decision logging

### Standup Facilitator

Guides daily standups through each participant's update: what they did, what they plan to do, and any blockers. Tracks blockers and suggests follow-ups.

**Category:** Productivity
**Capabilities:** Transcription, task extraction, action items
**Best for:** Daily standups, team check-ins, blocker tracking

### Meeting Summarizer

Generates concise post-meeting summaries with key takeaways including attendees, discussion topics, decisions made, action items, and next steps.

**Category:** General
**Capabilities:** Transcription, summarization
**Best for:** Post-meeting recaps, keeping remote team members in the loop

## How to Activate

1. Go to **Agents** in the sidebar
2. Scroll to **Kutana Managed Agents**
3. Click **Activate Agent** on the agent you want
4. Select the meeting from the dropdown
5. Click **Activate** to confirm

The agent joins the meeting immediately and begins monitoring the transcript.

## How It Works

When activated, a managed agent:

1. **Joins the meeting** as a participant (visible in the participant list)
2. **Monitors the transcript** continuously using the Kutana MCP tools
3. **Performs its role** -- extracting tasks, taking notes, facilitating, or summarizing
4. **Posts updates** to the meeting chat with findings and insights
5. **Runs until the meeting ends** or you deactivate it

### Entity Extraction

Managed agents work alongside the always-on entity extraction pipeline. The extraction pipeline processes transcript in 3-minute windows and extracts:

- **Tasks** -- action items with assignees and priorities
- **Decisions** -- choices made with context and rationale
- **Questions** -- open questions raised during discussion
- **Key Points** -- significant discussion points
- **Blockers** -- impediments identified
- **Follow-ups** -- post-meeting actions needed

Agents can read these extracted entities using the `get_entity_history` and `get_meeting_recap` MCP tools.

## Deactivating

To stop a managed agent:

1. Go to **Agents** in the sidebar
2. Find the active session under your agents
3. Click **Deactivate**

The agent will leave the meeting and stop monitoring.

## See Also

- [Connecting Agents Overview](/docs/connecting-agents/overview) -- Custom vs managed agents
- [MCP Server Reference](/docs/connecting-agents/mcp-server) -- Available MCP tools for agents
