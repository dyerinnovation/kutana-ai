import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";

type Section =
  | "getting-started"
  | "kutana-agents-overview"
  | "kutana-agents-basic"
  | "kutana-agents-pro"
  | "connecting-overview"
  | "mcp-server"
  | "claude-code-channel"
  | "openclaw-skill"
  | "agent-skill"
  | "cli"
  | "feeds-overview"
  | "feeds-slack"
  | "feeds-upcoming";

interface NavItem {
  id: Section;
  label: string;
  group?: string;
}

const sections: NavItem[] = [
  { id: "getting-started", label: "Getting Started" },
  { id: "kutana-agents-overview", label: "Overview", group: "Kutana Agents" },
  { id: "kutana-agents-basic", label: "Basic Agents", group: "Kutana Agents" },
  { id: "kutana-agents-pro", label: "Pro Agents", group: "Kutana Agents" },
  { id: "connecting-overview", label: "Overview", group: "Connecting Your Agent" },
  { id: "mcp-server", label: "MCP Server Reference", group: "Connecting Your Agent" },
  { id: "claude-code-channel", label: "Claude Code Channel", group: "Connecting Your Agent" },
  { id: "openclaw-skill", label: "OpenClaw", group: "Connecting Your Agent" },
  { id: "agent-skill", label: "Kutana Meeting Skill", group: "Connecting Your Agent" },
  { id: "cli", label: "CLI Reference", group: "Connecting Your Agent" },
  { id: "feeds-overview", label: "Overview", group: "Feeds" },
  { id: "feeds-slack", label: "Slack", group: "Feeds" },
  { id: "feeds-upcoming", label: "Coming Soon", group: "Feeds" },
];

/* ─── Collapsible section ───────────────────────────────────────────────── */

function Collapsible({ title, defaultOpen = false, children }: { title: string; defaultOpen?: boolean; children: React.ReactNode }) {
  return (
    <details open={defaultOpen} className="group rounded-lg border border-gray-800 bg-gray-900/30">
      <summary className="flex cursor-pointer items-center justify-between px-4 py-3 text-sm font-medium text-gray-200 hover:text-gray-50 transition-colors [&::-webkit-details-marker]:hidden">
        {title}
        <svg className="h-4 w-4 text-gray-500 transition-transform group-open:rotate-90" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="m9 5 7 7-7 7" />
        </svg>
      </summary>
      <div className="border-t border-gray-800 px-4 py-4">
        {children}
      </div>
    </details>
  );
}

/* ─── Page ──────────────────────────────────────────────────────────────── */

const SECTION_IDS = new Set<string>(sections.map((s) => s.id));

function sectionFromPath(pathname: string): Section {
  const match = pathname.match(/^\/docs\/(.+?)\/?$/);
  const slug = match?.[1];
  if (slug && SECTION_IDS.has(slug)) return slug as Section;
  return "getting-started";
}

export function DocsPage() {
  const location = useLocation();
  const navigate = useNavigate();
  const [active, setActiveState] = useState<Section>(() =>
    sectionFromPath(location.pathname)
  );

  useEffect(() => {
    setActiveState(sectionFromPath(location.pathname));
  }, [location.pathname]);

  const setActive = (s: Section) => {
    setActiveState(s);
    navigate(s === "getting-started" ? "/docs" : `/docs/${s}`);
  };

  // Ordered groups for sidebar rendering
  const groupOrder = ["Kutana Agents", "Connecting Your Agent", "Feeds"];
  const ungrouped = sections.filter((s) => !s.group);
  const groups = sections.reduce<Record<string, NavItem[]>>((acc, s) => {
    if (s.group) {
      (acc[s.group] ??= []).push(s);
    }
    return acc;
  }, {});

  return (
    <div className="flex gap-8 min-h-full">
      {/* Sidebar nav */}
      <aside className="w-52 shrink-0 hidden md:block">
        <nav className="sticky top-0 space-y-1">
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-gray-500">
            Documentation
          </p>

          {/* Getting Started (ungrouped) */}
          {ungrouped.map((s) => (
            <NavButton key={s.id} active={active === s.id} onClick={() => setActive(s.id)}>
              {s.label}
            </NavButton>
          ))}

          {/* Grouped sections in order */}
          {groupOrder.map((group) =>
            groups[group] ? (
              <div key={group} className="mt-4">
                <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-widest text-gray-600">
                  {group}
                </p>
                {groups[group].map((s) => (
                  <NavButton key={s.id} active={active === s.id} onClick={() => setActive(s.id)}>
                    {s.label}
                  </NavButton>
                ))}
              </div>
            ) : null
          )}
        </nav>
      </aside>

      {/* Mobile nav */}
      <div className="md:hidden w-full">
        <select
          value={active}
          onChange={(e) => setActive(e.target.value as Section)}
          className="w-full mb-4 rounded-lg bg-gray-900 border border-gray-800 px-3 py-2 text-sm text-gray-50"
        >
          {sections.map((s) => (
            <option key={s.id} value={s.id}>
              {s.group ? `${s.group} — ${s.label}` : s.label}
            </option>
          ))}
        </select>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 max-w-3xl">
        {active === "getting-started" && <GettingStarted onNavigate={setActive} />}
        {active === "kutana-agents-overview" && <KutanaAgentsOverview onNavigate={setActive} />}
        {active === "kutana-agents-basic" && <KutanaAgentsBasic />}
        {active === "kutana-agents-pro" && <KutanaAgentsPro />}
        {active === "connecting-overview" && <ConnectingOverview onNavigate={setActive} />}
        {active === "mcp-server" && <McpServerReference />}
        {active === "claude-code-channel" && <ClaudeCodeChannel />}
        {active === "openclaw-skill" && <OpenClawSetup />}
        {active === "agent-skill" && <KutanaMeetingSkill />}
        {active === "cli" && <CliReference />}
        {active === "feeds-overview" && <FeedsOverview />}
        {active === "feeds-slack" && <FeedsSlack />}
        {active === "feeds-upcoming" && <FeedsUpcoming />}
      </div>
    </div>
  );
}

