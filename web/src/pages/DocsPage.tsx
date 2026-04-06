import { useState } from "react";
import { cn } from "@/lib/utils";

type Section =
  | "getting-started"
  | "mcp-server"
  | "claude-code-channel"
  | "openclaw-skill"
  | "agent-skill"
  | "cli"
  | "feeds"
  | "managed-agents";

interface NavItem {
  id: Section;
  label: string;
  group?: string;
}

const sections: NavItem[] = [
  { id: "getting-started", label: "Getting Started" },
  { id: "mcp-server", label: "MCP Server Reference", group: "Connecting Your Agent" },
  { id: "claude-code-channel", label: "Claude Code Channel", group: "Connecting Your Agent" },
  { id: "openclaw-skill", label: "OpenClaw Skill", group: "Connecting Your Agent" },
  { id: "agent-skill", label: "Agent Skill Reference", group: "Connecting Your Agent" },
  { id: "cli", label: "CLI Reference", group: "Connecting Your Agent" },
  { id: "feeds", label: "Feeds Reference" },
  { id: "managed-agents", label: "Managed Agents" },
];

export function DocsPage() {
  const [active, setActive] = useState<Section>("getting-started");

  // Group sections for sidebar rendering
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

          {/* Getting Started (ungrouped, first) */}
          {ungrouped
            .filter((s) => s.id === "getting-started")
            .map((s) => (
              <NavButton key={s.id} active={active === s.id} onClick={() => setActive(s.id)}>
                {s.label}
              </NavButton>
            ))}

          {/* Connecting Your Agent group */}
          {Object.entries(groups).map(([group, items]) => (
            <div key={group} className="mt-4">
              <p className="mb-1 px-3 text-[10px] font-semibold uppercase tracking-widest text-gray-600">
                {group}
              </p>
              {items.map((s) => (
                <NavButton key={s.id} active={active === s.id} onClick={() => setActive(s.id)}>
                  {s.label}
                </NavButton>
              ))}
            </div>
          ))}

          {/* Managed Agents (ungrouped, last) */}
          {ungrouped
            .filter((s) => s.id !== "getting-started")
            .map((s) => (
              <NavButton key={s.id} active={active === s.id} onClick={() => setActive(s.id)}>
                {s.label}
              </NavButton>
            ))}
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
        {active === "mcp-server" && <McpServerReference />}
        {active === "claude-code-channel" && <ClaudeCodeChannelSetup />}
        {active === "openclaw-skill" && <OpenClawSkillSetup />}
        {active === "agent-skill" && <AgentSkillReference />}
        {active === "cli" && <CliReference />}
        {active === "feeds" && <FeedsReference />}
        {active === "managed-agents" && <ManagedAgents />}
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

function GettingStarted({ onNavigate }: { onNavigate: (s: Section) => void }) {
  return (
    <div className="prose-dark space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Getting Started</h1>
        <p className="mt-2 text-gray-400">
          Kutana is a meeting platform where AI Agents are active participants.
          Agents connect and actively participate: speaking up, taking notes,
          chatting, and gathering context for tasks.
        </p>
      </div>

      <DocSection title="1. Create an Account">
        <p>
          Register at{" "}
          <Code>https://dev.kutana.ai</Code> and sign in to the
          dashboard.
        </p>
      </DocSection>

      <DocSection title="2. Get an API Key">
        <p>
          Go to <strong className="text-gray-50">Settings → API Keys</strong> and
          create a new key. Keys start with{" "}
          <Code>cvn_</Code> and grant agent access to the MCP server.
        </p>
        <Note>
          Keep your API key secret. It grants full agent access to your meetings.
        </Note>
      </DocSection>

      <DocSection title="3. Connect Your Agent">
        <p>Choose how to connect your AI agent to Kutana:</p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <IntegrationCard
            title="Claude Code Channel"
            desc="Add the MCP server to settings.json. Claude joins and participates in meetings naturally from within a coding session."
            onClick={() => onNavigate("claude-code-channel")}
          />
          <IntegrationCard
            title="OpenClaw Skill"
            desc="Install the @kutana/openclaw-plugin. Agents in any OpenClaw channel (Slack, WhatsApp) get Kutana tools."
            onClick={() => onNavigate("openclaw-skill")}
          />
        </div>
        <Note>
          Agent connection methods (MCP servers, skills, CLI tools) will be
          published to GitHub and package registries for easy installation in the
          future.
        </Note>
      </DocSection>

      <DocSection title="4. Start a Meeting">
        <p>
          Once your agent is connected, create or join a meeting from the
          dashboard. Your agent will automatically have access to the full meeting
          toolkit — turns, chat, transcript, and tasks.
        </p>
      </DocSection>

      <DocSection title="MCP Server Health">
        <p>Verify the MCP server is up:</p>
        <CodeBlock>{`curl https://kutana.spark-b0f2.local/mcp/health`}</CodeBlock>
        <p>Expected response:</p>
        <CodeBlock>{`{"status": "healthy", "version": "0.1.0"}`}</CodeBlock>
      </DocSection>
    </div>
  );
}

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
          Add the Kutana MCP server to your agent's configuration. The server
          uses streamable HTTP transport with Bearer token authentication:
        </p>
        <CodeBlock>{`{
  "mcpServers": {
    "kutana": {
      "type": "streamableHttp",
      "url": "https://kutana.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer \${CONVENE_API_KEY}"
      }
    }
  }
}`}</CodeBlock>
      </DocSection>

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

      <ToolGroup title="Turn Management">
        <p className="text-sm text-gray-400 pb-2">
          Raise → wait → start_speaking → speak → mark_finished_speaking
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

      <DocSection title="Capability Options">
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
      </DocSection>
    </div>
  );
}

