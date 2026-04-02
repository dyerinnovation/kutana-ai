/**
 * MCP tool registrations for the Kutana AI Channel Server.
 *
 * Tools are grouped into two categories:
 *
 * **Lobby tools** (work without an active meeting):
 *   list_meetings, join_meeting, create_meeting, join_or_create_meeting
 *
 * **Meeting tools** (require an active meeting — return an error otherwise):
 *   reply, get_chat_messages, accept_task, update_status, raise_hand,
 *   get_queue_status, mark_finished_speaking, cancel_hand_raise,
 *   get_speaking_status, get_participants, request_context,
 *   get_meeting_recap, get_entity_history, leave_meeting
 */

import type { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import type { KutanaClient } from "./kutana-client.js";
import type {
  BlockerEntity,
  DecisionEntity,
  EntityType,
  FollowUpEntity,
  KeyPointEntity,
  QuestionEntity,
  TaskEntity,
} from "./types.js";

/** Callback invoked when meeting state changes (join/leave) so the server can notify Claude. */
export type MeetingStateChangeCallback = () => Promise<void> | void;

/** Register all Kutana AI tools on the MCP server. */
export function registerTools(
  server: Server,
  client: KutanaClient,
  onMeetingStateChange?: MeetingStateChangeCallback,
): void {
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      // -----------------------------------------------------------------------
      // Meeting lifecycle (lobby tools — no active meeting required)
      // -----------------------------------------------------------------------
      {
        name: "list_meetings",
        description:
          "List available meetings. Returns meetings with their IDs, titles, and status.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      {
        name: "join_meeting",
        description:
          "Join a meeting by ID. Opens a WebSocket connection to the gateway and starts receiving real-time events (transcript, chat, speaker changes).",
        inputSchema: {
          type: "object",
          properties: {
            meeting_id: {
              type: "string",
              description: "UUID of the meeting to join.",
            },
            capabilities: {
              type: "array",
              items: { type: "string" },
              description:
                'Capabilities to request. Default: ["listen", "transcribe", "data_channel"].',
            },
          },
          required: ["meeting_id"],
        },
      },
      {
        name: "create_meeting",
        description:
          "Create a new meeting. Returns the meeting info including its ID.",
        inputSchema: {
          type: "object",
          properties: {
            title: {
              type: "string",
              description: "Title for the new meeting.",
            },
          },
          required: ["title"],
        },
      },
      {
        name: "join_or_create_meeting",
        description:
          "Find an active meeting by title and join it. If no matching active meeting exists, create one and join it.",
        inputSchema: {
          type: "object",
          properties: {
            title: {
              type: "string",
              description: "Title to search for or create.",
            },
            capabilities: {
              type: "array",
              items: { type: "string" },
              description:
                'Capabilities to request. Default: ["listen", "transcribe", "data_channel"].',
            },
          },
          required: ["title"],
        },
      },
      {
        name: "leave_meeting",
        description:
          "Leave the current meeting. Closes the WebSocket connection and clears all meeting state.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      // -----------------------------------------------------------------------
      // Chat & messaging (requires active meeting)
      // -----------------------------------------------------------------------
      {
        name: "reply",
        description:
          "Send a text message to the meeting chat. Use this to communicate with meeting participants.",
        inputSchema: {
          type: "object",
          properties: {
            text: {
              type: "string",
              description: "The message to send to the meeting chat.",
            },
          },
          required: ["text"],
        },
      },
      {
        name: "speak",
        description:
          "Speak text aloud in the meeting using TTS. The gateway synthesizes your text into audio and broadcasts it to all participants. Use this when you want participants to hear you speak rather than just reading a chat message.",
        inputSchema: {
          type: "object",
          properties: {
            text: {
              type: "string",
              description: "The text to speak aloud in the meeting.",
            },
          },
          required: ["text"],
        },
      },
      {
        name: "get_chat_messages",
        description:
          "Read recent chat messages from the meeting.",
        inputSchema: {
          type: "object",
          properties: {
            limit: {
              type: "number",
              description:
                "Maximum number of recent messages to return (default: 50).",
            },
          },
          required: [],
        },
      },
      // -----------------------------------------------------------------------
      // Task management (requires active meeting)
      // -----------------------------------------------------------------------
      {
        name: "accept_task",
        description:
          "Claim a task extracted from the meeting.",
        inputSchema: {
          type: "object",
          properties: {
            task_id: {
              type: "string",
              description: "The ID of the task to accept.",
            },
          },
          required: ["task_id"],
        },
      },
      {
        name: "update_status",
        description:
          "Push a progress update for a task this agent has accepted.",
        inputSchema: {
          type: "object",
          properties: {
            task_id: {
              type: "string",
              description: "The ID of the task being updated.",
            },
            status: {
              type: "string",
              enum: ["in_progress", "completed", "blocked", "needs_review"],
              description: "The new status of the task.",
            },
            message: {
              type: "string",
              description: "A human-readable status update message.",
            },
          },
          required: ["task_id", "status", "message"],
        },
      },
      // -----------------------------------------------------------------------
      // Turn management (requires active meeting)
      // -----------------------------------------------------------------------
      {
        name: "raise_hand",
        description:
          "Request a turn to speak. Adds you to the speaker queue.",
        inputSchema: {
          type: "object",
          properties: {
            priority: {
              type: "string",
              enum: ["normal", "urgent"],
              description:
                "Queue priority — normal (FIFO) or urgent (front of queue). Default: normal.",
            },
            topic: {
              type: "string",
              description:
                "Optional short description of what you want to discuss.",
            },
          },
          required: [],
        },
      },
      {
        name: "get_queue_status",
        description:
          "Get the current speaker queue status.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      {
        name: "mark_finished_speaking",
        description:
          "Signal that you have finished your speaking turn.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      {
        name: "cancel_hand_raise",
        description:
          "Withdraw from the speaker queue.",
        inputSchema: {
          type: "object",
          properties: {
            hand_raise_id: {
              type: "string",
              description: "Specific hand raise UUID to cancel (optional).",
            },
          },
          required: [],
        },
      },
      {
        name: "get_speaking_status",
        description:
          "Check your current speaking status: whether you are the active speaker or in the queue.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      // -----------------------------------------------------------------------
      // Participants (requires active meeting)
      // -----------------------------------------------------------------------
      {
        name: "get_participants",
        description:
          "List the current participants in the meeting.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      // -----------------------------------------------------------------------
      // Transcript & entity history (requires active meeting)
      // -----------------------------------------------------------------------
      {
        name: "request_context",
        description:
          "Search the meeting transcript buffer for segments relevant to a topic or question.",
        inputSchema: {
          type: "object",
          properties: {
            query: {
              type: "string",
              description:
                "The topic or keywords to search for in the transcript.",
            },
            limit: {
              type: "number",
              description:
                "Maximum number of matching segments to return (default: 10).",
            },
          },
          required: ["query"],
        },
      },
      {
        name: "get_meeting_recap",
        description:
          "Fetch the current meeting recap: tasks, decisions, key points, and open questions.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      {
        name: "get_entity_history",
        description:
          "Retrieve extracted entities of a specific type from this meeting session.",
        inputSchema: {
          type: "object",
          properties: {
            entity_type: {
              type: "string",
              enum: [
                "task",
                "decision",
                "question",
                "entity_mention",
                "key_point",
                "blocker",
                "follow_up",
              ],
              description: "The type of entities to retrieve.",
            },
            limit: {
              type: "number",
              description:
                "Maximum number of entities to return (default: 50).",
            },
          },
          required: ["entity_type"],
        },
      },
    ],
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    const safeArgs = args ?? {};

    switch (name) {
      // Lobby tools — no meeting required
      case "list_meetings":
        return handleListMeetings(client);
      case "join_meeting":
        return handleJoinMeeting(client, safeArgs, onMeetingStateChange);
      case "create_meeting":
        return handleCreateMeeting(client, safeArgs);
      case "join_or_create_meeting":
        return handleJoinOrCreateMeeting(client, safeArgs, onMeetingStateChange);
      case "leave_meeting":
        return handleLeaveMeeting(client, onMeetingStateChange);

      // Meeting tools — require active meeting
      case "reply": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleReply(client, safeArgs);
      }
      case "speak": {
        const g = requireMeeting(client);
        if (g) return g;
        const text = String(safeArgs.text ?? "");
        if (!text) {
          return { content: [{ type: "text", text: "Error: text is required." }], isError: true };
        }
        await client.speak(text);
        return { content: [{ type: "text", text: `Speaking: "${text.slice(0, 100)}${text.length > 100 ? "..." : ""}"` }] };
      }
      case "get_chat_messages": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleGetChatMessages(client, safeArgs);
      }
      case "accept_task": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleAcceptTask(client, safeArgs);
      }
      case "update_status": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleUpdateStatus(client, safeArgs);
      }
      case "raise_hand": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleRaiseHand(client, safeArgs);
      }
      case "get_queue_status": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleGetQueueStatus(client);
      }
      case "mark_finished_speaking": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleMarkFinishedSpeaking(client);
      }
      case "cancel_hand_raise": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleCancelHandRaise(client, safeArgs);
      }
      case "get_speaking_status": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleGetSpeakingStatus(client);
      }
      case "get_participants": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleGetParticipants(client);
      }
      case "request_context": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleRequestContext(client, safeArgs);
      }
      case "get_meeting_recap": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleGetMeetingRecap(client);
      }
      case "get_entity_history": {
        const g = requireMeeting(client);
        if (g) return g;
        return handleGetEntityHistory(client, safeArgs);
      }
      default:
        return error(`Unknown tool: ${name}`);
    }
  });
}

