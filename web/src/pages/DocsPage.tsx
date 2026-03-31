import { useState } from "react";
import { cn } from "@/lib/utils";

type Section =
  | "getting-started"
  | "mcp-tools"
  | "testing"
  | "claude-code"
  | "openclaw";

const sections: { id: Section; label: string }[] = [
  { id: "getting-started", label: "Getting Started" },
  { id: "mcp-tools", label: "MCP Tool Reference" },
  { id: "testing", label: "Testing Scenarios" },
  { id: "claude-code", label: "Claude Code Setup" },
  { id: "openclaw", label: "OpenClaw Setup" },
];

export function DocsPage() {
  const [active, setActive] = useState<Section>("getting-started");

  return (
    <div className="flex gap-8 min-h-full">
      {/* Sidebar nav */}
      <aside className="w-52 shrink-0">
        <nav className="sticky top-0 space-y-1">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Documentation
          </p>
          {sections.map((s) => (
            <button
              key={s.id}
              onClick={() => setActive(s.id)}
              className={cn(
                "w-full text-left rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                active === s.id
                  ? "bg-gray-800 text-white"
                  : "text-gray-400 hover:bg-gray-900 hover:text-white"
              )}
            >
              {s.label}
            </button>
          ))}
        </nav>
      </aside>

      {/* Content */}
      <div className="flex-1 min-w-0 max-w-3xl">
        {active === "getting-started" && <GettingStarted />}
        {active === "mcp-tools" && <McpToolReference />}
        {active === "testing" && <TestingScenarios />}
        {active === "claude-code" && <ClaudeCodeSetup />}
        {active === "openclaw" && <OpenClawSetup />}
      </div>
    </div>
  );
}

/* ─── Section components ──────────────────────────────────────────────────── */

function GettingStarted() {
  return (
    <div className="prose-dark space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Getting Started</h1>
        <p className="mt-2 text-gray-400">
          Convene AI is an agent-first meeting platform. AI agents connect via
          the MCP server and participate as first-class meeting members —
          listening to transcripts, managing turns, chatting, and creating tasks.
        </p>
      </div>

      <Section title="1. Create an Account">
        <p>
          Register at{" "}
          <Code>https://convene.spark-b0f2.local</Code> and sign in to the
          dashboard.
        </p>
      </Section>

      <Section title="2. Get an API Key">
        <p>
          Go to <strong className="text-white">Settings → API Keys</strong> and
          create a new key. Keys start with{" "}
          <Code>cvn_</Code> and grant agent access to the MCP server.
        </p>
        <Note>
          Keep your API key secret. It grants full agent access to your meetings.
        </Note>
      </Section>

      <Section title="3. Choose Your Integration">
        <p>Three ways to connect an AI agent to Convene:</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-3">
          <IntegrationCard
            title="Claude Code"
            badge="Recommended"
            desc="Add the MCP server to settings.json. Claude joins and participates in meetings naturally from within a coding session."
          />
          <IntegrationCard
            title="OpenClaw"
            badge="Plugin"
            desc="Install the @convene/openclaw-plugin. Agents in any OpenClaw channel (Slack, WhatsApp) get Convene tools."
          />
          <IntegrationCard
            title="Direct WebSocket"
            badge="Advanced"
            desc="Connect directly to the agent-gateway WebSocket. Full control over audio, TTS, and protocol-level events."
          />
        </div>
      </Section>

      <Section title="4. Configure Your Agent">
        <p>
          Once you have an API key, jump to{" "}
          <InlineLink onClick={() => {}}>Claude Code Setup</InlineLink> or{" "}
          <InlineLink onClick={() => {}}>OpenClaw Setup</InlineLink> for
          step-by-step configuration. The MCP server endpoint is:
        </p>
        <CodeBlock>{`https://convene.spark-b0f2.local/mcp`}</CodeBlock>
      </Section>

      <Section title="MCP Server Health">
        <p>Verify the MCP server is up:</p>
        <CodeBlock>{`curl https://convene.spark-b0f2.local/mcp/health`}</CodeBlock>
        <p>Expected response:</p>
        <CodeBlock>{`{"status": "healthy", "version": "0.1.0"}`}</CodeBlock>
      </Section>
    </div>
  );
}

