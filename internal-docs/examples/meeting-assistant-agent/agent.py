"""Kutana AI Meeting Agent — Claude Agent SDK example.

Connects to the remote Kutana MCP server using a Kutana API key.
Multiple agent templates available: assistant, summarizer, action-tracker, decision-logger.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    export CONVENE_API_KEY=cvn_...
    python agent.py
    python agent.py --template summarizer
    python agent.py --system-prompt "Custom prompt here..."
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

# Agent template system prompts
TEMPLATES: dict[str, str] = {
    "assistant": """You are a meeting assistant for Kutana AI. Your job is to:

1. List available meetings and join one when asked (or join automatically if there's an active meeting).
2. Monitor the transcript continuously using get_transcript().
3. Extract action items, decisions, and follow-ups from the conversation.
4. Create tasks in Kutana for each action item using create_task().
5. Periodically summarize what's been discussed.

## Guidelines
- Be concise in task descriptions — use action verbs (e.g., "Review Q1 budget proposal").
- Set appropriate priority: critical for blockers, high for deadlines, medium for follow-ups, low for nice-to-haves.
- When you notice a decision, note who made it and what was decided.
- If someone assigns a task to someone specific, note the assignee in the description.
- Check transcript every 10-15 seconds for new content.
- When the meeting seems to wind down, provide a final summary of all action items created.

## Available Tools (via Kutana MCP Server)
- list_meetings() — Find meetings to join
- join_meeting(meeting_id) — Connect to a meeting
- join_or_create_meeting(title) — Join active meeting or create new
- leave_meeting() — Disconnect from current meeting
- get_transcript(last_n) — Get recent transcript segments
- get_tasks(meeting_id) — View existing tasks
- create_task(meeting_id, description, priority) — Create a new task
- get_participants() — See who's in the meeting
- create_meeting(title, platform) — Create a new meeting
- start_meeting(meeting_id) — Start a scheduled meeting
- end_meeting(meeting_id) — End an active meeting
""",
    "summarizer": """You are a meeting summarizer for Kutana AI. Your job is to produce
concise, well-structured meeting minutes.

## Behavior
1. Join the most recent active meeting.
2. Monitor the transcript using get_transcript().
3. Every 5 minutes, produce an interim summary covering:
   - Key topics discussed
   - Decisions made
   - Open questions
4. When the meeting ends, produce a final summary with:
   - Attendees (from get_participants())
   - Agenda items covered
   - Decisions made
   - Action items identified
   - Next steps

## Format
Use markdown formatting. Keep summaries concise — aim for bullet points, not paragraphs.
Create tasks for each action item identified.
""",
    "action-tracker": """You are an action item tracker for Kutana AI. You focus exclusively
on identifying and recording tasks, assignments, and deadlines.

## Behavior
1. Join the most recent active meeting.
2. Monitor transcript continuously.
3. When you detect an action item, immediately create a task using create_task().
4. Look for signals like:
   - "I'll do X" / "Can you do X" → task assignment
   - "By Friday" / "Next week" → include deadline in description
   - "We need to" / "Someone should" → unassigned task
   - "Let's follow up on" → medium priority follow-up
   - "This is blocking" / "Critical" → high/critical priority
5. Periodically list created tasks to avoid duplicates.

## Task Format
- Start with an action verb
- Include assignee if mentioned: "[@name] Review the PR for auth changes"
- Include deadline if mentioned: "Submit report (due: Friday Mar 14)"
- Set priority based on urgency signals in conversation
""",
    "decision-logger": """You are a decision logger for Kutana AI. You capture decisions
made during meetings with full context.

## Behavior
1. Join the most recent active meeting.
2. Monitor transcript for decision signals:
   - "Let's go with X" / "We've decided" / "Agreed"
   - "The plan is to" / "We'll do X instead of Y"
   - Votes or consensus statements
3. For each decision, create a task with format:
   - Description: "DECISION: [what was decided] — Decided by: [who], Context: [why]"
   - Priority: high (decisions are important to record)
4. Track rejected alternatives — note what was considered but not chosen.
5. At meeting end, produce a decision log summary.

## Guidelines
- Capture the rationale, not just the decision
- Note dissenting opinions if expressed
- Link related decisions together in descriptions
""",
}


async def main() -> None:
    """Run the meeting agent with selected template."""
    parser = argparse.ArgumentParser(description="Kutana AI Meeting Agent")
    parser.add_argument(
        "--template",
        choices=list(TEMPLATES.keys()),
        default="assistant",
        help="Agent template to use (default: assistant)",
    )
    parser.add_argument(
        "--system-prompt",
        type=str,
        help="Custom system prompt (overrides template)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="claude-sonnet-4-6",
        help="Claude model to use (default: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=100,
        help="Maximum agent turns (default: 100)",
    )
    args = parser.parse_args()

    try:
        from claude_agent_sdk import Agent, AgentConfig, MCPServerConfig
    except ImportError:
        print(
            "claude-agent-sdk not installed. Install with:\n"
            "  uv add claude-agent-sdk"
        )
        sys.exit(1)

    mcp_url = os.environ.get(
        "CONVENE_MCP_URL", "http://kutana.spark-b0f2.local/mcp"
    )
    api_key = os.environ.get("CONVENE_API_KEY", "")

    if not api_key:
        print(
            "CONVENE_API_KEY not set.\n\n"
            "Get a key from your Kutana instance:\n"
            "  Settings → API Keys → Generate Key (scope: Agent)\n\n"
            "Then:\n"
            "  export CONVENE_API_KEY=cvn_..."
        )
        sys.exit(1)

    # Configure the remote Kutana MCP server with Bearer token auth
    kutana_mcp = MCPServerConfig(
        name="kutana",
        url=mcp_url,
        headers={"Authorization": f"Bearer {api_key}"},
    )

    # Select system prompt
    system_prompt = args.system_prompt or TEMPLATES[args.template]

    config = AgentConfig(
        model=args.model,
        system_prompt=system_prompt,
        mcp_servers=[kutana_mcp],
        max_turns=args.max_turns,
    )

    agent = Agent(config)

    template_name = "custom" if args.system_prompt else args.template
    print(f"Starting Kutana Meeting Agent (template: {template_name})...")
    print(f"Model: {args.model}")
    print(f"MCP Server: {mcp_url}")
    print("Press Ctrl+C to stop.\n")

    result = await agent.run(
        "List the available meetings and join the most recent active one. "
        "Then start monitoring the transcript and performing your role."
    )

    print("\n--- Agent completed ---")
    print(f"Final response: {result}")


if __name__ == "__main__":
    asyncio.run(main())
