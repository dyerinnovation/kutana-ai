/**
 * MCP tool registrations for the Convene AI Channel Server.
 *
 * Tools enable two-way communication: Claude can send messages, claim tasks,
 * report progress, search the transcript buffer, and query entity history.
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
      case "accept_task":
        return handleAcceptTask(client, safeArgs);
      case "update_status":
        return handleUpdateStatus(client, safeArgs);
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
// Handler implementations
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
