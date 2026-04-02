# Feeds

Feeds are bidirectional integrations that connect your Kutana meetings to external platforms. Push meeting summaries to Slack, pull context from Notion, or deliver recaps to Discord — all automatically.

## How it works

When a meeting ends (or starts), Kutana automatically runs your configured Feeds. Each Feed is a short-lived AI agent that reads meeting data and delivers it to your chosen platform — or pulls external context into the meeting before it begins.

**Outbound (push):** After a meeting ends, a Feed agent reads the summary, tasks, and transcript, then posts a formatted recap to your Slack channel, Discord server, or other destination.

**Inbound (pull):** Before a meeting starts, a Feed agent fetches relevant context — a linked Slack thread, a Notion page, a GitHub issue — and injects it into the meeting so participants have background before the conversation begins.

**Bidirectional:** A single Feed can do both — pull context in at meeting start and push results out at meeting end.

## Supported platforms

| Platform | Status | Delivery type |
|----------|--------|---------------|
| Slack | Available | MCP Server |
| Discord | Coming Soon | Channel |
| Notion | Planned | MCP Server |
| GitHub | Planned | MCP Server |

## Getting started

1. Go to **Feeds** in the sidebar
2. Click **Configure** on a supported platform (e.g., Slack)
3. Fill in the configuration:
   - **Name** — A label for this feed (e.g., "Post-meeting recap to #general")
   - **Platform** — Select your target platform
   - **Delivery type** — MCP Server (provide server URL + auth token) or Channel
   - **Data types** — Choose what to deliver: Summary, Tasks, Transcript, Decisions
   - **Trigger** — When to run: After meeting ends, when a participant leaves, or manually
   - **Tag filter** (optional) — Only trigger for meetings with a specific tag
4. Click **Save Feed**

## What gets delivered

| Data type | Description |
|-----------|-------------|
| Summary | Key discussion points, decisions, and meeting overview |
| Tasks | Action items with assignees and deadlines |
| Transcript | Full or condensed meeting transcript |
| Decisions | Decisions made during the meeting with context |

## Triggers

| Trigger | When it runs |
|---------|-------------|
| After meeting ends | Automatically when the meeting is ended by the host |
| When participant leaves | When any participant disconnects |
| Manually | Only when you click "Run Now" from the Feeds page |

## Feed runs

Every Feed execution is tracked. From the Feeds page, you can:

- View run history for each Feed
- See delivery status (pending, running, delivered, failed)
- Check error messages for failed deliveries
- Manually re-trigger a failed delivery

## Security

Feed credentials (MCP auth tokens) are encrypted at rest and never returned in API responses. You'll see a token hint (last 4 characters) to confirm which credential is stored. Tokens are deleted immediately when you remove a Feed.
