# External Doc Page Templates

Page templates for each type of page in `docs/external/`. Every template is
a starting point — fill it with real content. Delete any section that does not
apply to the specific page.

---

## Template: overview.md

The platform overview is the entry point for every new reader. It must explain
what Kutana is, who it is for, and where to go next. Keep it concise.

```markdown
# Kutana AI

Kutana AI is an agent-first meeting platform. AI agents connect via MCP and
participate as first-class meeting members — not bots bolted on the side.
Humans join via browser. Agents listen for commitments, extract tasks, and
maintain persistent memory across meetings.

## Who This Is For

- **Meeting participants** — join a meeting, see real-time transcription and tasks
- **Agent developers** — connect an AI agent via MCP to listen, speak, and act
- **Developers** — build on the Kutana REST API and WebSocket protocol

## Core Concepts

| Concept | Description | Learn more |
|---|---|---|
| Meetings | Time-bounded sessions with audio, transcription, and tasks | [Meetings](concepts/meetings.md) |
| Agents | AI participants that connect via MCP | [Agents](concepts/agents.md) |
| Tasks | Commitments extracted from conversation | [Tasks](concepts/tasks.md) |
| Memory | Persistent context across sessions | [Memory](concepts/memory.md) |

## Quick Start

- **Humans:** [Join a meeting in the browser](getting-started/quickstart-human.md)
- **Agents:** [Connect via MCP in 5 minutes](getting-started/quickstart-agent.md)

## Platform Reference

- [Features](features/) — transcription, task extraction, turn management, voice
- [Agents](agents/) — MCP connection, capabilities, prebuilt templates
- [API Reference](api-reference/) — REST endpoints, WebSocket protocol, auth
- [Integrations](integrations/) — Claude Agent SDK, OpenClaw, CLI
- [Examples](examples/) — complete working agents
```

---

## Template: Feature Page

Use for `docs/external/features/<name>.md`.

```markdown
# <Feature Name>

One-sentence description of what this feature does and why it matters.

## Overview

2–3 sentences explaining the feature in plain language. What problem does it
solve? What does the user experience? What triggers it?

## How It Works

Step-by-step explanation of the feature's behavior. Include timing, triggering
conditions, and any limitations.

1. **Step one** — what happens first
2. **Step two** — what happens next
3. **Output** — what the user/agent receives

## Example

Show a real, complete example. Use actual parameter values, not placeholders.

\`\`\`python
# Example: connecting and receiving task extraction output
import asyncio
from claude_agent_sdk import ClaudeAgent

async def main():
    agent = ClaudeAgent(
        mcp_url="https://kutana.example.com/mcp",
        api_key="cvn_live_abc123",
    )
    async with agent.meeting("quarterly-review") as meeting:
        async for event in meeting.events():
            if event.type == "task_extracted":
                print(f"Task: {event.task.description}")
                print(f"  Assignee: {event.task.assignee}")
                print(f"  Due: {event.task.due_date}")

asyncio.run(main())
\`\`\`

Expected output:
\`\`\`
Task: Update the roadmap with Q2 priorities
  Assignee: sarah@example.com
  Due: 2026-04-01
\`\`\`

## Configuration

| Parameter | Type | Default | Description |
|---|---|---|---|
| `extraction_model` | `string` | `haiku` | LLM model for extraction (`haiku`, `sonnet`) |
| `confidence_threshold` | `float` | `0.7` | Minimum confidence to surface a task |

## Limitations

- Extraction runs on transcript segments, not real-time audio
- Confidence threshold applies per-segment; edge cases at segment boundaries
- Maximum 500 tasks per meeting

## Related

- [Task Extraction](task-extraction.md)
- [Tasks concept](../concepts/tasks.md)
- [Task API reference](../api-reference/tasks.md)
```

---

## Template: Concept Page

Use for `docs/external/concepts/<name>.md`.

```markdown
# <Concept Name>

Define the concept in one sentence.

## What It Is

Explain the concept in 2–4 sentences. What does it represent? How does it
relate to the rest of the platform?

## Lifecycle / States

If the concept has states or a lifecycle, show it:

```
created → active → ended → archived
```

| State | Description |
|---|---|
| `created` | Meeting scheduled but not started |
| `active` | Meeting in progress, audio streaming |
| `ended` | Meeting finished, tasks persisted |
| `archived` | Transcript and tasks stored long-term |
\`\`\`

## Key Properties

| Property | Type | Description |
|---|---|---|
| `id` | `UUID` | Unique identifier |
| `title` | `string` | Human-readable name |
| `status` | `enum` | One of `created`, `active`, `ended`, `archived` |

## Working With <Concept>

Show how to interact with the concept via the API or MCP tools:

\`\`\`python
# Create a meeting via MCP
result = await kutana.create_meeting(
    title="Weekly Standup",
    scheduled_at="2026-04-01T09:00:00Z",
)
print(result.meeting_id)  # "mtg_01HXN..."
\`\`\`

## Related

- [Meetings API](../api-reference/meetings.md)
- [Getting started: join a meeting](../getting-started/quickstart-human.md)
```

---

## Template: API Reference Page

Use for `docs/external/api-reference/<resource>.md`.

```markdown
# <Resource> API

Base URL: `https://kutana.example.com/api/v1`