/* ─── Nav button ─────────────────────────────────────────────────────────── */

function NavButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "w-full text-left rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        active
          ? "bg-gray-800 text-gray-50"
          : "text-gray-400 hover:bg-gray-900 hover:text-gray-50"
      )}
    >
      {children}
    </button>
  );
}

/* ─── Section components ──────────────────────────────────────────────────── */

/* ── Getting Started (5C) ────────────────────────────────────────────────── */

function GettingStarted({ onNavigate }: { onNavigate: (s: Section) => void }) {
  return (
    <div className="prose-dark space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Getting Started</h1>
        <p className="mt-2 text-gray-400">
          Welcome to Kutana — an agent-first meeting platform. AI agents join as
          first-class participants: they listen, speak, extract tasks, and
          maintain memory across meetings.
        </p>
      </div>

      <DocSection title="Run Your First Meeting">
        <ol className="list-decimal list-inside space-y-2 text-gray-400 text-sm">
          <li>
            Sign in to the dashboard at{" "}
            <Code>https://dev.kutana.ai</Code>.
          </li>
          <li>
            Go to <strong className="text-gray-50">Agents</strong> and enable
            the <strong className="text-gray-50">Transcript Agent</strong> — it
            captures everything said in the meeting.
          </li>
          <li>
            Click <strong className="text-gray-50">New Meeting</strong> from the
            dashboard, give it a title, and start the meeting.
          </li>
          <li>
            Watch the agent join automatically. It begins transcribing in real
            time and surfaces action items as they come up.
          </li>
        </ol>
      </DocSection>

      <DocSection title="Next Steps">
        <div className="mt-2 grid gap-4 sm:grid-cols-3">
          <IntegrationCard
            title="Explore Kutana Agents"
            desc="See all the pre-built agents available on the platform."
            onClick={() => onNavigate("kutana-agents-overview")}
          />
          <IntegrationCard
            title="Connect Your Own Agent"
            desc="Bring your own AI agent into meetings via MCP, Claude Code, or OpenClaw."
            onClick={() => onNavigate("connecting-overview")}
          />
          <IntegrationCard
            title="Set Up Feeds"
            desc="Push meeting recaps to Slack or pull context in before a meeting."
            onClick={() => onNavigate("feeds-overview")}
          />
        </div>
      </DocSection>
    </div>
  );
}

/* ── Kutana Agents Overview (5D) ─────────────────────────────────────────── */

function KutanaAgentsOverview({ onNavigate }: { onNavigate: (s: Section) => void }) {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Kutana Agents</h1>
        <p className="mt-2 text-gray-400">
          Kutana Agents are pre-built AI agents that run on the Kutana platform.
          They join meetings automatically and handle common tasks — no setup or
          external configuration required.
        </p>
      </div>

      <DocSection title="Two Tiers">
        <div className="grid gap-4 sm:grid-cols-2">
          <button
            onClick={() => onNavigate("kutana-agents-basic")}
            className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 text-left hover:border-gray-700 transition-colors"
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-semibold text-gray-50">Basic Agents</span>
              <span className="rounded-md bg-green-600/20 px-2 py-0.5 text-xs font-medium text-green-400">Basic</span>
            </div>
            <p className="text-xs text-gray-400">
              Core platform agents enabled by default for all users. Transcription,
              action items, and meeting summaries.
            </p>
          </button>
          <button
            onClick={() => onNavigate("kutana-agents-pro")}
            className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 text-left hover:border-gray-700 transition-colors"
          >
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm font-semibold text-gray-50">Pro Agents</span>
              <span className="rounded-md bg-blue-600/20 px-2 py-0.5 text-xs font-medium text-blue-400">Pro</span>
            </div>
            <p className="text-xs text-gray-400">
              Advanced agents with optional custom prompts for organizational best
              practices. Scrum Master, interviewer roles, and more.
            </p>
          </button>
        </div>
      </DocSection>
    </div>
  );
}

/* ── Basic Agents (5D) ───────────────────────────────────────────────────── */

function KutanaAgentsBasic() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Basic Agents</h1>
        <p className="mt-2 text-gray-400">
          Core platform agents enabled by default for all users. They handle the
          fundamentals so every meeting is captured and actionable.
        </p>
      </div>

      <AgentCard
        name="Transcript Agent"
        tier="Basic"
        tierColor="green"
        desc="Real-time transcription of meeting audio. Always active."
        howItWorks="Connects to the meeting audio stream and produces a live transcript with speaker attribution. Segments are available to all participants and other agents via the transcript API."
      />

      <AgentCard
        name="Action Item Agent"
        tier="Basic"
        tierColor="green"
        desc="Identifies commitments and action items from conversation. Creates tasks automatically."
        howItWorks="Monitors the transcript for language indicating commitments (deadlines, assignments, promises). Creates structured tasks with assignees and posts confirmations in the meeting chat."
      />

      <AgentCard
        name="Meeting Summary Agent"
        tier="Basic"
        tierColor="green"
        desc="Generates structured meeting summaries at the end of each meeting."
        howItWorks="When the meeting ends, reads the full transcript, extracts key discussion points, decisions, and open questions, then produces a formatted summary available in the dashboard and via Feeds."
      />
    </div>
  );
}

/* ── Pro Agents (5D) ─────────────────────────────────────────────────────── */