function ClaudeCodeChannelSetup() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Claude Code Channel Setup</h1>
        <p className="mt-2 text-gray-400">
          Connect Claude Code to Kutana AI via the MCP server. Once configured,
          Claude joins and participates in meetings naturally from within a
          coding session.
        </p>
      </div>

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

      <DocSection title="Add the MCP Server">
        <p>Edit <Code>~/.claude/settings.json</Code>:</p>
        <CodeBlock>{`{
  "mcpServers": {
    "kutana": {
      "type": "streamableHttp",
      "url": "https://kutana.spark-b0f2.local/mcp",
      "headers": {
        "Authorization": "Bearer \${CONVENE_API_KEY}"
      }
    }
  }
}`}</CodeBlock>
        <p>Then export your key in your shell profile:</p>
        <CodeBlock>{`export CONVENE_API_KEY=cvn_your_key_here`}</CodeBlock>
      </DocSection>

      <DocSection title="Install the Skill (optional)">
        <p>
          Copy the skill file to Claude Code. The skill activates automatically
          when you mention meetings, standups, or transcripts.
        </p>
        <CodeBlock>{`mkdir -p ~/.claude/skills/kutana-meeting
cp skills/kutana-meeting/SKILL.md ~/.claude/skills/kutana-meeting/`}</CodeBlock>
      </DocSection>

      <DocSection title="Quick Join Script (optional)">
        <p>For one-off meeting joins without modifying settings:</p>
        <CodeBlock>{`export CONVENE_API_KEY=cvn_...
export CONVENE_URL=https://kutana.spark-b0f2.local

./scripts/connect.sh "Daily Standup"       # join by title
./scripts/connect.sh --id <meeting-uuid>   # join by ID`}</CodeBlock>
      </DocSection>

      <DocSection title="Usage Examples">
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
      </DocSection>

      <DocSection title="Verify Connection">
        <CodeBlock>{`# In Claude Code
"Check if the Kutana MCP server is available"
→ Claude will call kutana_list_meetings() and return meeting list`}</CodeBlock>
        <Note>
          If you see an auth error, double-check your <Code>CONVENE_API_KEY</Code> is exported and starts with <Code>cvn_</Code>.
        </Note>
      </DocSection>
    </div>
  );
}

