/**
 * Convene AI OpenClaw Plugin
 *
 * Registers native Convene meeting tools in the OpenClaw gateway,
 * allowing agents to join meetings, manage turns, chat, read transcripts,
 * and create tasks.
 */

import { ConveneClient, type ConveneConfig } from "./convene-client.js";

/**
 * OpenClaw plugin interface (simplified — actual interface depends on OpenClaw SDK version).
 */
interface PluginContext {
  config: {
    apiKey: string;
    mcpUrl?: string;
  };
  registerTool: (name: string, handler: ToolHandler) => void;
  logger: {
    info: (msg: string) => void;
    error: (msg: string) => void;
  };
}

type ToolHandler = (params: Record<string, unknown>) => Promise<string>;

/**
 * Plugin entry point. Called by OpenClaw when the plugin is loaded.
 */
export default function register(ctx: PluginContext): void {
  const config: ConveneConfig = {
    apiKey: ctx.config.apiKey,
    mcpUrl: ctx.config.mcpUrl ?? "http://localhost:3001/mcp",
  };

  const client = new ConveneClient(config);

  // Authenticate on first tool call
  let authenticated = false;
  async function ensureAuth(): Promise<void> {
    if (!authenticated) {
      await client.authenticate();
      authenticated = true;
      ctx.logger.info("Authenticated with Convene MCP server");
    }
  }

  // ---------------------------------------------------------------------------
  // Meeting management
  // ---------------------------------------------------------------------------

  ctx.registerTool("convene_list_meetings", async () => {
    await ensureAuth();
    const meetings = await client.listMeetings();
    return JSON.stringify(meetings, null, 2);
  });

  ctx.registerTool("convene_join_meeting", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.joinMeeting(meetingId);
  });

  ctx.registerTool("convene_create_meeting", async (params) => {
    await ensureAuth();
    const title = params.title as string;
    if (!title) return "Error: title is required";
    const meeting = await client.createMeeting(title);
    return JSON.stringify(meeting, null, 2);
  });

  // ---------------------------------------------------------------------------
  // Transcript & tasks
  // ---------------------------------------------------------------------------

  ctx.registerTool("convene_get_transcript", async (params) => {
    await ensureAuth();
    const lastN = (params.last_n as number) ?? 50;
    const segments = await client.getTranscript(lastN);
    return JSON.stringify(segments, null, 2);
  });

  ctx.registerTool("convene_create_task", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    const description = params.description as string;
    const priority = (params.priority as string) ?? "medium";
    if (!meetingId || !description) {
      return "Error: meeting_id and description are required";
    }
    const task = await client.createTask(meetingId, description, priority);
    return JSON.stringify(task, null, 2);
  });

  // ---------------------------------------------------------------------------
  // Participants
  // ---------------------------------------------------------------------------

  ctx.registerTool("convene_get_participants", async () => {
    await ensureAuth();
    const participants = await client.getParticipants();
    return JSON.stringify(participants, null, 2);
  });

  // ---------------------------------------------------------------------------
  // Turn management
  // ---------------------------------------------------------------------------

  ctx.registerTool("convene_raise_hand", async (params) => {
    await ensureAuth();
    const priority = (params.priority as string) ?? "normal";
    const topic = params.topic as string | undefined;
    return await client.raiseHand(priority, topic);
  });

  ctx.registerTool("convene_get_queue_status", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    const status = await client.getQueueStatus(meetingId);
    return JSON.stringify(status, null, 2);
  });

  ctx.registerTool("convene_mark_finished_speaking", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.markFinishedSpeaking(meetingId);
  });

  ctx.registerTool("convene_cancel_hand_raise", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    const handRaiseId = params.hand_raise_id as string | undefined;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.cancelHandRaise(meetingId, handRaiseId);
  });

  ctx.registerTool("convene_get_speaking_status", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.getSpeakingStatus(meetingId);
  });

  // ---------------------------------------------------------------------------
  // Chat
  // ---------------------------------------------------------------------------

  ctx.registerTool("convene_send_chat_message", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    const text = params.text as string;
    if (!meetingId || !text) return "Error: meeting_id and text are required";
    return await client.sendChatMessage(meetingId, text);
  });

  ctx.registerTool("convene_get_chat_messages", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    const limit = (params.limit as number) ?? 50;
    if (!meetingId) return "Error: meeting_id is required";
    const messages = await client.getChatMessages(meetingId, limit);
    return JSON.stringify(messages, null, 2);
  });

  ctx.logger.info("Convene AI plugin registered with 14 tools");
}
