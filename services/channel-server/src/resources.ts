/**
 * MCP resource registrations for the Kutana AI Channel Server.
 *
 * Resources:
 *   - kutana://platform/context         — static platform context (Layer 1)
 *   - kutana://meeting/{id}             — meeting info + connection status
 *   - kutana://meeting/{id}/context     — detailed meeting context (Layer 2)
 *   - kutana://meeting/{id}/transcript  — buffered transcript segments
 *
 * The meetings resource template uses a `list` callback so clients can
 * browse available meetings. The list updates when meetings are joined
 * or left (via notifications/resources/list_changed).
 */

import type { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  ListResourcesRequestSchema,
  ListResourceTemplatesRequestSchema,
  ReadResourceRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import type { KutanaClient } from "./kutana-client.js";
import type { ChannelServerConfig } from "./config.js";

// ---------------------------------------------------------------------------
// Layer 1: Static platform context
// ---------------------------------------------------------------------------

export const PLATFORM_CONTEXT_DOC = `# Kutana AI — Platform Context

## What is Kutana AI?
Kutana AI is an agent-first meeting platform where AI agents connect as first-class
participants via a native WebSocket API. Humans join via browser (WebRTC); agents join
via the Agent Gateway. You are a live participant in an active meeting.

## Your Role
You are an AI agent participating in a Kutana AI meeting. You receive two streams:
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

### Meeting Lifecycle
| Tool | Purpose |
|------|---------|
| \`list_meetings\` | Browse available meetings |
| \`join_meeting\` | Join a meeting by ID |
| \`create_meeting\` | Create a new meeting |
| \`join_or_create_meeting\` | Find or create a meeting by title |
| \`leave_meeting\` | Leave the current meeting |

### In-Meeting
| Tool | Purpose | Key params |
|------|---------|------------|
| \`reply\` | Send a message to the meeting chat | \`text\` |
| \`accept_task\` | Claim a task you will handle | \`task_id\` |
| \`update_status\` | Report progress on an accepted task | \`task_id\`, \`status\`, \`message\` |
| \`raise_hand\` | Request a turn to speak | \`priority\`, \`topic\` |
| \`get_queue_status\` | Check the speaker queue | — |
| \`mark_finished_speaking\` | Release the floor | — |
| \`request_context\` | Search the transcript buffer | \`query\`, \`limit\` |
| \`get_meeting_recap\` | Full recap of extracted entities | — |

## Task Status Values
\`in_progress\` · \`completed\` · \`blocked\` · \`needs_review\`

## Behavior Guidelines
- Start by listing meetings or joining one
- Monitor the transcript and insight stream continuously once joined
- When you see a task you can handle, call \`accept_task\` to claim it
- Provide status updates via \`update_status\` as you work
- Use \`reply\` sparingly — only when you add clear value
- Search for context with \`request_context\` before making claims about past discussion
`;

// ---------------------------------------------------------------------------
// Registration
// ---------------------------------------------------------------------------

/** Register platform context and meeting resources on the MCP server. */
export function registerResources(
  server: Server,
  client: KutanaClient,
  config: ChannelServerConfig,
): void {
  // Static resources
  server.setRequestHandler(ListResourcesRequestSchema, async () => ({
    resources: [
      {
        uri: "kutana://platform/context",
        name: "Kutana AI Platform Context",
        description:
          "Platform context: what Kutana AI is, message formats, tools, and behaviour guidelines.",
        mimeType: "text/markdown",
      },
    ],
  }));

  // Resource templates — meetings are browsable via the list callback
  server.setRequestHandler(ListResourceTemplatesRequestSchema, async () => ({
    resourceTemplates: [
      {
        uriTemplate: "kutana://meeting/{meeting_id}",
        name: "Meeting",
        description:
          "Meeting info with connection status. Browse available meetings by listing this template.",
        mimeType: "application/json",
      },
      {
        uriTemplate: "kutana://meeting/{meeting_id}/context",
        name: "Meeting Context",
        description:
          "Dynamic context: connection status, agent mode, entity summary, and transcript preview.",
        mimeType: "text/markdown",
      },
      {
        uriTemplate: "kutana://meeting/{meeting_id}/transcript",
        name: "Meeting Transcript",
        description:
          "Session-scoped transcript segments received since joining the meeting.",
        mimeType: "application/json",
      },
    ],
  }));

  // Read handler for all resource URIs
  server.setRequestHandler(ReadResourceRequestSchema, async (request) => {
    const { uri } = request.params;

    // Static: platform context
    if (uri === "kutana://platform/context") {
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

    // Dynamic: meeting transcript
    const transcriptMatch =
      /^kutana:\/\/meeting\/([^/]+)\/transcript$/.exec(uri);
    if (transcriptMatch) {
      const meetingId = transcriptMatch[1] ?? "";
      if (client.getCurrentMeetingId() !== meetingId) {
        return {
          contents: [
            {
              uri,
              mimeType: "application/json",
              text: JSON.stringify({
                error: "Not connected to this meeting",
              }),
            },
          ],
        };
      }
      const segments = client.getRecentTranscript(9999);
      return {
        contents: [
          {
            uri,
            mimeType: "application/json",
            text: JSON.stringify(segments, null, 2),
          },
        ],
      };
    }

    // Dynamic: meeting context
    const contextMatch =
      /^kutana:\/\/meeting\/([^/]+)\/context$/.exec(uri);
    if (contextMatch) {
      const meetingId = contextMatch[1] ?? "";
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

    // Dynamic: meeting info
    const meetingMatch = /^kutana:\/\/meeting\/([^/]+)$/.exec(uri);
    if (meetingMatch) {
      const meetingId = meetingMatch[1] ?? "";
      const isConnected = client.getCurrentMeetingId() === meetingId;

      const info: Record<string, unknown> = {
        meeting_id: meetingId,
        connected: isConnected,
      };

      if (isConnected) {
        info["transcript_count"] = client.getRecentTranscript(9999).length;
        info["participants"] = client.getParticipants();
        info["entity_count"] = client.getEntities(undefined, 9999).length;
      }

      return {
        contents: [
          {
            uri,
            mimeType: "application/json",
            text: JSON.stringify(info, null, 2),
          },
        ],
      };
    }

    throw new Error(`Unknown resource URI: ${uri}`);
  });
}

/**
 * Send a resources/list_changed notification to inform Claude Code
 * that available resource state has changed (e.g. after join/leave).
 */
export async function notifyResourcesChanged(server: Server): Promise<void> {
  try {
    await server.notification({
      method: "notifications/resources/list_changed",
    });
  } catch {
    // Notification errors should not crash the server
  }
}

// ---------------------------------------------------------------------------
// Dynamic meeting context builder
// ---------------------------------------------------------------------------

function buildMeetingContext(
  meetingId: string,
  client: KutanaClient,
  config: ChannelServerConfig,
): string {
  const isCurrentMeeting = client.getCurrentMeetingId() === meetingId;
  const recentSegments = isCurrentMeeting
    ? client.getRecentTranscript(5)
    : [];

  const preview =
    recentSegments.length > 0
      ? recentSegments
          .map(
            (s) =>
              `- [${s.start_time.toFixed(1)}s] **${s.speaker ?? "Unknown"}**: ${s.text}`,
          )
          .join("\n")
      : "_No transcript segments buffered yet._";

  const entityCounts = isCurrentMeeting
    ? summariseEntities(client)
    : "_Not connected to this meeting._";

  const modeDescription =
    config.agentMode === "selective" && config.entityFilter.length > 0
      ? `selective (${config.entityFilter.join(", ")})`
      : config.agentMode;

  return `# Meeting Context

## Meeting ID
\`${meetingId}\`

## Connection Status
${isCurrentMeeting ? "Connected and listening" : "Not connected to this meeting"}

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

function summariseEntities(client: KutanaClient): string {
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
