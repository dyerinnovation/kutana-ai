/**
 * MCP tool registrations for the Discord MCP server.
 *
 * Tools expose Discord Bot API operations: send/edit/fetch messages,
 * add reactions, and get channel metadata.
 */

import type { Server } from "@modelcontextprotocol/sdk/server/index.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import {
  Client,
  type TextChannel,
  type NewsChannel,
  type DMChannel,
  ChannelType,
  type APIEmbed,
} from "discord.js";

/** Register all Discord tools on the MCP server. */
export function registerTools(server: Server, client: Client): void {
  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: [
      {
        name: "send_message",
        description:
          "Send a message to a Discord channel. Supports plain text and optional rich embeds.",
        inputSchema: {
          type: "object",
          properties: {
            channel_id: {
              type: "string",
              description: "The Discord channel ID to send the message to.",
            },
            content: {
              type: "string",
              description: "The text content of the message.",
            },
            embeds: {
              type: "array",
              description:
                "Optional array of Discord embed objects (title, description, color, fields, etc.).",
              items: {
                type: "object",
              },
            },
          },
          required: ["channel_id", "content"],
        },
      },
      {
        name: "fetch_messages",
        description:
          "Fetch recent messages from a Discord channel. Returns up to 100 messages.",
        inputSchema: {
          type: "object",
          properties: {
            channel_id: {
              type: "string",
              description: "The Discord channel ID to fetch messages from.",
            },
            limit: {
              type: "number",
              description:
                "Number of messages to fetch (default: 50, max: 100).",
            },
          },
          required: ["channel_id"],
        },
      },
      {
        name: "edit_message",
        description: "Edit an existing message in a Discord channel.",
        inputSchema: {
          type: "object",
          properties: {
            channel_id: {
              type: "string",
              description: "The Discord channel ID containing the message.",
            },
            message_id: {
              type: "string",
              description: "The ID of the message to edit.",
            },
            content: {
              type: "string",
              description: "The new text content for the message.",
            },
          },
          required: ["channel_id", "message_id", "content"],
        },
      },
      {
        name: "react",
        description: "Add a reaction emoji to a message in a Discord channel.",
        inputSchema: {
          type: "object",
          properties: {
            channel_id: {
              type: "string",
              description: "The Discord channel ID containing the message.",
            },
            message_id: {
              type: "string",
              description: "The ID of the message to react to.",
            },
            emoji: {
              type: "string",
              description:
                'The emoji to react with (Unicode emoji or custom emoji string like "<:name:id>").',
            },
          },
          required: ["channel_id", "message_id", "emoji"],
        },
      },
      {
        name: "get_channel_info",
        description:
          "Get metadata about a Discord channel including its name, type, and guild.",
        inputSchema: {
          type: "object",
          properties: {
            channel_id: {
              type: "string",
              description: "The Discord channel ID to get info for.",
            },
          },
          required: ["channel_id"],
        },
      },
    ],
  }));

  server.setRequestHandler(CallToolRequestSchema, async (request) => {
    const { name, arguments: args } = request.params;
    const safeArgs = args ?? {};

    switch (name) {
      case "send_message":
        return handleSendMessage(client, safeArgs);
      case "fetch_messages":
        return handleFetchMessages(client, safeArgs);
      case "edit_message":
        return handleEditMessage(client, safeArgs);
      case "react":
        return handleReact(client, safeArgs);
      case "get_channel_info":
        return handleGetChannelInfo(client, safeArgs);
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

/** Resolve a text-based channel from a channel ID. */
async function resolveTextChannel(
  client: Client,
  channelId: string,
): Promise<TextChannel | NewsChannel | DMChannel> {
  const channel = await client.channels.fetch(channelId);
  if (!channel) {
    throw new Error(`Channel not found: ${channelId}`);
  }
  if (
    channel.type !== ChannelType.GuildText &&
    channel.type !== ChannelType.GuildAnnouncement &&
    channel.type !== ChannelType.DM
  ) {
    throw new Error(
      `Channel ${channelId} is not a text-based channel (type: ${channel.type})`,
    );
  }
  return channel as TextChannel | NewsChannel | DMChannel;
}

async function handleSendMessage(
  client: Client,
  args: Record<string, unknown>,
) {
  const channelId = args["channel_id"];
  const content = args["content"];
  const embeds = args["embeds"];

  if (typeof channelId !== "string" || !channelId.trim()) {
    return error("channel_id is required and must be a non-empty string");
  }
  if (typeof content !== "string" || !content.trim()) {
    return error("content is required and must be a non-empty string");
  }

  try {
    const channel = await resolveTextChannel(client, channelId);

    const messagePayload: { content: string; embeds?: APIEmbed[] } = { content };
    if (Array.isArray(embeds) && embeds.length > 0) {
      messagePayload.embeds = embeds as APIEmbed[];
    }

    const msg = await channel.send(messagePayload);
    return ok(
      JSON.stringify({
        message_id: msg.id,
        channel_id: channelId,
        timestamp: msg.createdAt.toISOString(),
      }),
    );
  } catch (err) {
    return error(`Failed to send message: ${String(err)}`);
  }
}

async function handleFetchMessages(
  client: Client,
  args: Record<string, unknown>,
) {
  const channelId = args["channel_id"];
  if (typeof channelId !== "string" || !channelId.trim()) {
    return error("channel_id is required");
  }

  const rawLimit =
    typeof args["limit"] === "number" && args["limit"] > 0
      ? Math.floor(args["limit"])
      : 50;
  const limit = Math.min(rawLimit, 100);

  try {
    const channel = await resolveTextChannel(client, channelId);
    const messages = await channel.messages.fetch({ limit });

    const result = messages.map((msg) => ({
      id: msg.id,
      author: msg.author.tag,
      content: msg.content,
      timestamp: msg.createdAt.toISOString(),
      embeds: msg.embeds.map((e) => ({
        title: e.title,
        description: e.description,
        url: e.url,
      })),
    }));

    return ok(JSON.stringify(result, null, 2));
  } catch (err) {
    return error(`Failed to fetch messages: ${String(err)}`);
  }
}

async function handleEditMessage(
  client: Client,
  args: Record<string, unknown>,
) {
  const channelId = args["channel_id"];
  const messageId = args["message_id"];
  const content = args["content"];

  if (typeof channelId !== "string" || !channelId.trim()) {
    return error("channel_id is required");
  }
  if (typeof messageId !== "string" || !messageId.trim()) {
    return error("message_id is required");
  }
  if (typeof content !== "string" || !content.trim()) {
    return error("content is required");
  }

  try {
    const channel = await resolveTextChannel(client, channelId);
    const message = await channel.messages.fetch(messageId);
    await message.edit(content);
    return ok(JSON.stringify({ message_id: messageId, updated: true }));
  } catch (err) {
    return error(`Failed to edit message: ${String(err)}`);
  }
}

async function handleReact(client: Client, args: Record<string, unknown>) {
  const channelId = args["channel_id"];
  const messageId = args["message_id"];
  const emoji = args["emoji"];

  if (typeof channelId !== "string" || !channelId.trim()) {
    return error("channel_id is required");
  }
  if (typeof messageId !== "string" || !messageId.trim()) {
    return error("message_id is required");
  }
  if (typeof emoji !== "string" || !emoji.trim()) {
    return error("emoji is required");
  }

  try {
    const channel = await resolveTextChannel(client, channelId);
    const message = await channel.messages.fetch(messageId);
    await message.react(emoji);
    return ok(JSON.stringify({ reacted: true }));
  } catch (err) {
    return error(`Failed to add reaction: ${String(err)}`);
  }
}

async function handleGetChannelInfo(
  client: Client,
  args: Record<string, unknown>,
) {
  const channelId = args["channel_id"];
  if (typeof channelId !== "string" || !channelId.trim()) {
    return error("channel_id is required");
  }

  try {
    const channel = await client.channels.fetch(channelId);
    if (!channel) {
      return error(`Channel not found: ${channelId}`);
    }

    const info: Record<string, unknown> = {
      id: channel.id,
      type: ChannelType[channel.type],
    };

    if ("name" in channel && channel.name) {
      info.name = channel.name;
    }
    if ("guild" in channel && channel.guild) {
      info.guild_name = channel.guild.name;
    }

    return ok(JSON.stringify(info));
  } catch (err) {
    return error(`Failed to get channel info: ${String(err)}`);
  }
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