// ---------------------------------------------------------------------------
// Meeting guard
// ---------------------------------------------------------------------------

function requireMeeting(client: KutanaClient) {
  if (!client.getCurrentMeetingId()) {
    return error("Not in a meeting. Use join_meeting or join_or_create_meeting first.");
  }
  return null;
}

// ---------------------------------------------------------------------------
// Handler implementations — Meeting lifecycle
// ---------------------------------------------------------------------------

async function handleListMeetings(client: KutanaClient) {
  try {
    const meetings = await client.listMeetings();
    return ok(JSON.stringify(meetings, null, 2));
  } catch (err) {
    return error(String(err));
  }
}

async function handleJoinMeeting(
  client: KutanaClient,
  args: Record<string, unknown>,
  onMeetingStateChange?: MeetingStateChangeCallback,
) {
  const meetingId = args["meeting_id"];
  if (typeof meetingId !== "string" || !meetingId.trim()) {
    return error("meeting_id is required");
  }

  const capabilities = Array.isArray(args["capabilities"])
    ? (args["capabilities"] as string[])
    : undefined;

  try {
    await client.joinMeeting(meetingId, capabilities);
    if (onMeetingStateChange) await onMeetingStateChange();
    return ok(
      JSON.stringify({
        status: "joined",
        meeting_id: meetingId,
        note: "You are now receiving real-time events. Use reply to chat, raise_hand to speak.",
      }),
    );
  } catch (err) {
    return error(String(err));
  }
}