function KutanaAgentsPro() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Pro Agents</h1>
        <p className="mt-2 text-gray-400">
          Advanced agents with optional custom prompts for organizational best
          practices. Available on Pro plans and above.
        </p>
      </div>

      <AgentCard
        name="Scrum Master"
        tier="Pro"
        tierColor="blue"
        desc="Facilitates stand-ups and sprint ceremonies. Tracks blockers, action items, and time."
        howItWorks="Follows a structured agenda (yesterday, today, blockers). Keeps each participant on track with gentle time reminders, captures blockers as tasks, and posts a sprint summary at the end."
      />

      <AgentCard
        name="User Interviewer"
        tier="Pro"
        tierColor="blue"
        desc="Guides user research interviews. Captures insights, themes, and follow-up questions."
        howItWorks="Follows your interview script or generates questions based on a research goal. Tags responses by theme, captures verbatim quotes, and produces an insight summary with recommended follow-ups."
      />

      <AgentCard
        name="Candidate Interviewer"
        tier="Pro"
        tierColor="blue"
        desc="Structures technical and behavioral interviews. Tracks scoring criteria."
        howItWorks="Manages interview sections (intro, technical, behavioral, wrap-up). Records responses against your rubric, tracks time per section, and produces a structured scorecard for the hiring panel."
      />
    </div>
  );
}

/* ── Connecting Your Agent Overview (5E) ─────────────────────────────────── */

function ConnectingOverview({ onNavigate }: { onNavigate: (s: Section) => void }) {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Connecting Your Agent</h1>
        <p className="mt-2 text-gray-400">
          Bring your own AI agent into Kutana meetings. Your agent connects to the
          platform, joins meetings as a participant, and gets access to the full
          toolkit — turns, chat, transcript, and tasks.
        </p>
      </div>

      <DocSection title="Connection Methods">
        <div className="grid gap-4 sm:grid-cols-2">
          <IntegrationCard
            title="Claude Code Channel"
            desc="Real-time, push-based connection. Claude Code spawns a Kutana channel as a subprocess and receives live meeting events."
            onClick={() => onNavigate("claude-code-channel")}
          />
          <IntegrationCard
            title="OpenClaw Plugin"
            desc="Install the @kutana/openclaw-plugin to give any OpenClaw agent native Kutana meeting tools."
            onClick={() => onNavigate("openclaw-skill")}
          />
          <IntegrationCard
            title="MCP Server (Direct)"
            desc="Connect any MCP-compatible agent to the Kutana HTTP MCP server with Bearer token auth."
            onClick={() => onNavigate("mcp-server")}
          />
          <IntegrationCard
            title="CLI"
            desc="Terminal-based access to meetings, agents, and tasks via the kutana CLI."
            onClick={() => onNavigate("cli")}
          />
        </div>
      </DocSection>

      <DocSection title="Get an API Key">
        <p>
          All connection methods require a Kutana API key. Go to{" "}
          <strong className="text-gray-50">Settings &rarr; API Keys</strong> in
          the dashboard and generate a key with the{" "}
          <strong className="text-gray-50">Agent</strong> scope. Keys start with{" "}
          <Code>cvn_</Code>.
        </p>
        <Note>
          Keep your API key secret. It grants full agent access to your meetings.
        </Note>
      </DocSection>
    </div>
  );
}

/* ── MCP Server Reference ────────────────────────────────────────────────── */

