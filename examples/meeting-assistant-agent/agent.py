"""Convene AI Meeting Assistant — Claude Agent SDK example.

This agent uses the Convene MCP server to join meetings, monitor
transcripts, extract action items, and create tasks autonomously.

The agent's behavior is entirely driven by its system prompt. Change
the prompt to make the agent do anything: summarize, track decisions,
generate reports, etc. The MCP tools are the universal interface.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    export MCP_API_KEY=cvn_...
    export MCP_AGENT_CONFIG_ID=<agent-uuid>
    python agent.py
"""

from __future__ import annotations

import asyncio
import os
import sys


async def main() -> None:
    """Run the meeting assistant agent."""
    try:
        from claude_agent_sdk import Agent, AgentConfig, MCPServerConfig
    except ImportError:
        print(
            "claude-agent-sdk not installed. Install with:\n"
            "  pip install claude-agent-sdk\n"
            "or:\n"
            "  uv add claude-agent-sdk"
        )
        sys.exit(1)

    mcp_server_url = os.environ.get("MCP_SERVER_URL", "http://localhost:3001")

    if not mcp_server_url:
        print(
            "Required environment variables:\n"
            "  MCP_SERVER_URL — URL of the Convene MCP server (default: http://localhost:3001)\n"
            "\n"
            "The MCP server must be running (via Docker or locally).\n"
            "Make sure MCP_API_KEY and MCP_AGENT_CONFIG_ID are set on the server."
        )
        sys.exit(1)

    # Configure the Convene MCP server (Streamable HTTP)
    convene_mcp = MCPServerConfig(
        name="convene",
        url=f"{mcp_server_url}/mcp",
    )

    # System prompt that defines the agent's behavior
    system_prompt = """You are a meeting assistant for Convene AI. Your job is to:

1. List available meetings and join one when asked (or join automatically if there's an active meeting).
2. Monitor the transcript continuously using get_transcript().
3. Extract action items, decisions, and follow-ups from the conversation.
4. Create tasks in Convene for each action item using create_task().
5. Periodically summarize what's been discussed.

## Guidelines
- Be concise in task descriptions — use action verbs (e.g., "Review Q1 budget proposal").
- Set appropriate priority: critical for blockers, high for deadlines, medium for follow-ups, low for nice-to-haves.
- When you notice a decision, note who made it and what was decided.
- If someone assigns a task to someone specific, note the assignee in the description.
- Check transcript every 10-15 seconds for new content.
- When the meeting seems to wind down, provide a final summary of all action items created.

## Available Tools (via Convene MCP Server)
- list_meetings() — Find meetings to join
- join_meeting(meeting_id) — Connect to a meeting
- leave_meeting() — Disconnect from current meeting
- get_transcript(last_n) — Get recent transcript segments
- get_tasks(meeting_id) — View existing tasks
- create_task(meeting_id, description, priority) — Create a new task
- get_participants() — See who's in the meeting
"""

    config = AgentConfig(
        model="claude-sonnet-4-6",
        system_prompt=system_prompt,
        mcp_servers=[convene_mcp],
        max_turns=100,
    )

    agent = Agent(config)

    print("Starting Convene Meeting Assistant Agent...")
    print("The agent will list meetings and join one automatically.")
    print("Press Ctrl+C to stop.\n")

    result = await agent.run(
        "List the available meetings and join the most recent active one. "
        "Then start monitoring the transcript for action items."
    )

    print("\n--- Agent completed ---")
    print(f"Final response: {result}")


if __name__ == "__main__":
    asyncio.run(main())
