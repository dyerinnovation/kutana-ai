/**
 * MCP tool registrations for the Convene AI Channel Server.
 *
 * Tools enable two-way communication: Claude can send messages, claim tasks,
 * report progress, search the transcript buffer, and query entity history.
 *
 * Turn management tools (raise_hand, get_queue_status, mark_finished_speaking,
 * cancel_hand_raise, get_speaking_status) send native WebSocket messages to the
 * agent gateway and return the latest cached state.
 *
 * Chat tools (get_chat_messages) read from the in-process buffer populated by
 * inbound data.channel.chat gateway events.
 *
 * Participant tools (get_participants) return the current participant list with
 * the Claude Code session annotated as source: "claude-code".
 */

import type { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import type { ConveneClient } from "./convene-client.js";
import type {
  BlockerEntity,
  DecisionEntity,
  EntityType,
  FollowUpEntity,
  KeyPointEntity,
  QuestionEntity,
  TaskEntity,
} from "./types.js";

/** Register all Convene AI tools on the MCP server. */
export function registerTools(server: Server, client: ConveneClient): void {
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      // -----------------------------------------------------------------------
      // Chat & messaging
      // -----------------------------------------------------------------------
      {
        name: "reply",
        description:
          "Send a text message to the meeting chat. Use this to communicate with meeting participants when you have something meaningful to contribute.",
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
        name: "get_chat_messages",
        description:
          "Read recent chat messages from the meeting. Use this to catch up on the chat history or check what others have said.",
        inputSchema: {
          type: "object",
          properties: {
            limit: {
              type: "number",
              description: "Maximum number of recent messages to return (default: 50).",
            },
          },
          required: [],
        },
      },
      // -----------------------------------------------------------------------
      // Task management
      // -----------------------------------------------------------------------
      {
        name: "accept_task",
        description:
          "Claim a task extracted from the meeting, indicating this agent will handle it. Call this when you see a task assigned to you or matching your capabilities.",
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
          "Push a progress update for a task this agent has accepted. Call this whenever your status changes.",
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
      // Turn management
      // -----------------------------------------------------------------------
      {
        name: "raise_hand",
        description:
          "Request a turn to speak in the meeting. Adds you to the speaker queue. If no one is currently speaking, you become the active speaker immediately (queue_position = 0).",
        inputSchema: {
          type: "object",
          properties: {
            priority: {
              type: "string",
              enum: ["normal", "urgent"],
              description: "Queue priority — normal (FIFO) or urgent (front of queue). Default: normal.",
            },
            topic: {
              type: "string",
              description: "Optional short description of what you want to discuss.",
            },
          },
          required: [],
        },
      },
      {
        name: "get_queue_status",
        description:
          "Get the current speaker queue status. Shows who is speaking, who is waiting, and queue positions. Triggers a queue refresh from the gateway.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      {
        name: "mark_finished_speaking",
        description:
          "Signal that you have finished your speaking turn, advancing the queue to the next participant.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      {
        name: "cancel_hand_raise",
        description:
          "Withdraw from the speaker queue (lower your hand). If hand_raise_id is provided, cancels that specific raise; otherwise cancels your current hand raise.",
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
          "Check your current speaking status: whether you are the active speaker, in the queue, and the latest queue snapshot.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      // -----------------------------------------------------------------------
      // Participants
      // -----------------------------------------------------------------------
      {
        name: "get_participants",
        description:
          "List the current participants in the meeting. Your own session is annotated with source: 'claude-code'.",
        inputSchema: {
          type: "object",
          properties: {},
          required: [],
        },
      },
      // -----------------------------------------------------------------------
      // Transcript & entity history
      // -----------------------------------------------------------------------
      {
        name: "request_context",
        description:
          "Search the meeting transcript buffer for segments relevant to a topic or question. Use this before answering questions to ensure accuracy.",
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
          "Fetch the current meeting recap built from all extracted entities: tasks, decisions, key points, and open questions.",
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
      case "reply":
        return handleReply(client, safeArgs);
      case "get_chat_messages":
        return handleGetChatMessages(client, safeArgs);
      case "accept_task":
        return handleAcceptTask(client, safeArgs);
      case "update_status":
        return handleUpdateStatus(client, safeArgs);
      case "raise_hand":
        return handleRaiseHand(client, safeArgs);
      case "get_queue_status":
        return handleGetQueueStatus(client);
      case "mark_finished_speaking":
        return handleMarkFinishedSpeaking(client);
      case "cancel_hand_raise":
        return handleCancelHandRaise(client, safeArgs);
      case "get_speaking_status":
        return handleGetSpeakingStatus(client);
      case "get_participants":
        return handleGetParticipants(client);
      case "request_context":
        return handleRequestContext(client, safeArgs);
      case "get_meeting_recap":
        return handleGetMeetingRecap(client);
      case "get_entity_history":
        return handleGetEntityHistory(client, safeArgs);
      default:
        return {
          content: [{ type: "text" as const, text: `Unknown tool: ${name}` }],
          isError: true,
        };
    }
  });
}

// ---------------------------------------------------------------------------
// Handler implementations — Chat
// ---------------------------------------------------------------------------

async function handleReply(
  client: ConveneClient,
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
  client: ConveneClient,
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
  client: ConveneClient,
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
  client: ConveneClient,
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
  client: ConveneClient,
  args: Record<string, unknown>,
) {
  const priority =
    args["priority"] === "urgent" ? "urgent" : "normal";
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

async function handleGetQueueStatus(client: ConveneClient) {
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

async function handleMarkFinishedSpeaking(client: ConveneClient) {
  await client.finishedSpeaking();
  return ok(JSON.stringify({ status: "finished_speaking" }));
}

async function handleCancelHandRaise(
  client: ConveneClient,
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

function handleGetSpeakingStatus(client: ConveneClient) {
  const { isSpeaking, isInQueue } = client.getSpeakingStatus();
  const queueStatus = client.getLastQueueStatus();

  return ok(
    JSON.stringify(
      {
        is_speaking: isSpeaking,
        is_in_queue: isInQueue,
        last_known_queue: queueStatus,
        note: "Local state may lag by one event. Call get_queue_status to force a refresh.",
      },
      null,
      2,
    ),
  );
}

// ---------------------------------------------------------------------------
// Handler implementations — Participants
// ---------------------------------------------------------------------------

function handleGetParticipants(client: ConveneClient) {
  const participants = client.getParticipants();
  return ok(JSON.stringify(participants, null, 2));
}

// ---------------------------------------------------------------------------
// Handler implementations — Transcript & entity history
// ---------------------------------------------------------------------------

function handleRequestContext(
  client: ConveneClient,
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

function handleGetMeetingRecap(client: ConveneClient) {
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
    .map((e) => ({ id: e.id, summary: e.summary, participants: e.participants }));

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
    .map((e) => ({ id: e.id, description: e.description, severity: e.severity }));

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
  client: ConveneClient,
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
