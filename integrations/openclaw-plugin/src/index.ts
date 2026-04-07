/**
 * Kutana AI OpenClaw Plugin
 *
 * Registers native Kutana meeting tools in the OpenClaw gateway,
 * allowing agents to join meetings, read transcripts, and create tasks.
 */

import { KutanaClient, type KutanaConfig } from "./kutana-client.js";

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
  const config: KutanaConfig = {
    apiKey: ctx.config.apiKey,
    mcpUrl: ctx.config.mcpUrl ?? "https://kutana.spark-b0f2.local/mcp",
  };

  const client = new KutanaClient(config);

  // Authenticate on first tool call
  let authenticated = false;
  async function ensureAuth(): Promise<void> {
    if (!authenticated) {
      await client.authenticate();
      authenticated = true;
      ctx.logger.info("Authenticated with Kutana MCP server");
    }
  }

  // Register tools
  ctx.registerTool("kutana_list_meetings", async () => {
    await ensureAuth();
    const meetings = await client.listMeetings();
    return JSON.stringify(meetings, null, 2);
  });

  ctx.registerTool("kutana_join_meeting", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    const capabilities = params.capabilities as string[] | undefined;
    return await client.joinMeeting(meetingId, capabilities);
  });

  ctx.registerTool("kutana_get_transcript", async (params) => {
    await ensureAuth();
    const lastN = (params.last_n as number) ?? 50;
    const segments = await client.getTranscript(lastN);
    return JSON.stringify(segments, null, 2);
  });

  ctx.registerTool("kutana_create_task", async (params) => {
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

  ctx.registerTool("kutana_get_participants", async () => {
    await ensureAuth();
    const participants = await client.getParticipants();
    return JSON.stringify(participants, null, 2);
  });

  ctx.registerTool("kutana_create_meeting", async (params) => {
    await ensureAuth();
    const title = params.title as string;
    if (!title) return "Error: title is required";
    const meeting = await client.createMeeting(title);
    return JSON.stringify(meeting, null, 2);
  });

  // Turn Management Tools
  ctx.registerTool("kutana_start_speaking", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.startSpeaking(meetingId);
  });

  ctx.registerTool("kutana_raise_hand", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    const priority = (params.priority as string) ?? "normal";
    const topic = params.topic as string | undefined;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.raiseHand(meetingId, priority, topic);
  });

  ctx.registerTool("kutana_get_queue_status", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.getQueueStatus(meetingId);
  });

  ctx.registerTool("kutana_mark_finished_speaking", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.markFinishedSpeaking(meetingId);
  });

  ctx.registerTool("kutana_cancel_hand_raise", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    const handRaiseId = params.hand_raise_id as string | undefined;
    return await client.cancelHandRaise(meetingId, handRaiseId);
  });

  // Chat Tools
  ctx.registerTool("kutana_send_chat_message", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    const content = params.content as string;
    const messageType = (params.message_type as string) ?? "text";
    if (!meetingId || !content) {
      return "Error: meeting_id and content are required";
    }
    return await client.sendChatMessage(meetingId, content, messageType);
  });

  ctx.registerTool("kutana_get_chat_messages", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    const limit = (params.limit as number) ?? 50;
    const messageType = params.message_type as string | undefined;
    const since = params.since as string | undefined;
    return await client.getChatMessages(meetingId, limit, messageType, since);
  });

  ctx.registerTool("kutana_leave_meeting", async () => {
    await ensureAuth();
    return await client.leaveMeeting();
  });

  ctx.registerTool("kutana_speak", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    const text = params.text as string;
    if (!meetingId || !text) return "Error: meeting_id and text are required";
    return await client.speak(meetingId, text);
  });

  ctx.registerTool("kutana_get_meeting_status", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.getMeetingStatus(meetingId);
  });

  ctx.registerTool("kutana_get_speaking_status", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.getSpeakingStatus(meetingId);
  });

  // Meeting lifecycle tools
  ctx.registerTool("kutana_get_tasks", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.getTasks(meetingId);
  });

  ctx.registerTool("kutana_get_summary", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.getSummary(meetingId);
  });

  ctx.registerTool("kutana_set_context", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    const context = params.context as string;
    if (!meetingId || !context) return "Error: meeting_id and context are required";
    return await client.setContext(meetingId, context);
  });

  ctx.registerTool("kutana_start_meeting", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.startMeeting(meetingId);
  });

  ctx.registerTool("kutana_end_meeting", async (params) => {
    await ensureAuth();
    const meetingId = params.meeting_id as string;
    if (!meetingId) return "Error: meeting_id is required";
    return await client.endMeeting(meetingId);
  });

  ctx.registerTool("kutana_join_or_create_meeting", async (params) => {
    await ensureAuth();
    const title = params.title as string;
    if (!title) return "Error: title is required";
    const capabilities = params.capabilities as string[] | undefined;
    return await client.joinOrCreateMeeting(title, capabilities);
  });

  // Data channel tools
  ctx.registerTool("kutana_subscribe_channel", async (params) => {
    await ensureAuth();
    const channel = params.channel as string;
    if (!channel) return "Error: channel is required";
    return await client.subscribeChannel(channel);
  });

  ctx.registerTool("kutana_publish_to_channel", async (params) => {
    await ensureAuth();
    const channel = params.channel as string;
    const payload = params.payload as Record<string, unknown>;
    if (!channel || !payload) return "Error: channel and payload are required";
    return await client.publishToChannel(channel, payload);
  });

  ctx.registerTool("kutana_get_channel_messages", async (params) => {
    await ensureAuth();
    const channel = params.channel as string;
    if (!channel) return "Error: channel is required";
    const lastN = (params.last_n as number) ?? 50;
    return await client.getChannelMessages(channel, lastN);
  });

  ctx.registerTool("kutana_get_meeting_events", async (params) => {
    await ensureAuth();
    const lastN = (params.last_n as number) ?? 50;
    const eventType = params.event_type as string | undefined;
    return await client.getMeetingEvents(lastN, eventType);
  });

  ctx.logger.info("Kutana AI plugin registered with 27 tools");
}