function McpServerReference() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">MCP Server Reference</h1>
        <p className="mt-2 text-gray-400">
          All tools are prefixed with <Code>kutana_</Code> and available via
          the MCP server. Tools require an active meeting join unless noted.
        </p>
      </div>

      <DocSection title="Adding the MCP Server">
        <p>
          Add the Kutana MCP server to your agent&apos;s configuration. The server
          uses streamable HTTP transport with Bearer token authentication:
        </p>
        <CodeBlock>{`{
  "mcpServers": {
    "kutana": {
      "type": "streamableHttp",
      "url": "https://kutana.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer \${KUTANA_API_KEY}"
      }
    }
  }
}`}</CodeBlock>
      </DocSection>

      <Collapsible title="Meeting Lifecycle Tools" defaultOpen>
        <ToolGroup title="Meeting Lifecycle">
          <ToolRow
            name="kutana_list_meetings"
            params=""
            desc="List all meetings with status (scheduled, active, ended). No join required."
          />
          <ToolRow
            name="kutana_join_meeting"
            params="meeting_id, capabilities?"
            desc="Join a meeting. capabilities: ['listen','transcribe','text_only','voice','tts_enabled']"
          />
          <ToolRow
            name="kutana_join_or_create_meeting"
            params="title, capabilities?"
            desc="Join an active meeting by title, or create a new one if none found."
          />
          <ToolRow
            name="kutana_leave_meeting"
            params=""
            desc="Leave the current meeting."
          />
          <ToolRow
            name="kutana_create_meeting"
            params="title, description?, scheduled_start?"
            desc="Create a new meeting. Returns meeting_id."
          />
          <ToolRow
            name="kutana_start_meeting"
            params="meeting_id"
            desc="Start a scheduled meeting (transitions to active)."
          />
          <ToolRow
            name="kutana_end_meeting"
            params="meeting_id"
            desc="End an active meeting."
          />
          <ToolRow
            name="kutana_get_meeting_status"
            params="meeting_id"
            desc="Get current status, turn queue, participants, and recent chat."
          />
        </ToolGroup>
      </Collapsible>

      <Collapsible title="Transcript & Participants Tools">
        <ToolGroup title="Transcript &amp; Participants">
          <ToolRow
            name="kutana_get_transcript"
            params="last_n?"
            desc="Get recent transcript segments (default: 50). Must be joined."
          />
          <ToolRow
            name="kutana_get_participants"
            params=""
            desc="List all current participants with roles and capabilities."
          />
          <ToolRow
            name="kutana_get_meeting_events"
            params="last_n?, event_type?"
            desc="Poll meeting events. Use event_type='turn_your_turn' to wait for the floor."
          />
        </ToolGroup>
      </Collapsible>

      <Collapsible title="Turn Management, Chat, Tasks & Channels Tools">
        <ToolGroup title="Turn Management">
          <p className="text-sm text-gray-400 pb-2">
            Raise &rarr; wait &rarr; start_speaking &rarr; speak &rarr; mark_finished_speaking
          </p>
          <ToolRow
            name="kutana_raise_hand"
            params="meeting_id, topic?"
            desc="Enter the speaker queue. queue_position=0 means floor is yours immediately."
          />
          <ToolRow
            name="kutana_start_speaking"
            params="meeting_id"
            desc="Confirm you have the floor and begin your turn."
          />
          <ToolRow
            name="kutana_mark_finished_speaking"
            params="meeting_id"
            desc="Release the floor. Advances the queue to the next speaker."
          />
          <ToolRow
            name="kutana_cancel_hand_raise"
            params="meeting_id"
            desc="Withdraw from the speaker queue without speaking."
          />
          <ToolRow
            name="kutana_get_queue_status"
            params="meeting_id"
            desc="See current speaker and waiting queue."
          />
          <ToolRow
            name="kutana_get_speaking_status"
            params="meeting_id"
            desc="Check if it's your turn and the current queue state."
          />
        </ToolGroup>

        <ToolGroup title="Chat">
          <ToolRow
            name="kutana_send_chat_message"
            params="meeting_id, content, message_type?"
            desc="Send a message. message_type: text | question | action_item | decision"
          />
          <ToolRow
            name="kutana_get_chat_messages"
            params="meeting_id, limit?, message_type?"
            desc="Get chat history. Filter by message_type."
          />
        </ToolGroup>

        <ToolGroup title="Tasks">
          <ToolRow
            name="kutana_get_tasks"
            params="meeting_id"
            desc="Get all tasks/action items for a meeting. No join required."
          />
          <ToolRow
            name="kutana_create_task"
            params="meeting_id, description, priority?, assignee?"
            desc="Create a task. priority: low | medium | high"
          />
        </ToolGroup>

        <ToolGroup title="Channels">
          <ToolRow
            name="kutana_subscribe_channel"
            params="channel"
            desc="Subscribe to a named channel for custom pub/sub events."
          />
          <ToolRow
            name="kutana_publish_to_channel"
            params="channel, payload"
            desc="Publish a JSON payload to a channel."
          />
          <ToolRow
            name="kutana_get_channel_messages"
            params="channel, last_n?"
            desc="Read recent messages from a channel."
          />
        </ToolGroup>
      </Collapsible>

      <Collapsible title="Capability Options">
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
      </Collapsible>

      <Collapsible title="Code Example">
        <CodeBlock>{`// Example: Join a meeting and read the transcript
const response = await mcpClient.callTool("kutana_list_meetings", {});
const meetings = JSON.parse(response.content);

const active = meetings.find(m => m.status === "active");
await mcpClient.callTool("kutana_join_meeting", {
  meeting_id: active.id,
  capabilities: ["listen", "transcribe"]
});

const transcript = await mcpClient.callTool("kutana_get_transcript", {
  last_n: 20
});`}</CodeBlock>
      </Collapsible>
    </div>
  );
}

/* ── Claude Code Channel (5F — rewritten) ────────────────────────────────── */

