export function DocsPage() {
  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Documentation</h1>
        <p className="text-sm text-gray-400 mt-1">
          Connect your AI agents and get started with Convene AI
        </p>
      </div>

      {/* Quick Start */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-white border-b border-gray-800 pb-2">
          Quick Start
        </h2>
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            {
              step: "1",
              title: "Create an Agent",
              description: "Go to Dashboard → Create Agent to register a new AI agent and configure its capabilities.",
              href: "/agents/new",
              linkText: "Create Agent →",
            },
            {
              step: "2",
              title: "Generate an API Key",
              description: "Open your agent and generate an API key. Your agent uses this key to authenticate with Convene.",
              href: null,
              linkText: null,
            },
            {
              step: "3",
              title: "Join a Meeting",
              description: "Create a meeting, start it, and use your agent's API key to connect via WebSocket or MCP.",
              href: "/meetings",
              linkText: "View Meetings →",
            },
          ].map((item) => (
            <div key={item.step} className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-blue-600 text-xs font-bold text-white mb-3">
                {item.step}
              </div>
              <h3 className="text-sm font-semibold text-white mb-1">{item.title}</h3>
              <p className="text-xs text-gray-400 leading-relaxed">{item.description}</p>
              {item.href && (
                <a
                  href={item.href}
                  className="inline-block mt-2 text-xs text-blue-400 hover:text-blue-300"
                >
                  {item.linkText}
                </a>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* Agent Connection */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-white border-b border-gray-800 pb-2">
          Agent Connection (Claude Agent SDK)
        </h2>
        <p className="text-sm text-gray-400">
          Connect a Claude agent to Convene AI using the MCP server and your agent&apos;s API key.
        </p>
        <div className="rounded-lg border border-gray-800 bg-gray-950 p-4">
          <p className="text-xs text-gray-500 mb-2 font-mono">claude_desktop_config.json</p>
          <pre className="text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap font-mono leading-relaxed">{`{
  "mcpServers": {
    "convene": {
      "command": "docker",
      "args": ["run", "--rm", "-i",
        "-e", "CONVENE_API_KEY=<your-api-key>",
        "-e", "CONVENE_API_URL=https://convene.spark-b0f2.local/api/v1",
        "convene-mcp-server"
      ]
    }
  }
}`}</pre>
        </div>
      </section>

      {/* WebSocket Protocol */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-white border-b border-gray-800 pb-2">
          Agent WebSocket Protocol
        </h2>
        <p className="text-sm text-gray-400">
          Agents can connect directly to the agent gateway via WebSocket.
        </p>
        <div className="rounded-lg border border-gray-800 bg-gray-950 p-4">
          <p className="text-xs text-gray-500 mb-2 font-mono">Connection URL</p>
          <pre className="text-xs text-gray-300 font-mono">{`wss://<host>/agent/connect?token=<api-key>&meeting_id=<id>`}</pre>
        </div>
        <div className="space-y-2">
          {[
            { msg: '{ "type": "join_meeting", "meeting_id": "..." }', desc: "Join a meeting room" },
            { msg: '{ "type": "audio_data", "data": "<base64-pcm16>", "sample_rate": 16000 }', desc: "Stream audio (16kHz mono PCM16, base64)" },
            { msg: '{ "type": "leave_meeting" }', desc: "Leave the meeting" },
          ].map((item) => (
            <div key={item.msg} className="rounded-lg border border-gray-800 bg-gray-950 p-3">
              <p className="text-xs text-gray-500 mb-1">{item.desc}</p>
              <pre className="text-xs text-gray-300 font-mono overflow-x-auto">{item.msg}</pre>
            </div>
          ))}
        </div>
      </section>

      {/* MCP Tools */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-white border-b border-gray-800 pb-2">
          MCP Tools
        </h2>
        <p className="text-sm text-gray-400">
          The Convene MCP server exposes these tools to Claude agents:
        </p>
        <div className="space-y-2">
          {[
            { name: "convene_join_meeting", desc: "Join a meeting by ID. Returns participant list and meeting context." },
            { name: "convene_leave_meeting", desc: "Leave the current meeting." },
            { name: "convene_start_speaking", desc: "Send a text message that will be spoken aloud via TTS in the meeting." },
            { name: "convene_list_meetings", desc: "List active and upcoming meetings." },
            { name: "convene_get_transcript", desc: "Retrieve the meeting transcript so far." },
          ].map((tool) => (
            <div key={tool.name} className="flex gap-3 rounded-lg border border-gray-800 bg-gray-900/50 p-3">
              <code className="shrink-0 text-xs font-mono text-blue-400 mt-0.5">{tool.name}</code>
              <p className="text-xs text-gray-400">{tool.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Resources */}
      <section className="space-y-4">
        <h2 className="text-lg font-semibold text-white border-b border-gray-800 pb-2">
          Further Reading
        </h2>
        <div className="grid gap-3 sm:grid-cols-2">
          {[
            { title: "Agent Platform Overview", path: "docs/technical/AGENT_PLATFORM.md" },
            { title: "MCP Auth (OAuth 2.1)", path: "docs/technical/MCP_AUTH.md" },
            { title: "Claude Agent SDK Setup", path: "docs/integrations/CLAUDE_AGENT_SDK.md" },
            { title: "CLI Reference", path: "docs/integrations/CLI.md" },
            { title: "Cost Architecture", path: "docs/technical/cost-architecture.md" },
            { title: "Full Task Roadmap", path: "docs/TASKLIST.md" },
          ].map((doc) => (
            <div key={doc.path} className="flex items-center justify-between rounded-lg border border-gray-800 bg-gray-900/50 px-4 py-3">
              <span className="text-sm text-gray-300">{doc.title}</span>
              <code className="text-xs text-gray-600 font-mono">{doc.path}</code>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