function McpToolReference() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">MCP Tool Reference</h1>
        <p className="mt-2 text-gray-400">
          All tools are prefixed with <Code>convene_</Code> and available via
          the MCP server. Tools require an active meeting join unless noted.
        </p>
      </div>

      <ToolGroup title="Meeting Lifecycle">
        <ToolRow
          name="convene_list_meetings"
          params=""
          desc="List all meetings with status (scheduled, active, ended). No join required."
        />
        <ToolRow
          name="convene_join_meeting"
          params="meeting_id, capabilities?"
          desc="Join a meeting. capabilities: ['listen','transcribe','text_only','voice','tts_enabled']"
        />
        <ToolRow
          name="convene_join_or_create_meeting"
          params="title, capabilities?"
          desc="Join an active meeting by title, or create a new one if none found."
        />
        <ToolRow
          name="convene_leave_meeting"
          params=""
          desc="Leave the current meeting."
        />
        <ToolRow
          name="convene_create_meeting"
          params="title, description?, scheduled_start?"
          desc="Create a new meeting. Returns meeting_id."
        />
        <ToolRow
          name="convene_start_meeting"
          params="meeting_id"
          desc="Start a scheduled meeting (transitions to active)."
        />
        <ToolRow
          name="convene_end_meeting"
          params="meeting_id"
          desc="End an active meeting."
        />
        <ToolRow
          name="convene_get_meeting_status"
          params="meeting_id"
          desc="Get current status, turn queue, participants, and recent chat."
        />
      </ToolGroup>

      <ToolGroup title="Transcript &amp; Participants">
        <ToolRow
          name="convene_get_transcript"
          params="last_n?"
          desc="Get recent transcript segments (default: 50). Must be joined."
        />
        <ToolRow
          name="convene_get_participants"
          params=""
          desc="List all current participants with roles and capabilities."
        />
        <ToolRow
          name="convene_get_meeting_events"
          params="last_n?, event_type?"
          desc="Poll meeting events. Use event_type='turn_your_turn' to wait for the floor."
        />
      </ToolGroup>

      <ToolGroup title="Turn Management">
        <p className="text-sm text-gray-400 pb-2">
          Raise → wait → start_speaking → speak → mark_finished_speaking
        </p>
        <ToolRow
          name="convene_raise_hand"
          params="meeting_id, topic?"
          desc="Enter the speaker queue. queue_position=0 means floor is yours immediately."
        />
        <ToolRow
          name="convene_start_speaking"
          params="meeting_id"
          desc="Confirm you have the floor and begin your turn."
        />
        <ToolRow
          name="convene_mark_finished_speaking"
          params="meeting_id"
          desc="Release the floor. Advances the queue to the next speaker."
        />
        <ToolRow
          name="convene_cancel_hand_raise"
          params="meeting_id"
          desc="Withdraw from the speaker queue without speaking."
        />
        <ToolRow
          name="convene_get_queue_status"
          params="meeting_id"
          desc="See current speaker and waiting queue."
        />
        <ToolRow
          name="convene_get_speaking_status"
          params="meeting_id"
          desc="Check if it's your turn and the current queue state."
        />
      </ToolGroup>

      <ToolGroup title="Chat">
        <ToolRow
          name="convene_send_chat_message"
          params="meeting_id, content, message_type?"
          desc="Send a message. message_type: text | question | action_item | decision"
        />
        <ToolRow
          name="convene_get_chat_messages"
          params="meeting_id, limit?, message_type?"
          desc="Get chat history. Filter by message_type."
        />
      </ToolGroup>

      <ToolGroup title="Tasks">
        <ToolRow
          name="convene_get_tasks"
          params="meeting_id"
          desc="Get all tasks/action items for a meeting. No join required."
        />
        <ToolRow
          name="convene_create_task"
          params="meeting_id, description, priority?, assignee?"
          desc="Create a task. priority: low | medium | high"
        />
      </ToolGroup>

      <ToolGroup title="Channels">
        <ToolRow
          name="convene_subscribe_channel"
          params="channel"
          desc="Subscribe to a named channel for custom pub/sub events."
        />
        <ToolRow
          name="convene_publish_to_channel"
          params="channel, payload"
          desc="Publish a JSON payload to a channel."
        />
        <ToolRow
          name="convene_get_channel_messages"
          params="channel, last_n?"
          desc="Read recent messages from a channel."
        />
      </ToolGroup>

      <Section title="Capability Options">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-left text-gray-400">
              <th className="pb-2 pr-4 font-medium">Capability</th>
              <th className="pb-2 font-medium">Effect</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {[
              ["listen", "Receive transcript in real time (default)"],
              ["transcribe", "Buffer transcript segments (default)"],
              ["text_only", "No audio processing — text channels only"],
              ["voice", "Full audio input/output (requires TTS/STT setup)"],
              ["tts_enabled", "Text-to-speech output for agent responses"],
            ].map(([cap, desc]) => (
              <tr key={cap}>
                <td className="py-2 pr-4">
                  <Code>{cap}</Code>
                </td>
                <td className="py-2 text-gray-400">{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  );
}

function TestingScenarios() {
  const [open, setOpen] = useState<number | null>(0);

  const scenarios = [
    {
      title: "Scenario 1: Basic Meeting Lifecycle",
      goal: "Create a meeting, join it, read participants, and leave cleanly.",
      steps: [
        {
          label: "Register & get API key",
          detail:
            "Sign up at convene.spark-b0f2.local. Go to Settings → API Keys and create a key starting with cvn_.",
        },
        {
          label: "Configure MCP in settings.json",
          detail: `Add to ~/.claude/settings.json:\n{\n  "mcpServers": {\n    "convene": {\n      "type": "streamableHttp",\n      "url": "https://convene.spark-b0f2.local/mcp",\n      "headers": { "Authorization": "Bearer cvn_YOUR_KEY" }\n    }\n  }\n}`,
        },
        {
          label: "Create and join a meeting",
          detail:
            'In Claude Code: "Create a meeting called Test Meeting and join it." Verify the response includes a meeting_id and participant count.',
        },
        {
          label: "Get participants & status",
          detail:
            '"Who is in the meeting?" → calls get_participants(). Check your agent appears in the list.',
        },
        {
          label: "Leave the meeting",
          detail: '"Leave the meeting." → calls leave_meeting(). Verify clean exit.',
        },
      ],
      expected:
        "Meeting created, agent joins as participant, status reflects joined state, clean leave.",
    },
    {
      title: "Scenario 2: Turn Management",
      goal:
        "Exercise the full raise → wait → speak → finish turn management flow.",
      steps: [
        {
          label: "Join an active meeting",
          detail:
            '"Join the Test Meeting." Confirm joined with capabilities: listen, transcribe.',
        },
        {
          label: "Raise hand",
          detail:
            '"Raise my hand to discuss the project update." → calls raise_hand(meeting_id, topic="project update"). Check queue_position.',
        },
        {
          label: "Check queue status",
          detail:
            '"Who\'s in the queue?" → calls get_queue_status(). Verify your agent is listed.',
        },
        {
          label: "Start speaking",
          detail:
            '"Start speaking." → calls start_speaking(). Confirm floor is granted.',
        },
        {
          label: "Finish speaking",
          detail:
            '"Done speaking." → calls mark_finished_speaking(). Queue should advance.',
        },
      ],
      expected:
        "Agent enters queue, gets the floor in order, releases floor properly.",
    },
    {
      title: "Scenario 3: Chat & Tasks",
      goal:
        "Send chat messages and create action items from meeting context.",
      steps: [
        {
          label: "Join meeting",
          detail: "Join an active or newly created meeting.",
        },
        {
          label: "Send a text message",
          detail:
            '"Send a chat: I\'ll review the API changes by EOD." → calls send_chat_message with type=text.',
        },
        {
          label: "Send an action item",
          detail:
            '"Create an action item: Review PR #42 before Friday, high priority." → calls create_task.',
        },
        {
          label: "Read chat history",
          detail:
            '"Show me the chat history." → calls get_chat_messages(). Verify your messages appear.',
        },
        {
          label: "Read tasks",
          detail:
            '"What are the action items?" → calls get_tasks(). Verify task was created.',
        },
      ],
      expected:
        "Messages and tasks visible in meeting context. Task appears in dashboard.",
    },
    {
      title: "Scenario 4: Claude Code Channel Integration",
      goal:
        "Subscribe to a channel, publish events, and read them back — for custom agent coordination.",
      steps: [
        {
          label: "Join meeting",
          detail: "Join an active meeting.",
        },
        {
          label: "Subscribe to a channel",
          detail:
            '"Subscribe to the dev-updates channel." → calls subscribe_channel("dev-updates").',
        },
        {
          label: "Publish an event",
          detail:
            '"Publish to dev-updates: {\\\"type\\\": \\\"build_complete\\\", \\\"status\\\": \\\"pass\\\"}" → calls publish_to_channel.',
        },
        {
          label: "Read channel messages",
          detail:
            '"Get the last 10 dev-updates messages." → calls get_channel_messages("dev-updates", last_n=10).',
        },
        {
          label: "Verify in meeting events",
          detail: '"Get recent meeting events." → calls get_meeting_events(). Channel events appear in the stream.',
        },
      ],
      expected:
        "Custom events flow through channels and appear in the meeting event stream.",
    },
  ];

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Testing Scenarios</h1>
        <p className="mt-2 text-gray-400">
          Four end-to-end walkthroughs covering the full Convene AI feature set.
          Run these in order for a complete system verification.
        </p>
      </div>

      <div className="space-y-3">
        {scenarios.map((s, i) => (
          <div
            key={i}
            className="rounded-xl border border-gray-800 overflow-hidden"
          >
            <button
              onClick={() => setOpen(open === i ? null : i)}
              className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-gray-900/50 transition-colors"
            >
              <div>
                <span className="text-sm font-semibold text-white">
                  {s.title}
                </span>
                <p className="mt-0.5 text-sm text-gray-400">{s.goal}</p>
              </div>
              <ChevronIcon open={open === i} />
            </button>

            {open === i && (
              <div className="border-t border-gray-800 px-5 py-4 space-y-4">
                <div className="space-y-3">
                  {s.steps.map((step, j) => (
                    <div key={j} className="flex gap-3">
                      <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-600/20 text-xs font-bold text-blue-400">
                        {j + 1}
                      </div>
                      <div>
                        <p className="text-sm font-medium text-white">
                          {step.label}
                        </p>
                        {step.detail.includes("\n") ? (
                          <pre className="mt-1.5 rounded-lg bg-gray-900 p-3 text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
                            {step.detail}
                          </pre>
                        ) : (
                          <p className="mt-0.5 text-sm text-gray-400">
                            {step.detail}
                          </p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="rounded-lg border border-green-800/50 bg-green-950/30 px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-green-500 mb-1">
                    Expected result
                  </p>
                  <p className="text-sm text-green-300">{s.expected}</p>
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ClaudeCodeSetup() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">Claude Code Setup</h1>
        <p className="mt-2 text-gray-400">
          Connect Claude Code to Convene AI via the MCP server. Once configured,
          Claude joins and participates in meetings naturally from within a
          coding session.
        </p>
      </div>

      <Section title="Prerequisites">
        <ul className="list-disc list-inside space-y-1 text-gray-400 text-sm">
          <li>
            Claude Code CLI installed (<Code>npm install -g @anthropic-ai/claude-code</Code>)
          </li>
          <li>
            Convene account and API key (<Code>cvn_...</Code>) from the dashboard
          </li>
        </ul>
      </Section>

      <Section title="Option A — settings.json (recommended)">
        <p>Edit <Code>~/.claude/settings.json</Code>:</p>
        <CodeBlock>{`{
  "mcpServers": {
    "convene": {
      "type": "streamableHttp",
      "url": "https://convene.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer \${CONVENE_API_KEY}"
      }
    }
  }
}`}</CodeBlock>
        <p>Then export your key in your shell profile:</p>
        <CodeBlock>{`export CONVENE_API_KEY=cvn_your_key_here`}</CodeBlock>
      </Section>

      <Section title="Option B — Install the skill">
        <p>
          Copy the skill file to Claude Code. The skill activates automatically
          when you mention meetings, standups, or transcripts.
        </p>
        <CodeBlock>{`mkdir -p ~/.claude/skills/convene-meeting
cp skills/convene-meeting/SKILL.md ~/.claude/skills/convene-meeting/`}</CodeBlock>
      </Section>

      <Section title="Option C — connect.sh (quick join)">
        <p>For one-off meeting joins without modifying settings:</p>
        <CodeBlock>{`export CONVENE_API_KEY=cvn_...
export CONVENE_URL=https://convene.spark-b0f2.local

./scripts/connect.sh "Daily Standup"       # join by title
./scripts/connect.sh --id <meeting-uuid>   # join by ID`}</CodeBlock>
      </Section>

      <Section title="Usage Examples">
        <p className="text-gray-400 text-sm mb-3">
          Once configured, speak naturally in Claude Code:
        </p>
        <CodeBlock>{`"Join the standup meeting"
→ join_or_create_meeting("Daily Standup")

"What's being discussed right now?"
→ get_transcript(last_n=20)

"Raise my hand to ask about the API change"
→ raise_hand(meeting_id, topic="API change question")

"Send a chat: I'll look into the auth bug"
→ send_chat_message(meeting_id, "I'll look into the auth bug")

"Create an action item: Review PR #42 before Friday"
→ create_task(meeting_id, "Review PR #42 before Friday", priority="high")`}</CodeBlock>
      </Section>

      <Section title="Verify Connection">
        <CodeBlock>{`# In Claude Code
"Check if the Convene MCP server is available"
→ Claude will call convene_list_meetings() and return meeting list`}</CodeBlock>
        <Note>
          If you see an auth error, double-check your <Code>CONVENE_API_KEY</Code> is exported and starts with <Code>cvn_</Code>.
        </Note>
      </Section>
    </div>
  );
}

function OpenClawSetup() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-white">OpenClaw Setup</h1>
        <p className="mt-2 text-gray-400">
          The <Code>@convene/openclaw-plugin</Code> gives OpenClaw agents native
          Convene tools in any channel — Slack, WhatsApp, and more.
        </p>
      </div>

      <Section title="Installation">
        <CodeBlock>{`openclaw plugins install @convene/openclaw-plugin`}</CodeBlock>
      </Section>

      <Section title="Configuration">
        <p>Add to your OpenClaw <Code>config.yaml</Code>:</p>
        <CodeBlock>{`plugins:
  entries:
    convene:
      config:
        apiKey: "cvn_..."           # Your Convene API key
        mcpUrl: "https://convene.spark-b0f2.local/mcp"`}</CodeBlock>
      </Section>

      <Section title="Available Tools">
        <p className="text-sm text-gray-400 mb-3">
          All Convene tools are available to agents via the plugin:
        </p>
        <div className="space-y-4">
          <ToolSubGroup title="Meeting Management">
            {["convene_list_meetings", "convene_join_meeting", "convene_get_transcript", "convene_create_task", "convene_get_participants", "convene_create_meeting"].map(t => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
          <ToolSubGroup title="Turn Management">
            {["convene_raise_hand", "convene_start_speaking", "convene_mark_finished_speaking", "convene_get_queue_status", "convene_cancel_hand_raise"].map(t => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
          <ToolSubGroup title="Chat">
            {["convene_send_chat_message", "convene_get_chat_messages"].map(t => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
        </div>
      </Section>

      <Section title="Turn Workflow">
        <CodeBlock>{`convene_raise_hand(meeting_id, topic="...")
  → queue_position=0: floor is yours immediately
  → queue_position>0: wait for turn_your_turn event

convene_start_speaking(meeting_id)
[speak via send_chat_message or voice]
convene_mark_finished_speaking(meeting_id)`}</CodeBlock>
      </Section>

      <Section title="Verify">
        <p>Test the plugin by asking your agent in any channel:</p>
        <CodeBlock>{`@agent list my Convene meetings`}</CodeBlock>
        <Note>
          The agent calls <Code>convene_list_meetings</Code> and returns all available meetings.
        </Note>
      </Section>
    </div>
  );
}

/* ─── Shared UI primitives ────────────────────────────────────────────────── */

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold text-white border-b border-gray-800 pb-2">
        {title}
      </h2>
      <div className="space-y-2 text-sm text-gray-400">{children}</div>
    </section>
  );
}

function ToolGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <h2 className="text-base font-semibold text-white border-b border-gray-800 pb-2">
        {title}
      </h2>
      <div className="divide-y divide-gray-800/50">{children}</div>
    </section>
  );
}

function ToolRow({
  name,
  params,
  desc,
}: {
  name: string;
  params: string;
  desc: string;
}) {
  return (
    <div className="py-3 grid grid-cols-[1fr,2fr] gap-4 items-start">
      <div>
        <code className="text-xs font-mono text-blue-400">{name}</code>
        {params && (
          <p className="mt-0.5 text-xs text-gray-500 font-mono">{params}</p>
        )}
      </div>
      <p className="text-sm text-gray-400">{desc}</p>
    </div>
  );
}

function ToolSubGroup({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1.5">
        {title}
      </p>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

function IntegrationCard({
  title,
  badge,
  desc,
}: {
  title: string;
  badge: string;
  desc: string;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-white">{title}</span>
        <span className="rounded-md bg-blue-600/20 px-2 py-0.5 text-xs font-medium text-blue-400">
          {badge}
        </span>
      </div>
      <p className="text-xs text-gray-400">{desc}</p>
    </div>
  );
}

function Code({
  children,
  block,
}: {
  children: React.ReactNode;
  block?: boolean;
}) {
  if (block) {
    return (
      <span className="inline-block rounded-md bg-gray-900 border border-gray-800 px-2 py-0.5 text-xs font-mono text-blue-300">
        {children}
      </span>
    );
  }
  return (
    <code className="rounded-md bg-gray-900 px-1.5 py-0.5 text-xs font-mono text-blue-300">
      {children}
    </code>
  );
}

function CodeBlock({ children }: { children: string }) {
  return (
    <pre className="rounded-xl bg-gray-900 border border-gray-800 p-4 text-xs font-mono text-gray-300 overflow-x-auto whitespace-pre-wrap">
      {children}
    </pre>
  );
}

function Note({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-yellow-800/50 bg-yellow-950/20 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-yellow-500 mb-1">
        Note
      </p>
      <p className="text-sm text-yellow-200/80">{children}</p>
    </div>
  );
}

function InlineLink({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="text-blue-400 hover:text-blue-300 underline underline-offset-2"
    >
      {children}
    </button>
  );
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      className={cn(
        "h-4 w-4 text-gray-400 transition-transform",
        open && "rotate-180"
      )}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m19 9-7 7-7-7"
      />
    </svg>
  );
}
