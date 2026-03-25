// ── Docs Manifest ────────────────────────────────────────────────────────────
// Imports all external-docs markdown files as raw strings at build time.
// Vite resolves these at build time — no runtime fetching needed.

import readmeContent from "../../../external-docs/README.md?raw";
import agentPlatformOverview from "../../../external-docs/agent-platform/overview.md?raw";
import connectingMcpAuth from "../../../external-docs/agent-platform/connecting/mcp-auth.md?raw";
import connectingMcpQuickstart from "../../../external-docs/agent-platform/connecting/mcp-quickstart.md?raw";
import connectingClaudeCodeChannel from "../../../external-docs/agent-platform/connecting/claude-code-channel.md?raw";
import connectingCli from "../../../external-docs/agent-platform/connecting/cli.md?raw";
import openclawPluginGuide from "../../../external-docs/openclaw/plugin-guide.md?raw";
import openclawConveneSkill from "../../../external-docs/openclaw/convene-skill.md?raw";
import providersReadme from "../../../external-docs/providers/README.md?raw";
import providersLlmAnthropic from "../../../external-docs/providers/llm/anthropic.md?raw";
import providersLlmGroq from "../../../external-docs/providers/llm/groq.md?raw";
import providersLlmOllama from "../../../external-docs/providers/llm/ollama.md?raw";
import providersSttAssemblyai from "../../../external-docs/providers/stt/assemblyai.md?raw";
import providersSttDeepgram from "../../../external-docs/providers/stt/deepgram.md?raw";
import providersSttWhisper from "../../../external-docs/providers/stt/whisper.md?raw";
import providersTtsCartesia from "../../../external-docs/providers/tts/cartesia.md?raw";
import providersTtsElevenlabs from "../../../external-docs/providers/tts/elevenlabs.md?raw";
import providersTtsPiper from "../../../external-docs/providers/tts/piper.md?raw";
import selfHostingDeployment from "../../../external-docs/self-hosting/deployment.md?raw";

// ── Types ────────────────────────────────────────────────────────────────────

export type DocNode =
  | { kind: "page"; id: string; title: string; content: string }
  | { kind: "section"; id: string; title: string; children: DocNode[] };

// ── Flat lookup: slug → {title, content} ────────────────────────────────────

export const docPages: Record<string, { title: string; content: string }> = {
  overview: { title: "Overview", content: readmeContent },

  "agent-platform/overview": {
    title: "Agent Platform Overview",
    content: agentPlatformOverview,
  },
  "agent-platform/connecting/mcp-auth": {
    title: "MCP Authentication",
    content: connectingMcpAuth,
  },
  "agent-platform/connecting/mcp-quickstart": {
    title: "Connecting via MCP",
    content: connectingMcpQuickstart,
  },
  "agent-platform/connecting/claude-code-channel": {
    title: "Claude Code Channel",
    content: connectingClaudeCodeChannel,
  },
  "agent-platform/connecting/cli": {
    title: "Convene CLI",
    content: connectingCli,
  },

  "openclaw/plugin-guide": {
    title: "OpenClaw Plugin Guide",
    content: openclawPluginGuide,
  },
  "openclaw/convene-skill": {
    title: "Convene Skill",
    content: openclawConveneSkill,
  },

  "providers/overview": {
    title: "Providers Overview",
    content: providersReadme,
  },
  "providers/llm/anthropic": {
    title: "Anthropic",
    content: providersLlmAnthropic,
  },
  "providers/llm/groq": { title: "Groq", content: providersLlmGroq },
  "providers/llm/ollama": { title: "Ollama", content: providersLlmOllama },
  "providers/stt/assemblyai": {
    title: "AssemblyAI",
    content: providersSttAssemblyai,
  },
  "providers/stt/deepgram": {
    title: "Deepgram",
    content: providersSttDeepgram,
  },
  "providers/stt/whisper": {
    title: "Whisper (Self-hosted)",
    content: providersSttWhisper,
  },
  "providers/tts/cartesia": {
    title: "Cartesia",
    content: providersTtsCartesia,
  },
  "providers/tts/elevenlabs": {
    title: "ElevenLabs",
    content: providersTtsElevenlabs,
  },
  "providers/tts/piper": {
    title: "Piper (Self-hosted)",
    content: providersTtsPiper,
  },

  "self-hosting/deployment": {
    title: "Deployment",
    content: selfHostingDeployment,
  },
};

