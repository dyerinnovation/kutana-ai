/**
 * MCP resource registrations for the Convene AI Channel Server.
 *
 * Resources implement Layer 1 (platform context) and Layer 2 (meeting context)
 * of the three-layer agent context seeding architecture described in
 * docs/technical/agent-context-seeding.md.
 */

import type { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  ListResourcesRequestSchema,
  ListResourceTemplatesRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import type { ConveneClient } from "./convene-client.js";
import type { ChannelServerConfig } from "./config.js";

// ---------------------------------------------------------------------------
// Layer 1: Static platform context
// ---------------------------------------------------------------------------

export const PLATFORM_CONTEXT_DOC = `# Convene AI — Platform Context

## What is Convene AI?
Convene AI is an agent-first meeting platform where AI agents connect as first-class
participants via a native WebSocket API. Humans join via browser (WebRTC); agents join
via the Agent Gateway. You are a live participant in an active meeting.

## Your Role
You are an AI agent participating in a Convene AI meeting. You receive two streams:
- **Transcript segments** — real-time speech-to-text from meeting participants
- **Meeting insights** — structured entities extracted from the conversation

Act as an attentive, helpful participant: listen, identify tasks you can handle, communicate
clearly, and report your progress.

## Message Formats

### Transcript Segment
\`\`\`xml
<transcript>[2.0s-4.5s] Alice Chen: We need to deploy the auth fix by Friday.</transcript>
\`\`\`

### Meeting Insight
\`\`\`xml
<insight type="task">
{
  "id": "...",
  "title": "Deploy auth fix",
  "assignee": null,
  "priority": "high",
  "status": "identified",
  "deadline": "Friday"
}
</insight>
\`\`\`

Insight types: **task**, **decision**, **question**, **entity_mention**, **key_point**,
**blocker**, **follow_up**.

## Available Tools

| Tool | Purpose | Key params |
|------|---------|------------|
| \`reply\` | Send a message to the meeting chat | \`text\` |
| \`accept_task\` | Claim a task you will handle | \`task_id\` |
| \`update_status\` | Report progress on an accepted task | \`task_id\`, \`status\`, \`message\` |
| \`request_context\` | Keyword search over the transcript buffer | \`query\`, \`limit\` |
| \`get_meeting_recap\` | Full recap: tasks, decisions, open questions | — |
| \`get_entity_history\` | All extracted entities of a type | \`entity_type\`, \`limit\` |

## Task Status Values
\`in_progress\` · \`completed\` · \`blocked\` · \`needs_review\`

## Behavior Guidelines
- Monitor the transcript and insight stream continuously
- When you see a task you can handle, call \`accept_task\` to claim it
- Provide status updates via \`update_status\` as you work
- Use \`reply\` sparingly — only when you add clear value
- Search for context with \`request_context\` before making claims about past discussion
- Use \`get_meeting_recap\` if you join late or need a full picture
`;

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

/** Register platform context and meeting context resources on the MCP server. */
export function registerResources(
  server: Server,
  client: ConveneClient,
  config: ChannelServerConfig,
): void {
  // Static resource list
  server.setRequestHandler(ListResourcesRequestSchema, async () => ({
    resources: [
      {
        uri: "convene://platform/context",
        name: "Convene AI Platform Context",
        description:
          "Static platform context: what Convene AI is, message formats, tools, and behaviour guidelines.",
        mimeType: "text/markdown",
      },
    ],
  }));

  // Resource template for dynamic meeting context
  server.setRequestHandler(ListResourceTemplatesRequestSchema, async () => ({
    resourceTemplates: [
      {
        uriTemplate: "convene://meeting/{meeting_id}/context",
        name: "Meeting Context",
        description:
          "Dynamic context for a specific meeting: connection status, agent mode, and a recent transcript preview.",
        mimeType: "text/markdown",
      },
    ],
  }));

  // Read handler for both the static resource and the template instances
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params;

    if (uri === "convene://platform/context") {
      return {
        contents: [
          {
            uri,
            mimeType: "text/markdown",
            text: PLATFORM_CONTEXT_DOC,
          },
        ],
      };
    }

    const meetingMatch = /^convene:\/\/meeting\/([^/]+)\/context$/.exec(uri);
    if (meetingMatch) {
      const meetingId = meetingMatch[1] ?? "";
      return {
        contents: [
          {
            uri,
            mimeType: "text/markdown",
            text: buildMeetingContext(meetingId, client, config),
          },
        ],
      };
    }

    throw new Error(`Unknown resource URI: ${uri}`);
  });
}

// ---------------------------------------------------------------------------
// Dynamic meeting context builder
// ---------------------------------------------------------------------------

function buildMeetingContext(
  meetingId: string,
  client: ConveneClient,
  config: ChannelServerConfig,
): string {
  const connected = client.isConnected();
  const recentSegments = client.getRecentTranscript(5);

  const preview =
    recentSegments.length > 0
      ? recentSegments
          .map(
            (s) =>
              `- [${s.start_time.toFixed(1)}s] **${s.speaker ?? "Unknown"}**: ${s.text}`,
          )
          .join("\n")
      : "_No transcript segments buffered yet._";

  const entityCounts = summariseEntities(client);

  const modeDescription =
    config.agentMode === "selective" && config.entityFilter.length > 0
      ? `selective (${config.entityFilter.join(", ")})`
      : config.agentMode;

  return `# Meeting Context

## Meeting ID
\`${meetingId}\`

## Connection Status
${connected ? "✓ Connected and listening" : "✗ Not connected to gateway"}

## Agent Mode
${modeDescription}

## Entity Buffer Summary
${entityCounts}

## Recent Transcript Preview
${preview}

---
_This resource is generated dynamically from the in-process buffer. Use \`get_meeting_recap\` for a structured summary of all extracted entities._
`;
}

function summariseEntities(client: ConveneClient): string {
  const types = [
    "task",
    "decision",
    "question",
    "key_point",
    "blocker",
    "follow_up",
    "entity_mention",
  ] as const;

  const rows = types.map((t) => {
    const count = client.getEntities(t, 9999).length;
    return `- **${t}**: ${count.toString()}`;
  });

  return rows.join("\n");
}