function ClaudeCodeChannel() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Claude Code Channel</h1>
        <p className="mt-2 text-gray-400">
          A real-time, push-based connection between Claude Code and Kutana
          meetings. The channel runs as a stdio MCP subprocess and delivers live
          meeting events directly into your Claude Code session.
        </p>
      </div>

      <DocSection title="What Is a Claude Code Channel?">
        <p>
          Claude Code Channels are <strong className="text-gray-50">stdio-transport MCP servers</strong> spawned
          as subprocesses by Claude Code. Unlike standard MCP servers (which Claude
          Code calls on demand), a channel declares the{" "}
          <Code>claude/channel</Code> capability and <strong className="text-gray-50">pushes</strong> events
          into the session via <Code>notifications/claude/channel</Code> messages.
        </p>
        <p>
          Events arrive in Claude&apos;s context as XML tags:
        </p>
        <CodeBlock>{`<channel source="kutana-ai" topic="transcript" type="transcript_segment">
[2.0s-4.5s] Alice: We should finalize the API spec by Thursday.
</channel>`}</CodeBlock>
        <p>
          This means Claude Code receives live transcript, chat messages, turn
          updates, and extracted insights (tasks, decisions, questions) without
          polling — they push in automatically.
        </p>
      </DocSection>

      <DocSection title="Prerequisites">
        <ul className="list-disc list-inside space-y-1 text-gray-400 text-sm">
          <li>
            Claude Code CLI installed (<Code>npm install -g @anthropic-ai/claude-code</Code>)
          </li>
          <li>
            Kutana account and API key (<Code>cvn_...</Code>) from the dashboard
          </li>
        </ul>
      </DocSection>

      <DocSection title="Installation">
        <p>
          Register the channel using the <Code>claude mcp add-json</Code> CLI
          command. Do <strong className="text-gray-50">not</strong> edit{" "}
          <Code>~/.claude/settings.json</Code> manually — the{" "}
          <Code>--dangerously-load-development-channels</Code> flag only finds
          servers in the managed registry.
        </p>
        <CodeBlock>{`claude mcp add-json --scope user kutana-ai '{
  "type": "stdio",
  "command": "npx",
  "args": ["@kutana/channel"],
  "env": {
    "KUTANA_API_KEY": "cvn_your_key_here",
    "KUTANA_API_URL": "wss://kutana.spark-b0f2.local/ws",
    "KUTANA_HTTP_URL": "https://kutana.spark-b0f2.local"
  }
}'`}</CodeBlock>
        <p>Then launch Claude Code with the channel enabled:</p>
        <CodeBlock>{`claude --dangerously-load-development-channels server:kutana-ai`}</CodeBlock>
        <Note>
          The <Code>--dangerously-load-development-channels</Code> flag is
          required during the research preview for custom channels. Without it,
          tools load but push events are silently dropped.
        </Note>
      </DocSection>

      <DocSection title="How It Works">
        <p>The channel follows a lifecycle:</p>
        <ol className="list-decimal list-inside space-y-2 text-gray-400 text-sm">
          <li>
            <strong className="text-gray-50">Startup</strong> — Plugin
            authenticates with the API (API key to JWT). Tools and resources
            register. No meeting joined yet.
          </li>
          <li>
            <strong className="text-gray-50">Discovery</strong> — Call{" "}
            <Code>list_meetings</Code> or browse{" "}
            <Code>kutana://meeting/&#123;id&#125;</Code> resources.
          </li>
          <li>
            <strong className="text-gray-50">Join</strong> — Call{" "}
            <Code>join_meeting</Code>. A WebSocket opens and events begin
            pushing via <Code>{"notifications/claude/channel"}</Code>.
          </li>
          <li>
            <strong className="text-gray-50">Active</strong> — All 18 tools
            available. Transcript, chat, turn, and insight events flow as{" "}
            <Code>{"<channel>"}</Code> tags.
          </li>
          <li>
            <strong className="text-gray-50">Leave</strong> — Call{" "}
            <Code>leave_meeting</Code>. WebSocket closes, buffers clear.
          </li>
        </ol>
      </DocSection>

      <Collapsible title="Available Tools (18 total)" defaultOpen>
        <div className="space-y-4">
          <ToolSubGroup title="Lobby (no meeting required)">
            {["list_meetings", "join_meeting", "create_meeting", "join_or_create_meeting"].map((t) => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
          <ToolSubGroup title="Meeting (require active meeting)">
            {[
              "leave_meeting", "reply", "get_chat_messages", "accept_task",
              "update_status", "raise_hand", "get_queue_status",
              "mark_finished_speaking", "cancel_hand_raise", "get_speaking_status",
              "get_participants", "request_context", "get_meeting_recap",
              "get_entity_history",
            ].map((t) => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
        </div>
      </Collapsible>

      <Collapsible title="Channel Event Types">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-left text-gray-400">
              <th className="pb-2 pr-4 font-medium">Gateway Event</th>
              <th className="pb-2 pr-4 font-medium">Channel Topic</th>
              <th className="pb-2 font-medium">Channel Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {[
              ["transcript", "transcript", "transcript_segment"],
              ["data.channel.insights.*", "insight", "Entity type (task, decision, etc.)"],
              ["data.channel.chat", "chat", "chat_message"],
              ["turn.queue.updated", "turn", "queue_updated"],
              ["turn.speaker.changed", "turn", "speaker_changed"],
              ["turn.your_turn", "turn", "your_turn"],
              ["participant_update", "participant", "joined / left"],
            ].map(([event, topic, type]) => (
              <tr key={event}>
                <td className="py-2 pr-4"><Code>{event}</Code></td>
                <td className="py-2 pr-4 text-gray-400">{topic}</td>
                <td className="py-2 text-gray-400">{type}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Collapsible>

      <DocSection title="Usage">
        <p className="text-gray-400 text-sm mb-3">
          Once the channel is running, speak naturally in Claude Code:
        </p>
        <CodeBlock>{`"Join the standup meeting"
→ join_or_create_meeting("Daily Standup")

"What's being discussed?"
→ Transcript events are already streaming — Claude reads them directly

"Raise my hand to ask about the API rollout"
→ raise_hand(topic="API rollout timeline")

"Send a message: I'll handle the auth bug"
→ reply("I'll handle the auth bug")

"What tasks came out of this meeting?"
→ get_meeting_recap()`}</CodeBlock>
      </DocSection>

      <DocSection title="Verify Connection">
        <CodeBlock>{`# In Claude Code (with channel running)
"List available Kutana meetings"
→ Claude calls list_meetings() and returns the meeting list`}</CodeBlock>
        <Note>
          If you see an auth error, verify your <Code>KUTANA_API_KEY</Code> in the
          registration JSON starts with <Code>cvn_</Code>.
        </Note>
      </DocSection>
    </div>
  );
}

/* ── OpenClaw Setup (5G — rewritten) ─────────────────────────────────────── */

function OpenClawSetup() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">OpenClaw Plugin</h1>
        <p className="mt-2 text-gray-400">
          The <Code>@kutana/openclaw-plugin</Code> registers native Kutana
          meeting tools in the OpenClaw gateway, allowing any OpenClaw agent to
          join meetings, read transcripts, manage turns, and create tasks.
        </p>
      </div>

      <DocSection title="Prerequisites">
        <ul className="list-disc list-inside space-y-1 text-gray-400 text-sm">
          <li>OpenClaw 0.9 or later</li>
          <li>
            A Kutana API key (<Code>cvn_...</Code>) — generate one from{" "}
            <strong className="text-gray-50">Settings &rarr; API Keys</strong> with
            the <strong className="text-gray-50">Agent</strong> scope
          </li>
        </ul>
      </DocSection>

      <DocSection title="Installation">
        <CodeBlock>{`openclaw plugins install @kutana/openclaw-plugin`}</CodeBlock>
      </DocSection>

      <DocSection title="Configuration">
        <p>Add to your OpenClaw <Code>config.yaml</Code>:</p>
        <CodeBlock>{`plugins:
  entries:
    kutana:
      config:
        apiKey: "cvn_..."                              # your Kutana API key
        mcpUrl: "https://kutana.spark-b0f2.local/mcp"  # your Kutana instance URL`}</CodeBlock>
      </DocSection>

      <DocSection title="Available Tools (17)">
        <p className="text-sm text-gray-400 mb-3">
          The plugin registers the following tools in the OpenClaw gateway:
        </p>
        <div className="space-y-4">
          <ToolSubGroup title="Meeting Management">
            {[
              "kutana_list_meetings",
              "kutana_create_meeting",
              "kutana_join_meeting",
              "kutana_leave_meeting",
              "kutana_get_transcript",
              "kutana_get_participants",
              "kutana_create_task",
              "kutana_get_meeting_status",
            ].map((t) => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
          <ToolSubGroup title="Turn Management">
            {[
              "kutana_raise_hand",
              "kutana_start_speaking",
              "kutana_speak",
              "kutana_mark_finished_speaking",
              "kutana_cancel_hand_raise",
              "kutana_get_queue_status",
              "kutana_get_speaking_status",
            ].map((t) => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
          <ToolSubGroup title="Chat">
            {["kutana_send_chat_message", "kutana_get_chat_messages"].map((t) => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
        </div>
      </DocSection>

      <DocSection title="How It Works">
        <p>
          The plugin connects to the Kutana MCP server via HTTP with Bearer token
          authentication. When an OpenClaw agent invokes a Kutana tool, the plugin
          forwards the call to the MCP server and returns the result to the agent.
        </p>
        <CodeBlock>{`OpenClaw Agent
    │  Native tool calls
    ▼
@kutana/openclaw-plugin
    │  HTTP + Bearer token (JSON-RPC 2.0)
    ▼
Kutana MCP Server`}</CodeBlock>
      </DocSection>

      <DocSection title="Capabilities">
        <p>
          Pass a <Code>capabilities</Code> array to <Code>kutana_join_meeting</Code> to
          control what the agent can do:
        </p>
        <table className="w-full text-sm mt-2">
          <thead>
            <tr className="border-b border-gray-800 text-left text-gray-400">
              <th className="pb-2 pr-4 font-medium">Capability</th>
              <th className="pb-2 font-medium">Effect</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {[
              ["text_only", "Transcript and chat only — no audio processing (default)"],
              ["tts_enabled", "Agent can speak via text-to-speech"],
              ["voice", "Bidirectional raw PCM16 audio via the sidecar WebSocket (advanced)"],
            ].map(([cap, desc]) => (
              <tr key={cap}>
                <td className="py-2 pr-4"><Code>{cap}</Code></td>
                <td className="py-2 text-gray-400">{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </DocSection>

      <DocSection title="Turn Workflow">
        <CodeBlock>{`kutana_raise_hand(meeting_id, topic="...")
  → queue_position=0: floor is yours immediately
  → queue_position>0: wait, poll with kutana_get_queue_status

kutana_start_speaking(meeting_id)
kutana_speak(meeting_id, text="What I want to say...")
kutana_mark_finished_speaking(meeting_id)`}</CodeBlock>
      </DocSection>

      <DocSection title="Verify">
        <p>Test the plugin by asking your agent:</p>
        <CodeBlock>{`@agent list my Kutana meetings`}</CodeBlock>
        <Note>
          The agent calls <Code>kutana_list_meetings</Code> and returns all
          available meetings.
        </Note>
      </DocSection>
    </div>
  );
}

/* ── Kutana Meeting Skill (5H — rewritten) ───────────────────────────────── */

function KutanaMeetingSkill() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Kutana Meeting Skill</h1>
        <p className="mt-2 text-gray-400">
          The <Code>kutana-meeting</Code> skill is a{" "}
          <Code>SKILL.md</Code> file that gives Claude Code agents natural
          language instructions for participating in Kutana meetings. It activates
          automatically when you mention meetings, standups, or transcripts.
        </p>
      </div>

      <DocSection title="What Is a Skill?">
        <p>
          A skill is a <Code>SKILL.md</Code> file placed in your agent&apos;s
          skills directory. It contains structured instructions that Claude Code
          loads when a trigger phrase is detected — like mentioning a meeting,
          standup, or action items.
        </p>
      </DocSection>

      <DocSection title="Installation">
        <p>Copy the skill file to your Claude Code skills directory:</p>
        <CodeBlock>{`mkdir -p ~/.claude/skills/kutana-meeting
cp skills/kutana-meeting/SKILL.md ~/.claude/skills/kutana-meeting/`}</CodeBlock>
        <p>
          The skill activates automatically when you mention meetings, standups,
          calls, hand raises, speakers, transcripts, action items, or ask to join
          a meeting.
        </p>
        <Note>
          The skill requires the Kutana MCP server to be configured. See the{" "}
          <strong className="text-gray-50">MCP Server Reference</strong> for
          setup instructions.
        </Note>
      </DocSection>

      <DocSection title="What It Provides">
        <div className="space-y-4">
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
            <span className="text-sm font-semibold text-gray-50">Meeting Lifecycle</span>
            <p className="mt-1 text-xs text-gray-400">
              Join meetings by title or ID, create new meetings, get meeting status,
              and leave when done. The skill teaches agents to use{" "}
              <Code>join_or_create_meeting</Code> for flexible joining.
            </p>
          </div>
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
            <span className="text-sm font-semibold text-gray-50">Turn Management</span>
            <p className="mt-1 text-xs text-gray-400">
              Raise hand to enter the speaker queue, wait for your turn, confirm
              the floor, speak, and release. The skill covers the full raise
              &rarr; wait &rarr; start_speaking &rarr; finish flow.
            </p>
          </div>
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
            <span className="text-sm font-semibold text-gray-50">Chat &amp; Transcript</span>
            <p className="mt-1 text-xs text-gray-400">
              Send typed chat messages (text, questions, action items, decisions),
              read chat history, get transcript segments, and list participants.
            </p>
          </div>
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
            <span className="text-sm font-semibold text-gray-50">Tasks &amp; Context</span>
            <p className="mt-1 text-xs text-gray-400">
              Create tasks with priority and description, browse meetings without
              joining, and understand capability options like{" "}
              <Code>listen</Code>, <Code>transcribe</Code>, and{" "}
              <Code>tts_enabled</Code>.
            </p>
          </div>
        </div>
      </DocSection>

      <DocSection title="Trigger Phrases">
        <p>
          The skill activates when your agent detects relevant context:
        </p>
        <div className="flex flex-wrap gap-2 mt-2">
          {["meeting", "kutana", "standup", "call", "hand raise", "speaker", "transcript", "action items", "join meeting"].map((t) => (
            <Code key={t} block>{t}</Code>
          ))}
        </div>
      </DocSection>
    </div>
  );
}

/* ── CLI Reference (5K — with subsection anchors) ────────────────────────── */

function CliReference() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">CLI Reference</h1>
        <p className="mt-2 text-gray-400">
          The <Code>kutana</Code> CLI wraps the Kutana REST API for
          terminal-based access to meetings, agents, and tasks.
        </p>
      </div>

      <DocSection title="Quick Install">
        <h3 id="cli-install" className="sr-only">Install</h3>
        <CodeBlock>{`curl -LsSf https://kutana.ai/install.sh | bash`}</CodeBlock>
        <p>
          This installs <Code>git</Code> and <Code>uv</Code> if needed,
          clones the repository, and adds <Code>kutana</Code> to your PATH.
        </p>
      </DocSection>

      <DocSection title="Install from Source">
        <CodeBlock>{`git clone https://github.com/dyerinnovation/kutana-ai.git
cd kutana-ai
uv tool install -e services/cli`}</CodeBlock>
      </DocSection>

      <DocSection title="Authentication">
        <h3 id="cli-auth" className="sr-only">Authentication</h3>
        <CodeBlock>{`# Login with email/password
kutana login

# Credentials stored in ~/.kutana/config.json`}</CodeBlock>
      </DocSection>

      <DocSection title="Commands">
        <h3 id="cli-commands" className="sr-only">Commands</h3>
        <ToolGroup title="Meetings">
          <ToolRow name="kutana meetings list" params="" desc="List all meetings with status." />
          <ToolRow name="kutana meetings create" params='"Sprint Planning"' desc="Create a new meeting with the given title." />
          <ToolRow name="kutana meetings start" params="<meeting-id>" desc="Start a scheduled meeting." />
          <ToolRow name="kutana meetings end" params="<meeting-id>" desc="End an active meeting." />
        </ToolGroup>

        <ToolGroup title="Agents">
          <ToolRow name="kutana agents list" params="" desc="List your registered agents." />
          <ToolRow name="kutana agents create" params='"name" --capabilities listen,transcribe' desc="Create an agent with capabilities." />
        </ToolGroup>

        <ToolGroup title="API Keys">
          <ToolRow name="kutana keys generate" params="<agent-id> --name my-key" desc="Generate an API key for an agent." />
        </ToolGroup>

        <ToolGroup title="Configuration">
          <ToolRow name="kutana config show" params="" desc="Display current configuration." />
          <ToolRow name="kutana config set" params="api_url <url>" desc="Set the API server URL." />
        </ToolGroup>
      </DocSection>

      <DocSection title="Configuration File">
        <h3 id="cli-config" className="sr-only">Configuration</h3>
        <p>Stored at <Code>~/.kutana/config.json</Code>:</p>
        <CodeBlock>{`{
  "api_url": "https://api-dev.kutana.ai",
  "token": "<jwt-token>",
  "email": "user@example.com"
}`}</CodeBlock>
      </DocSection>
    </div>
  );
}

/* ── Feeds Overview (5I) ─────────────────────────────────────────────────── */

function FeedsOverview() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Feeds</h1>
        <p className="mt-2 text-gray-400">
          Feeds are integrations that connect your Kutana meetings to external
          platforms. Pull context in before a meeting starts, or push it out
          when it ends as enriched meeting context.
        </p>
      </div>

      <DocSection title="How It Works">
        <p>
          At the beginning and end of a meeting, Kutana automatically runs your
          configured Feeds. Each Feed is a short-lived AI agent that reads
          meeting data and delivers it to your chosen platform — or pulls
          external context into the meeting.
        </p>
        <ul className="list-disc list-inside space-y-2 text-gray-400 text-sm mt-3">
          <li>
            <strong className="text-gray-50">Inbound (Pull)</strong> — Before a
            meeting starts, a Feed agent fetches relevant context — a Slack
            thread, Notion page, or GitHub issue — and injects it into the
            meeting so participants are prepared.
          </li>
          <li>
            <strong className="text-gray-50">Outbound (Push)</strong> — After a
            meeting ends, a Feed agent reads the summary, tasks, and transcript,
            then posts a formatted recap to Slack or other destinations.
          </li>
        </ul>
      </DocSection>

      <DocSection title="Examples">
        <div className="space-y-3">
          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
            <p className="text-sm font-medium text-gray-50">Inbound: Slack Thread</p>
            <p className="text-xs text-gray-400 mt-1">
              Before a sprint planning meeting, pull the latest #engineering thread
              so the team starts with full context on recent discussions.
            </p>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
            <p className="text-sm font-medium text-gray-50">Outbound: Slack Recap</p>
            <p className="text-xs text-gray-400 mt-1">
              After a standup ends, post a summary with action items and blockers
              to the #standup-notes channel.
            </p>
          </div>
        </div>
      </DocSection>

      <DocSection title="Data Types">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-left text-gray-400">
              <th className="pb-2 pr-4 font-medium">Data Type</th>
              <th className="pb-2 font-medium">Description</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {[
              ["Summary", "Key discussion points, decisions, and meeting overview"],
              ["Tasks", "Action items with assignees and deadlines"],
              ["Transcript", "Full or condensed meeting transcript"],
              ["Decisions", "Decisions made during the meeting with context"],
            ].map(([type, desc]) => (
              <tr key={type}>
                <td className="py-2 pr-4"><Code>{type}</Code></td>
                <td className="py-2 text-gray-400">{desc}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </DocSection>

      <DocSection title="Security">
        <p>
          Feed credentials (MCP auth tokens) are encrypted at rest and never
          returned in API responses. You&apos;ll see a token hint (last 4 characters)
          to confirm which credential is stored. Tokens are deleted immediately
          when you remove a Feed.
        </p>
      </DocSection>
    </div>
  );
}

/* ── Feeds — Slack (5I) ──────────────────────────────────────────────────── */

function FeedsSlack() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Slack Feed</h1>
        <p className="mt-2 text-gray-400">
          Connect your Kutana meetings to Slack. Push meeting recaps to channels
          or pull Slack threads into meetings as context.
        </p>
      </div>

      <DocSection title="Setup">
        <ol className="list-decimal list-inside space-y-2 text-gray-400 text-sm">
          <li>
            Go to <strong className="text-gray-50">Feeds</strong> in the sidebar
          </li>
          <li>
            Click <strong className="text-gray-50">Configure</strong> on{" "}
            <strong className="text-gray-50">Slack</strong>
          </li>
          <li>
            Enter your Slack MCP server URL or bot token
          </li>
          <li>
            Choose the delivery type: <strong className="text-gray-50">MCP Server</strong>
          </li>
          <li>
            Select which data types to include (Summary, Tasks, Transcript, Decisions)
          </li>
          <li>
            Set the trigger: after meeting ends, or manually
          </li>
          <li>
            Click <strong className="text-gray-50">Save Feed</strong>
          </li>
        </ol>
      </DocSection>

      <DocSection title="What Gets Delivered">
        <p>
          When triggered, the Slack Feed agent posts a formatted message to your
          configured channel. The message includes:
        </p>
        <ul className="list-disc list-inside space-y-1 text-gray-400 text-sm mt-2">
          <li>Meeting title, duration, and participant list</li>
          <li>Key discussion points and decisions</li>
          <li>Action items with assignees</li>
          <li>Condensed transcript (if selected)</li>
        </ul>
      </DocSection>

      <DocSection title="Inbound Context">
        <p>
          To pull a Slack thread into a meeting, configure an inbound feed with
          the Slack channel and thread URL. The Feed agent fetches the thread
          before the meeting starts and makes it available to all participants.
        </p>
      </DocSection>

      <DocSection title="Triggers">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-left text-gray-400">
              <th className="pb-2 pr-4 font-medium">Trigger</th>
              <th className="pb-2 font-medium">When It Runs</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {[
              ["After meeting ends", "Automatically when the host ends the meeting"],
              ["Before meeting starts", "When the meeting is created or scheduled to begin"],
              ["Manually", "Only when you click 'Run Now' from the Feeds page"],
            ].map(([trigger, when]) => (
              <tr key={trigger}>
                <td className="py-2 pr-4 text-gray-200">{trigger}</td>
                <td className="py-2 text-gray-400">{when}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </DocSection>
    </div>
  );
}

/* ── Feeds — Coming Soon (5I) ────────────────────────────────────────────── */

function FeedsUpcoming() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Coming Soon</h1>
        <p className="mt-2 text-gray-400">
          These Feed integrations are planned for upcoming releases.
        </p>
      </div>

      <div className="space-y-4">
        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-gray-50">Discord</span>
            <span className="rounded-md bg-gray-700/30 px-2 py-0.5 text-xs font-medium text-gray-400">
              Coming Soon
            </span>
          </div>
          <p className="text-xs text-gray-400">
            Push meeting recaps to Discord channels via a Claude Code Channel
            integration. Pull thread context from Discord into meetings.
          </p>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-gray-50">Notion</span>
            <span className="rounded-md bg-gray-700/30 px-2 py-0.5 text-xs font-medium text-gray-400">
              Planned
            </span>
          </div>
          <p className="text-xs text-gray-400">
            Sync meeting summaries and action items to Notion databases. Pull
            relevant Notion pages as context before meetings start.
          </p>
        </div>

        <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-gray-50">GitHub</span>
            <span className="rounded-md bg-gray-700/30 px-2 py-0.5 text-xs font-medium text-gray-400">
              Planned
            </span>
          </div>
          <p className="text-xs text-gray-400">
            Create GitHub issues from meeting action items. Pull issue and PR
            context into technical meetings automatically.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ─── Shared UI primitives ────────────────────────────────────────────────── */

function DocSection({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3">
      <h2 className="text-base font-semibold text-gray-50 border-b border-gray-800 pb-2">
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
      <h2 className="text-base font-semibold text-gray-50 border-b border-gray-800 pb-2">
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
  desc,
  onClick,
}: {
  title: string;
  desc: string;
  onClick?: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 text-left hover:border-gray-700 transition-colors"
    >
      <span className="text-sm font-semibold text-gray-50">{title}</span>
      <p className="mt-2 text-xs text-gray-400">{desc}</p>
    </button>
  );
}

function AgentCard({
  name,
  desc,
  tier,
  tierColor,
  howItWorks,
}: {
  name: string;
  desc: string;
  tier: string;
  tierColor: "green" | "blue";
  howItWorks: string;
}) {
  const colorClasses = tierColor === "green"
    ? "bg-green-600/20 text-green-400"
    : "bg-blue-600/20 text-blue-400";

  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-semibold text-gray-50">{name}</span>
        <span className={cn("rounded-md px-2 py-0.5 text-xs font-medium", colorClasses)}>
          {tier}
        </span>
      </div>
      <p className="text-xs text-gray-400">{desc}</p>
      <div className="border-t border-gray-800 pt-2">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-gray-600 mb-1">
          How it works
        </p>
        <p className="text-xs text-gray-500">{howItWorks}</p>
      </div>
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