async function handleCreateMeeting(
  client: KutanaClient,
  args: Record<string, unknown>,
) {
  const title = args["title"];
  if (typeof title !== "string" || !title.trim()) {
    return error("title is required");
  }

  try {
    const meeting = await client.createMeeting(title);
    return ok(JSON.stringify(meeting, null, 2));
  } catch (err) {
    return error(String(err));
  }
}

async function handleJoinOrCreateMeeting(
  client: KutanaClient,
  args: Record<string, unknown>,
  onMeetingStateChange?: MeetingStateChangeCallback,
) {
  const title = args["title"];
  if (typeof title !== "string" || !title.trim()) {
    return error("title is required");
  }

  const capabilities = Array.isArray(args["capabilities"])
    ? (args["capabilities"] as string[])
    : undefined;

  try {
    // Look for an active meeting with a matching title
    const meetings = await client.listMeetings();
    const match = meetings.find(
      (m) =>
        m.title?.toLowerCase() === title.toLowerCase() &&
        (m.status === "active" || m.status === "scheduled"),
    );

    let meetingId: string;
    let action: string;

    if (match) {
      meetingId = match.id;
      action = "joined_existing";
    } else {
      const created = await client.createMeeting(title);
      meetingId = created.id;
      action = "created_and_joined";
    }

    await client.joinMeeting(meetingId, capabilities);
    if (onMeetingStateChange) await onMeetingStateChange();

    return ok(
      JSON.stringify({
        status: action,
        meeting_id: meetingId,
        title,
      }),
    );
  } catch (err) {
    return error(String(err));
  }
}