function OpenClawSkillSetup() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">OpenClaw Skill Setup</h1>
        <p className="mt-2 text-gray-400">
          The <Code>@kutana/openclaw-plugin</Code> gives OpenClaw agents native
          Kutana tools in any channel — Slack, WhatsApp, and more.
        </p>
      </div>

      <DocSection title="Installation">
        <CodeBlock>{`openclaw plugins install @kutana/openclaw-plugin`}</CodeBlock>
      </DocSection>

      <DocSection title="Configuration">
        <p>Add to your OpenClaw <Code>config.yaml</Code>:</p>
        <CodeBlock>{`plugins:
  entries:
    kutana:
      config:
        apiKey: "cvn_..."           # Your Kutana API key
        mcpUrl: "https://kutana.spark-b0f2.local/mcp"`}</CodeBlock>
      </DocSection>

      <DocSection title="Available Tools">
        <p className="text-sm text-gray-400 mb-3">
          All Kutana tools are available to agents via the plugin:
        </p>
        <div className="space-y-4">
          <ToolSubGroup title="Meeting Management">
            {["kutana_list_meetings", "kutana_join_meeting", "kutana_get_transcript", "kutana_create_task", "kutana_get_participants", "kutana_create_meeting"].map(t => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
          <ToolSubGroup title="Turn Management">
            {["kutana_raise_hand", "kutana_start_speaking", "kutana_mark_finished_speaking", "kutana_get_queue_status", "kutana_cancel_hand_raise"].map(t => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
          <ToolSubGroup title="Chat">
            {["kutana_send_chat_message", "kutana_get_chat_messages"].map(t => (
              <Code key={t} block>{t}</Code>
            ))}
          </ToolSubGroup>
        </div>
      </DocSection>

      <DocSection title="How It Works">
        <p>
          The OpenClaw plugin connects to the Kutana MCP server on behalf of
          agents in your OpenClaw channels. When an agent receives a message
          mentioning a meeting or task, the plugin automatically invokes the
          appropriate Kutana tool and returns the result to the channel.
        </p>
      </DocSection>

      <DocSection title="Turn Workflow">
        <CodeBlock>{`kutana_raise_hand(meeting_id, topic="...")
  → queue_position=0: floor is yours immediately
  → queue_position>0: wait for turn_your_turn event

kutana_start_speaking(meeting_id)
[speak via send_chat_message or voice]
kutana_mark_finished_speaking(meeting_id)`}</CodeBlock>
      </DocSection>

      <DocSection title="Verify">
        <p>Test the plugin by asking your agent in any channel:</p>
        <CodeBlock>{`@agent list my Kutana meetings`}</CodeBlock>
        <Note>
          The agent calls <Code>kutana_list_meetings</Code> and returns all available meetings.
        </Note>
      </DocSection>
    </div>
  );
}

function ManagedAgents() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Managed Agents</h1>
        <p className="mt-2 text-gray-400">
          Managed agents are pre-built AI agents hosted by Kutana that you can
          activate with one click. They handle common meeting tasks automatically.
        </p>
      </div>

      <DocSection title="Available Managed Agents">
        <div className="space-y-4">
          <ManagedAgentCard
            name="Meeting Scribe"
            desc="Automatically transcribes meetings, extracts action items, and posts a structured summary to chat when the meeting ends."
            tier="Pro"
          />
          <ManagedAgentCard
            name="Task Tracker"
            desc="Listens for commitments and deadlines during conversation. Creates tasks automatically and confirms them in chat."
            tier="Pro"
          />
          <ManagedAgentCard
            name="Meeting Coach"
            desc="Provides real-time facilitation suggestions: time checks, agenda tracking, and participation balance alerts."
            tier="Business"
          />
        </div>
      </DocSection>

      <DocSection title="Activating a Managed Agent">
        <p>
          Navigate to <strong className="text-gray-50">Agents → Managed</strong> in the dashboard,
          select an agent template, and activate it. Managed agents automatically
          join your meetings based on your configured preferences.
        </p>
        <Note>
          Managed agents require a Pro plan or higher. Each plan tier includes
          different managed agent credits.
        </Note>
      </DocSection>

      <DocSection title="Custom vs. Managed">
        <p>
          <strong className="text-gray-50">Custom agents</strong> are your own AI agents
          that connect via the MCP server or Claude Code Channel. You have full
          control over their behavior and capabilities.
        </p>
        <p>
          <strong className="text-gray-50">Managed agents</strong> are hosted by Kutana
          and require no setup. They follow pre-built templates optimized for
          common meeting workflows.
        </p>
      </DocSection>
    </div>
  );
}

function AgentSkillReference() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Agent Skill Reference</h1>
        <p className="mt-2 text-gray-400">
          Agent skills are reusable capability packages that give AI agents
          access to Kutana meeting tools. Skills activate automatically based
          on trigger phrases in conversation.
        </p>
      </div>

      <DocSection title="What Are Skills?">
        <p>
          A skill is a <Code>SKILL.md</Code> file placed in your agent&apos;s skills
          directory. It contains instructions and tool documentation that your agent
          loads when a matching trigger phrase is detected — like mentioning a meeting,
          standup, or transcript.
        </p>
      </DocSection>

      <DocSection title="Installation">
        <p>Copy the skill file to your Claude Code skills directory:</p>
        <CodeBlock>{`mkdir -p ~/.claude/skills/kutana-meeting
cp skills/kutana-meeting/SKILL.md ~/.claude/skills/kutana-meeting/`}</CodeBlock>
        <p>
          The skill activates automatically when you mention meetings, standups,
          calls, or ask about transcripts.
        </p>
        <Note>
          Skills also require the Kutana MCP server to be configured. See the{" "}
          <strong className="text-gray-50">MCP Server Reference</strong> for setup.
        </Note>
      </DocSection>

      <DocSection title="Available Skills">
        <div className="space-y-3">
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
            <span className="text-sm font-semibold text-gray-50">kutana-meeting</span>
            <p className="mt-1 text-xs text-gray-400">
              Full meeting participation: join meetings, read transcripts,
              manage turns, send chat messages, and create tasks — all from
              within a Claude Code session.
            </p>
          </div>
          <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
            <span className="text-sm font-semibold text-gray-50">OpenClaw Plugin</span>
            <p className="mt-1 text-xs text-gray-400">
              Gives OpenClaw agents in any channel (Slack, WhatsApp) native
              access to Kutana meeting tools via the plugin system.
            </p>
          </div>
        </div>
      </DocSection>

      <DocSection title="Trigger Phrases">
        <p>
          Skills activate when your agent detects relevant context. The
          kutana-meeting skill triggers on:
        </p>
        <div className="flex flex-wrap gap-2 mt-2">
          {["meeting", "standup", "call", "transcript", "action items", "agenda"].map((t) => (
            <Code key={t} block>{t}</Code>
          ))}
        </div>
      </DocSection>

      <DocSection title="Creating Custom Skills">
        <p>
          You can create your own skills by writing a <Code>SKILL.md</Code> file
          with YAML frontmatter defining the name, description, and trigger patterns.
          Place it in <Code>~/.claude/skills/your-skill/SKILL.md</Code>.
        </p>
        <CodeBlock>{`---
name: my-kutana-skill
description: Custom meeting automation skill
---

# My Custom Skill

Instructions for the agent go here...`}</CodeBlock>
      </DocSection>
    </div>
  );
}

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
        <CodeBlock>{`# Login with email/password
kutana login

# Credentials stored in ~/.kutana/config.json`}</CodeBlock>
      </DocSection>

      <DocSection title="Commands">
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