// ── Navigation tree ──────────────────────────────────────────────────────────

export const docsTree: DocNode[] = [
  { kind: "page", id: "overview", title: "Overview", content: readmeContent },

  {
    kind: "section",
    id: "agent-platform",
    title: "Agent Platform",
    children: [
      {
        kind: "page",
        id: "agent-platform/overview",
        title: "Overview",
        content: agentPlatformOverview,
      },
      {
        kind: "section",
        id: "agent-platform/connecting",
        title: "Connecting",
        children: [
          {
            kind: "page",
            id: "agent-platform/connecting/mcp-auth",
            title: "MCP Authentication",
            content: connectingMcpAuth,
          },
          {
            kind: "page",
            id: "agent-platform/connecting/mcp-quickstart",
            title: "Connecting via MCP",
            content: connectingMcpQuickstart,
          },
          {
            kind: "page",
            id: "agent-platform/connecting/claude-code-channel",
            title: "Claude Code Channel",
            content: connectingClaudeCodeChannel,
          },
          {
            kind: "page",
            id: "agent-platform/connecting/cli",
            title: "Convene CLI",
            content: connectingCli,
          },
        ],
      },
    ],
  },

  {
    kind: "section",
    id: "openclaw",
    title: "OpenClaw",
    children: [
      {
        kind: "page",
        id: "openclaw/plugin-guide",
        title: "Plugin Guide",
        content: openclawPluginGuide,
      },
      {
        kind: "page",
        id: "openclaw/convene-skill",
        title: "Convene Skill",
        content: openclawConveneSkill,
      },
    ],
  },

  {
    kind: "section",
    id: "providers",
    title: "Providers",
    children: [
      {
        kind: "page",
        id: "providers/overview",
        title: "Overview",
        content: providersReadme,
      },
      {
        kind: "section",
        id: "providers/llm",
        title: "LLM",
        children: [
          {
            kind: "page",
            id: "providers/llm/anthropic",
            title: "Anthropic",
            content: providersLlmAnthropic,
          },
          {
            kind: "page",
            id: "providers/llm/groq",
            title: "Groq",
            content: providersLlmGroq,
          },
          {
            kind: "page",
            id: "providers/llm/ollama",
            title: "Ollama",
            content: providersLlmOllama,
          },
        ],
      },
      {
        kind: "section",
        id: "providers/stt",
        title: "Speech-to-Text",
        children: [
          {
            kind: "page",
            id: "providers/stt/assemblyai",
            title: "AssemblyAI",
            content: providersSttAssemblyai,
          },
          {
            kind: "page",
            id: "providers/stt/deepgram",
            title: "Deepgram",
            content: providersSttDeepgram,
          },
          {
            kind: "page",
            id: "providers/stt/whisper",
            title: "Whisper (Self-hosted)",
            content: providersSttWhisper,
          },
        ],
      },
      {
        kind: "section",
        id: "providers/tts",
        title: "Text-to-Speech",
        children: [
          {
            kind: "page",
            id: "providers/tts/cartesia",
            title: "Cartesia",
            content: providersTtsCartesia,
          },
          {
            kind: "page",
            id: "providers/tts/elevenlabs",
            title: "ElevenLabs",
            content: providersTtsElevenlabs,
          },
          {
            kind: "page",
            id: "providers/tts/piper",
            title: "Piper (Self-hosted)",
            content: providersTtsPiper,
          },
        ],
      },
    ],
  },

  {
    kind: "section",
    id: "self-hosting",
    title: "Self-Hosting",
    children: [
      {
        kind: "page",
        id: "self-hosting/deployment",
        title: "Deployment",
        content: selfHostingDeployment,
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