async function handleLeaveMeeting(
  client: KutanaClient,
  onMeetingStateChange?: MeetingStateChangeCallback,
) {
  const g = requireMeeting(client);
  if (g) return g;

  const meetingId = client.getCurrentMeetingId();
  await client.leaveMeeting();
  if (onMeetingStateChange) await onMeetingStateChange();

  return ok(
    JSON.stringify({
      status: "left",
      meeting_id: meetingId,
    }),
  );
}

// ---------------------------------------------------------------------------
// Handler implementations — Chat
// ---------------------------------------------------------------------------

async function handleReply(
  client: KutanaClient,
  args: Record<string, unknown>,
) {
  const text = args["text"];
  if (typeof text !== "string" || !text.trim()) {
    return error("text is required and must be a non-empty string");
  }

  await client.sendChatMessage(text);
  return ok(`Message sent: "${text}"`);
}

function handleGetChatMessages(
  client: KutanaClient,
  args: Record<string, unknown>,
) {
  const limit =
    typeof args["limit"] === "number" && args["limit"] > 0
      ? Math.floor(args["limit"])
      : 50;

  const messages = client.getChatMessages(limit);
  return ok(JSON.stringify(messages, null, 2));
}

// ---------------------------------------------------------------------------
// Handler implementations — Task management
// ---------------------------------------------------------------------------

async function handleAcceptTask(
  client: KutanaClient,
  args: Record<string, unknown>,
) {
  const taskId = args["task_id"];
  if (typeof taskId !== "string" || !taskId.trim()) {
    return error("task_id is required");
  }

  await client.acceptTask(taskId);
  return ok(JSON.stringify({ status: "accepted", task_id: taskId }));
}

async function handleUpdateStatus(
  client: KutanaClient,
  args: Record<string, unknown>,
) {
  const taskId = args["task_id"];
  const status = args["status"];
  const message = args["message"];

  if (
    typeof taskId !== "string" ||
    typeof status !== "string" ||
    typeof message !== "string"
  ) {
    return error("task_id, status, and message are all required strings");
  }

  await client.updateTaskStatus(taskId, status, message);
  return ok(
    JSON.stringify({
      status: "updated",
      task_id: taskId,
      new_status: status,
    }),
  );
}

// ---------------------------------------------------------------------------
// Handler implementations — Turn management
// ---------------------------------------------------------------------------

async function handleRaiseHand(
  client: KutanaClient,
  args: Record<string, unknown>,
) {
  const priority = args["priority"] === "urgent" ? "urgent" : "normal";
  const topic =
    typeof args["topic"] === "string" && args["topic"].trim()
      ? args["topic"]
      : undefined;

  await client.raiseHand(priority, topic);
  return ok(
    JSON.stringify({
      status: "hand_raised",
      priority,
      topic: topic ?? null,
      note: "Queue state will arrive via turn.queue.updated event. Call get_queue_status to check position.",
    }),
  );
}

async function handleGetQueueStatus(client: KutanaClient) {
  await client.requestQueueStatus();
  const status = client.getLastQueueStatus();
  if (status === null) {
    return ok(
      JSON.stringify({
        note: "Queue refresh sent to gateway. No cached state yet — try again in a moment.",
      }),
    );
  }
  return ok(JSON.stringify(status, null, 2));
}

async function handleMarkFinishedSpeaking(client: KutanaClient) {
  await client.finishedSpeaking();
  return ok(JSON.stringify({ status: "finished_speaking" }));
}

async function handleCancelHandRaise(
  client: KutanaClient,
  args: Record<string, unknown>,
) {
  const handRaiseId =
    typeof args["hand_raise_id"] === "string" && args["hand_raise_id"].trim()
      ? args["hand_raise_id"]
      : undefined;

  await client.lowerHand(handRaiseId);
  return ok(
    JSON.stringify({
      status: "hand_lowered",
      hand_raise_id: handRaiseId ?? null,
    }),
  );
}