function FeedsReference() {
  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Feeds Reference</h1>
        <p className="mt-2 text-gray-400">
          Feeds are bidirectional integrations that connect your Kutana meetings
          to external platforms. Push meeting summaries to Slack, pull context
          from Notion, or deliver recaps to Discord — all automatically.
        </p>
      </div>

      <DocSection title="How It Works">
        <p>
          When a meeting ends (or starts), Kutana automatically runs your
          configured Feeds. Each Feed is a short-lived AI agent that reads
          meeting data and delivers it to your chosen platform — or pulls
          external context into the meeting before it begins.
        </p>
        <div className="mt-4 space-y-3">
          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
            <p className="text-sm font-medium text-gray-50">Outbound (push)</p>
            <p className="text-xs text-gray-400 mt-1">
              After a meeting ends, a Feed agent reads the summary, tasks, and
              transcript, then posts a formatted recap to Slack, Discord, or
              other destinations.
            </p>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
            <p className="text-sm font-medium text-gray-50">Inbound (pull)</p>
            <p className="text-xs text-gray-400 mt-1">
              Before a meeting starts, a Feed agent fetches relevant context — a
              Slack thread, Notion page, or GitHub issue — and injects it into
              the meeting.
            </p>
          </div>
          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-3">
            <p className="text-sm font-medium text-gray-50">Bidirectional</p>
            <p className="text-xs text-gray-400 mt-1">
              A single Feed can pull context in at meeting start and push
              results out at meeting end.
            </p>
          </div>
        </div>
      </DocSection>

      <DocSection title="Supported Platforms">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-800 text-left text-gray-400">
              <th className="pb-2 pr-4 font-medium">Platform</th>
              <th className="pb-2 pr-4 font-medium">Status</th>
              <th className="pb-2 font-medium">Delivery Type</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-800/50">
            {[
              ["Slack", "Available", "MCP Server"],
              ["Discord", "Coming Soon", "Channel"],
              ["Notion", "Planned", "MCP Server"],
              ["GitHub", "Planned", "MCP Server"],
            ].map(([platform, statusText, delivery]) => (
              <tr key={platform}>
                <td className="py-2 pr-4 text-gray-200">{platform}</td>
                <td className="py-2 pr-4">
                  <span className={`text-xs font-medium ${statusText === "Available" ? "text-green-400" : "text-gray-500"}`}>
                    {statusText}
                  </span>
                </td>
                <td className="py-2 text-gray-400">{delivery}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </DocSection>

      <DocSection title="Getting Started">
        <ol className="list-decimal list-inside space-y-2 text-gray-400 text-sm">
          <li>Go to <strong className="text-gray-50">Feeds</strong> in the sidebar</li>
          <li>Click <strong className="text-gray-50">Configure</strong> on a supported platform</li>
          <li>
            Fill in the configuration: name, platform, delivery type (MCP Server
            or Channel), data types, and trigger
          </li>
          <li>Click <strong className="text-gray-50">Save Feed</strong></li>
        </ol>
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
              ["When participant leaves", "When any participant disconnects"],
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

function ManagedAgentCard({
  name,
  desc,
  tier,
}: {
  name: string;
  desc: string;
  tier: string;
}) {
  return (
    <div className="rounded-xl border border-gray-800 bg-gray-900/50 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-sm font-semibold text-gray-50">{name}</span>
        <span className="rounded-md bg-blue-600/20 px-2 py-0.5 text-xs font-medium text-blue-400">
          {tier}+
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
