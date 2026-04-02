// ── Docs Manifest ────────────────────────────────────────────────────────────
// Imports all external-docs markdown files as raw strings at build time.
// Vite resolves these at build time — no runtime fetching needed.

import readmeContent from "../../../external-docs/README.md?raw";
import connectingOverview from "../../../external-docs/connecting-agents/overview.md?raw";
import connectingMcpAuth from "../../../external-docs/connecting-agents/custom-agents/mcp-auth.md?raw";
import connectingMcpQuickstart from "../../../external-docs/connecting-agents/custom-agents/mcp-quickstart.md?raw";
import connectingClaudeCodeChannel from "../../../external-docs/connecting-agents/custom-agents/claude-code-channel.md?raw";
import connectingClaudeAgentSdk from "../../../external-docs/connecting-agents/custom-agents/claude-agent-sdk.md?raw";
import connectingCli from "../../../external-docs/connecting-agents/custom-agents/cli.md?raw";
import connectingOpenclawPlugin from "../../../external-docs/connecting-agents/custom-agents/openclaw-plugin.md?raw";
import connectingKutanaSkill from "../../../external-docs/connecting-agents/custom-agents/kutana-skill.md?raw";
import managedAgentsOverview from "../../../external-docs/connecting-agents/managed-agents/overview.md?raw";
import feedsOverview from "../../../external-docs/feeds/overview.md?raw";

// ── Types ────────────────────────────────────────────────────────────────────

export type DocNode =
  | { kind: "page"; id: string; title: string; content: string }
  | { kind: "section"; id: string; title: string; children: DocNode[] };

// ── Flat lookup: slug → {title, content} ────────────────────────────────────

export const docPages: Record<string, { title: string; content: string }> = {
  overview: { title: "Overview", content: readmeContent },

  "connecting-agents/overview": {
    title: "Connecting Agents",
    content: connectingOverview,
  },
  "connecting-agents/custom-agents/mcp-auth": {
    title: "MCP Authentication",
    content: connectingMcpAuth,
  },
  "connecting-agents/custom-agents/mcp-quickstart": {
    title: "Connecting via MCP",
    content: connectingMcpQuickstart,
  },
  "connecting-agents/custom-agents/claude-code-channel": {
    title: "Claude Code Channel",
    content: connectingClaudeCodeChannel,
  },
  "connecting-agents/custom-agents/claude-agent-sdk": {
    title: "Claude Agent SDK",
    content: connectingClaudeAgentSdk,
  },
  "connecting-agents/custom-agents/cli": {
    title: "Kutana CLI",
    content: connectingCli,
  },
  "connecting-agents/custom-agents/openclaw-plugin": {
    title: "OpenClaw Plugin",
    content: connectingOpenclawPlugin,
  },
  "connecting-agents/custom-agents/kutana-skill": {
    title: "Kutana Skill",
    content: connectingKutanaSkill,
  },
  "connecting-agents/managed-agents/overview": {
    title: "Managed Agents",
    content: managedAgentsOverview,
  },

  "feeds/overview": {
    title: "Feeds",
    content: feedsOverview,
  },
};

// ── Navigation tree ──────────────────────────────────────────────────────────

export const docsTree: DocNode[] = [
  { kind: "page", id: "overview", title: "Overview", content: readmeContent },

  {
    kind: "section",
    id: "connecting-agents",
    title: "Connecting Agents",
    children: [
      {
        kind: "page",
        id: "connecting-agents/overview",
        title: "Overview",
        content: connectingOverview,
      },
      {
        kind: "section",
        id: "connecting-agents/custom-agents",
        title: "Custom Agents",
        children: [
          {
            kind: "page",
            id: "connecting-agents/custom-agents/mcp-quickstart",
            title: "MCP Quickstart",
            content: connectingMcpQuickstart,
          },
          {
            kind: "page",
            id: "connecting-agents/custom-agents/mcp-auth",
            title: "MCP Authentication",
            content: connectingMcpAuth,
          },
          {
            kind: "page",
            id: "connecting-agents/custom-agents/claude-code-channel",
            title: "Claude Code Channel",
            content: connectingClaudeCodeChannel,
          },
          {
            kind: "page",
            id: "connecting-agents/custom-agents/claude-agent-sdk",
            title: "Claude Agent SDK",
            content: connectingClaudeAgentSdk,
          },
          {
            kind: "page",
            id: "connecting-agents/custom-agents/cli",
            title: "Kutana CLI",
            content: connectingCli,
          },
          {
            kind: "page",
            id: "connecting-agents/custom-agents/openclaw-plugin",
            title: "OpenClaw Plugin",
            content: connectingOpenclawPlugin,
          },
          {
            kind: "page",
            id: "connecting-agents/custom-agents/kutana-skill",
            title: "Kutana Skill",
            content: connectingKutanaSkill,
          },
        ],
      },
      {
        kind: "section",
        id: "connecting-agents/managed-agents",
        title: "Managed Agents",
        children: [
          {
            kind: "page",
            id: "connecting-agents/managed-agents/overview",
            title: "Overview",
            content: managedAgentsOverview,
          },
        ],
      },
    ],
  },

  {
    kind: "section",
    id: "feeds",
    title: "Feeds",
    children: [
      {
        kind: "page",
        id: "feeds/overview",
        title: "Overview",
        content: feedsOverview,
      },
    ],
  },
];

/** Return the first page id in the tree (used as default landing page). */
export function firstPageId(nodes: DocNode[]): string {
  for (const node of nodes) {
    if (node.kind === "page") return node.id;
    const found = firstPageId(node.children);
    if (found) return found;
  }
  return "overview";
}