function handleGetSpeakingStatus(client: KutanaClient) {
  const { isSpeaking, isInQueue } = client.getSpeakingStatus();
  const queueStatus = client.getLastQueueStatus();

  return ok(
    JSON.stringify(
      {
        is_speaking: isSpeaking,
        is_in_queue: isInQueue,
        last_known_queue: queueStatus,
      },
      null,
      2,
    ),
  );
}

// ---------------------------------------------------------------------------
// Handler implementations — Participants
// ---------------------------------------------------------------------------

function handleGetParticipants(client: KutanaClient) {
  const participants = client.getParticipants();
  return ok(JSON.stringify(participants, null, 2));
}

// ---------------------------------------------------------------------------
// Handler implementations — Transcript & entity history
// ---------------------------------------------------------------------------

function handleRequestContext(
  client: KutanaClient,
  args: Record<string, unknown>,
) {
  const query = args["query"];
  if (typeof query !== "string" || !query.trim()) {
    return error("query is required");
  }

  const limit =
    typeof args["limit"] === "number" && args["limit"] > 0
      ? Math.floor(args["limit"])
      : 10;

  const segments = client.getRecentTranscript(500);
  const queryLower = query.toLowerCase();
  const relevant = segments
    .filter((s) => s.text.toLowerCase().includes(queryLower))
    .slice(-limit);

  return ok(JSON.stringify(relevant, null, 2));
}

function handleGetMeetingRecap(client: KutanaClient) {
  const allEntities = client.getEntities(undefined, 1000);

  const tasks = allEntities
    .filter((e): e is TaskEntity => e.entity_type === "task")
    .map((e) => ({
      id: e.id,
      title: e.title,
      assignee: e.assignee,
      priority: e.priority,
      status: e.status,
    }));

  const decisions = allEntities
    .filter((e): e is DecisionEntity => e.entity_type === "decision")
    .map((e) => ({
      id: e.id,
      summary: e.summary,
      participants: e.participants,
    }));

  const keyPoints = allEntities
    .filter((e): e is KeyPointEntity => e.entity_type === "key_point")
    .map((e) => ({ id: e.id, summary: e.summary, importance: e.importance }));

  const openQuestions = allEntities
    .filter(
      (e): e is QuestionEntity =>
        e.entity_type === "question" && e.status === "open",
    )
    .map((e) => ({ id: e.id, text: e.text, asker: e.asker }));

  const blockers = allEntities
    .filter((e): e is BlockerEntity => e.entity_type === "blocker")
    .map((e) => ({
      id: e.id,
      description: e.description,
      severity: e.severity,
    }));

  const followUps = allEntities
    .filter((e): e is FollowUpEntity => e.entity_type === "follow_up")
    .map((e) => ({ id: e.id, description: e.description, owner: e.owner }));

  const recap = {
    summary: {
      total_entities: allEntities.length,
      task_count: tasks.length,
      decision_count: decisions.length,
      open_question_count: openQuestions.length,
      blocker_count: blockers.length,
    },
    tasks,
    decisions,
    key_points: keyPoints,
    open_questions: openQuestions,
    blockers,
    follow_ups: followUps,
  };

  return ok(JSON.stringify(recap, null, 2));
}

function handleGetEntityHistory(
  client: KutanaClient,
  args: Record<string, unknown>,
) {
  const entityType = args["entity_type"];
  if (typeof entityType !== "string" || !entityType.trim()) {
    return error("entity_type is required");
  }

  const limit =
    typeof args["limit"] === "number" && args["limit"] > 0
      ? Math.floor(args["limit"])
      : 50;

  const entities = client.getEntities(entityType as EntityType, limit);
  return ok(JSON.stringify(entities, null, 2));
}

// ---------------------------------------------------------------------------
// Response helpers
// ---------------------------------------------------------------------------

function ok(text: string) {
  return { content: [{ type: "text" as const, text }] };
}

function error(message: string) {
  return {
    content: [{ type: "text" as const, text: `Error: ${message}` }],
    isError: true,
  };
}