Authentication: `Authorization: Bearer <token>` — see [Authentication](overview.md#authentication).

---

## List <Resources>

`GET /meetings`

Returns a paginated list of meetings the authenticated user has access to.

**Query parameters**

| Parameter | Type | Required | Description |
|---|---|---|---|
| `status` | `string` | No | Filter by status: `active`, `ended`, `archived` |
| `limit` | `integer` | No | Results per page (default: 20, max: 100) |
| `cursor` | `string` | No | Pagination cursor from previous response |

**Example request**

\`\`\`bash
curl https://kutana.example.com/api/v1/meetings \
  -H "Authorization: Bearer cvn_live_abc123" \
  -G --data-urlencode "status=active"
\`\`\`

**Example response**

\`\`\`json
{
  "data": [
    {
      "id": "mtg_01HXN4B7KXYZ",
      "title": "Weekly Standup",
      "status": "active",
      "started_at": "2026-04-01T09:00:00Z",
      "participant_count": 4
    }
  ],
  "has_more": false,
  "next_cursor": null
}
\`\`\`

---

## Get a <Resource>

`GET /meetings/{meeting_id}`

**Path parameters**

| Parameter | Type | Description |
|---|---|---|
| `meeting_id` | `string` | The meeting ID |

**Example request**

\`\`\`bash
curl https://kutana.example.com/api/v1/meetings/mtg_01HXN4B7KXYZ \
  -H "Authorization: Bearer cvn_live_abc123"
\`\`\`

**Example response**

\`\`\`json
{
  "id": "mtg_01HXN4B7KXYZ",
  "title": "Weekly Standup",
  "status": "active",
  "started_at": "2026-04-01T09:00:00Z",
  "ended_at": null,
  "participants": [
    { "id": "usr_abc", "name": "Sarah Chen", "role": "host" },
    { "id": "agt_xyz", "name": "ActionBot", "role": "agent" }
  ]
}
\`\`\`

**Error responses**

| Status | Code | Description |
|---|---|---|
| `404` | `meeting_not_found` | No meeting with this ID |
| `403` | `access_denied` | User does not have access to this meeting |

---

## Create a <Resource>

`POST /meetings`

[Continue same pattern for create/update/delete endpoints]
```

---

## Template: Integration Page

Use for `docs/external/integrations/<name>.md`.

```markdown
# <Integration Name>

One line: what this integration is and why you'd use it.

## Prerequisites

- Kutana account with API access
- [Any other requirement with a link]

## Installation

\`\`\`bash
pip install claude-agent-sdk
\`\`\`

## Configuration

\`\`\`python
# ~/.kutana/config.json  or  environment variable
CONVENE_API_KEY=cvn_live_abc123
CONVENE_MCP_URL=https://kutana.example.com/mcp
\`\`\`

## Quickstart

A complete end-to-end example from zero to working integration:

\`\`\`python
import asyncio
from claude_agent_sdk import ClaudeAgent, MCPServerConfig

mcp_config = MCPServerConfig(
    url="https://kutana.example.com/mcp",
    headers={"Authorization": "Bearer cvn_live_abc123"},
)

agent = ClaudeAgent(mcp_servers=[mcp_config])

async def main():
    result = await agent.run(
        "Join the standup meeting and extract all action items"
    )
    print(result)

asyncio.run(main())
\`\`\`

## Available Tools

| Tool | Description |
|---|---|
| `list_meetings` | List available meetings |
| `join_meeting` | Join a meeting with specified capabilities |
| `get_transcript` | Retrieve recent transcript segments |
| `create_task` | Create a task from a detected commitment |

Full tool reference: [MCP Connection](../agents/mcp-connection.md)

## Next Steps

- [Agent templates](../agents/templates.md) — prebuilt agent configurations
- [Full examples](../examples/meeting-assistant.md) — complete working agent
```

---

## Template: Example Page

Use for `docs/external/examples/<name>.md`.

```markdown
# Example: <Name>

What this example demonstrates and when you'd use it.

## What You'll Build

Describe the finished agent/integration in 2–3 sentences. What does it do?
What events does it respond to? What does it output?

## Complete Source

\`\`\`python
# examples/action-tracker/main.py
# Full, runnable example — copy this file and set CONVENE_API_KEY

import asyncio
import os
from claude_agent_sdk import ClaudeAgent, MCPServerConfig

API_KEY = os.environ["CONVENE_API_KEY"]

mcp = MCPServerConfig(
    url="https://kutana.example.com/mcp",
    headers={"Authorization": f"Bearer {API_KEY}"},
)

SYSTEM_PROMPT = """You are an action tracker. When you detect a commitment or
task in the meeting transcript, extract it and call create_task immediately.
Assignee should be inferred from context. If unclear, leave it unassigned."""

async def main():
    agent = ClaudeAgent(
        mcp_servers=[mcp],
        system_prompt=SYSTEM_PROMPT,
        model="claude-haiku-4-5-20251001",
    )
    await agent.run(
        "Join the active meeting and track all action items until it ends."
    )

if __name__ == "__main__":
    asyncio.run(main())
\`\`\`

## How It Works

Walk through the key lines of the example with annotations:

1. **Line 12–15** — Configure MCP server with Bearer token auth
2. **Line 17–21** — System prompt constrains agent behavior to task extraction
3. **Line 23–26** — Agent joins the active meeting and runs until it ends

## Running It

\`\`\`bash
export CONVENE_API_KEY=cvn_live_abc123
python main.py
\`\`\`

Expected output:
\`\`\`
[09:04:12] Joined meeting: Weekly Standup
[09:06:33] Task created: "Update roadmap" → sarah@example.com (by 2026-04-01)
[09:11:15] Task created: "Schedule infra review" → ops team (unscheduled)
[09:30:00] Meeting ended. 3 tasks extracted.
\`\`\`

## Variations

- **Add Slack notifications** — call the Slack API inside the task creation callback
- **Filter by confidence** — only surface tasks above `confidence=0.85`
- **Multiple meetings** — run multiple agent instances in parallel

## Related

- [Task Extraction feature](../features/task-extraction.md)
- [Claude Agent SDK integration](../integrations/claude-agent-sdk.md)
- [Tasks API](../api-reference/tasks.md)
```
