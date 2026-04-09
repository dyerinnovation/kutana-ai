#!/usr/bin/env python3
"""Set up Kutana managed agents on the Anthropic platform.

Creates environments, agent definitions, and optionally tests a session.
Reads the API key from a file (never hardcoded).

Usage:
    # Create everything
    uv run python scripts/setup_managed_agents.py --create-all

    # Create environment only
    uv run python scripts/setup_managed_agents.py --create-env

    # Create agents only (requires environment ID)
    uv run python scripts/setup_managed_agents.py --create-agents --env-id <ENV_ID>

    # Test a session (requires agent ID and environment ID)
    uv run python scripts/setup_managed_agents.py --test --agent-name "Meeting Notetaker" --env-id <ENV_ID>

    # List existing resources
    uv run python scripts/setup_managed_agents.py --list
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

from anthropic import Anthropic

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

API_KEY_FILE = (
    Path.home() / "Documents/dev/z-api-keys-and-tokens/ANTHROPIC_API_KEY_TEST.txt"
)  # fallback only
SYSTEM_PROMPTS_FILE = (
    Path(__file__).resolve().parent.parent
    / "internal-docs/development/managed-agent-system-prompts.md"
)
OUTPUT_FILE = (
    Path(__file__).resolve().parent.parent / "internal-docs/development/managed-agent-ids.json"
)

MODEL = "claude-sonnet-4-6"

# Kutana custom tool definitions (type: "custom" for managed agents API)
KUTANA_TOOLS: list[dict[str, Any]] = [
    {
        "type": "custom",
        "name": "kutana_send_chat_message",
        "description": "Send a chat message to the meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
                "text": {"type": "string"},
                "message_type": {
                    "type": "string",
                    "enum": ["text", "action_item", "decision"],
                    "default": "text",
                },
            },
            "required": ["meeting_id", "text"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_create_task",
        "description": "Create a task/action item in the meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
                "description": {"type": "string"},
                "assignee": {"type": "string"},
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "default": "medium",
                },
            },
            "required": ["meeting_id", "description"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_raise_hand",
        "description": "Request a turn to speak in the meeting.",
        "input_schema": {
            "type": "object",
            "properties": {"meeting_id": {"type": "string"}},
            "required": ["meeting_id"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_mark_finished_speaking",
        "description": "Signal that you have finished speaking.",
        "input_schema": {
            "type": "object",
            "properties": {"meeting_id": {"type": "string"}},
            "required": ["meeting_id"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_get_transcript",
        "description": "Get recent transcript segments from the meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
                "last_n": {"type": "integer", "default": 20},
            },
            "required": ["meeting_id"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_get_participants",
        "description": "Get the list of participants in the meeting.",
        "input_schema": {
            "type": "object",
            "properties": {"meeting_id": {"type": "string"}},
            "required": ["meeting_id"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_get_meeting_status",
        "description": "Get the current meeting status snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {"meeting_id": {"type": "string"}},
            "required": ["meeting_id"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_get_tasks",
        "description": "Get tasks/action items tracked for this meeting.",
        "input_schema": {
            "type": "object",
            "properties": {"meeting_id": {"type": "string"}},
            "required": ["meeting_id"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_get_chat_messages",
        "description": "Read chat message history for this meeting.",
        "input_schema": {
            "type": "object",
            "properties": {"meeting_id": {"type": "string"}},
            "required": ["meeting_id"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_get_meeting_events",
        "description": "Get real-time meeting events (joins, leaves, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {"meeting_id": {"type": "string"}},
            "required": ["meeting_id"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_get_queue_status",
        "description": "Check the speaker queue status.",
        "input_schema": {
            "type": "object",
            "properties": {"meeting_id": {"type": "string"}},
            "required": ["meeting_id"],
        },
    },
    {
        "type": "custom",
        "name": "kutana_speak",
        "description": "Speak aloud via TTS in the meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["meeting_id", "text"],
        },
    },
]

# Agent template names and their tier (for organizing output)
AGENT_TEMPLATES = [
    {"name": "Meeting Notetaker", "tier": "basic", "index": 1},
    {"name": "Meeting Summarizer", "tier": "basic", "index": 2},
    {"name": "Action Item Tracker", "tier": "pro", "index": 3},
    {"name": "Decision Logger", "tier": "pro", "index": 4},
    {"name": "Standup Facilitator", "tier": "pro", "index": 5},
    {"name": "Code Discussion Tracker", "tier": "pro", "index": 6},
    {"name": "Sprint Retro Coach", "tier": "business", "index": 7},
    {"name": "Sprint Planner", "tier": "business", "index": 8},
    {"name": "User Interviewer", "tier": "business", "index": 9},
    {"name": "Initial Interviewer", "tier": "business", "index": 10},
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def load_api_key() -> str:
    """Load API key from ANTHROPIC_API_KEY env var, falling back to file."""
    import os

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key and API_KEY_FILE.exists():
        key = API_KEY_FILE.read_text().strip()
    if not key:
        print("ERROR: Set ANTHROPIC_API_KEY or place key in", API_KEY_FILE)
        sys.exit(1)
    return key


def parse_system_prompts(md_path: Path) -> dict[str, str]:
    """Parse system prompts from the managed-agent-system-prompts.md file.

    Returns a dict mapping agent name -> system prompt text.
    """
    content = md_path.read_text()
    prompts: dict[str, str] = {}

    # Pattern: ### N. Agent Name\n\n```\n<prompt>\n```
    pattern = r"### \d+\.\s+(.+?)\n\n```\n(.*?)```"
    for match in re.finditer(pattern, content, re.DOTALL):
        name = match.group(1).strip()
        prompt = match.group(2).strip()
        prompts[name] = prompt

    return prompts


def get_client(api_key: str) -> Anthropic:
    """Create an Anthropic client."""
    return Anthropic(api_key=api_key)


# ---------------------------------------------------------------------------
# API Operations
# ---------------------------------------------------------------------------


def create_environment(client: Anthropic, name: str = "kutana-agents") -> dict[str, Any]:
    """Create a managed agent environment."""
    print(f"\n--- Creating environment: {name} ---")
    env = client.beta.agents.environments.create(  # type: ignore[attr-defined]
        name=name,
        config={
            "type": "cloud",
            "networking": {"type": "unrestricted"},
        },
    )
    result = {"id": env.id, "name": name}
    print(f"  Environment ID: {env.id}")
    return result


def create_environment_via_http(api_key: str, name: str = "kutana-agents") -> dict[str, Any]:
    """Create environment using raw HTTP (fallback if SDK doesn't support it yet)."""
    import httpx

    print(f"\n--- Creating environment: {name} ---")
    resp = httpx.post(
        "https://api.anthropic.com/v1/environments",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "managed-agents-2026-04-01",
            "content-type": "application/json",
        },
        json={
            "name": name,
            "config": {
                "type": "cloud",
                "networking": {"type": "unrestricted"},
            },
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"  Environment ID: {data['id']}")
    return {"id": data["id"], "name": name}


def create_agent_via_sdk(
    client: Anthropic,
    name: str,
    system_prompt: str,
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a managed agent using the SDK."""
    agent = client.beta.agents.create(
        name=f"Kutana {name}",
        model=MODEL,
        system=system_prompt,
        tools=tools,
    )
    return {"id": agent.id, "version": agent.version, "name": name}


def create_agent_via_http(
    api_key: str,
    name: str,
    system_prompt: str,
    tools: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a managed agent using raw HTTP."""
    import httpx

    resp = httpx.post(
        "https://api.anthropic.com/v1/agents",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "anthropic-beta": "managed-agents-2026-04-01",
            "content-type": "application/json",
        },
        json={
            "name": f"Kutana {name}",
            "model": MODEL,
            "system": system_prompt,
            "tools": tools,
        },
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"id": data["id"], "version": data["version"], "name": name}


def create_all_agents(
    api_key: str,
    client: Anthropic,
    prompts: dict[str, str],
    use_sdk: bool = True,
) -> list[dict[str, Any]]:
    """Create all 10 agent definitions."""
    agents: list[dict[str, Any]] = []

    for template in AGENT_TEMPLATES:
        name = template["name"]
        prompt = prompts.get(name)
        if not prompt:
            print(f"  WARNING: No system prompt found for '{name}', skipping")
            continue

        print(f"\n--- Creating agent: {name} (tier: {template['tier']}) ---")

        try:
            if use_sdk:
                result = create_agent_via_sdk(client, name, prompt, KUTANA_TOOLS)
            else:
                result = create_agent_via_http(api_key, name, prompt, KUTANA_TOOLS)

            result["tier"] = template["tier"]
            result["index"] = template["index"]
            agents.append(result)
            print(f"  Agent ID: {result['id']} (version {result['version']})")
        except Exception as e:
            print(f"  ERROR creating {name}: {e}")
            # If SDK fails, try HTTP fallback
            if use_sdk:
                print("  Retrying with HTTP...")
                try:
                    result = create_agent_via_http(api_key, name, prompt, KUTANA_TOOLS)
                    result["tier"] = template["tier"]
                    result["index"] = template["index"]
                    agents.append(result)
                    print(f"  Agent ID: {result['id']} (version {result['version']})")
                except Exception as e2:
                    print(f"  HTTP fallback also failed: {e2}")

    return agents


def test_session(
    api_key: str,
    client: Anthropic,
    agent_id: str,
    env_id: str,
    use_sdk: bool = True,
) -> dict[str, Any]:
    """Test a session with an agent by sending a transcript message."""
    import httpx

    print("\n--- Testing session ---")

    test_transcript = (
        "Meeting: Weekly Engineering Standup\n"
        "Participants: Alice (Engineering Lead), Bob (Backend), Charlie (Frontend)\n\n"
        "## Transcript Update\n\n"
        "[00:00] Alice: Good morning everyone. Let's do our standup. Bob, you want to go first?\n"
        "[00:15] Bob: Sure. Yesterday I finished the API rate limiting implementation. "
        "Today I'm going to work on the database migration for the new user schema. "
        "No blockers for me.\n"
        "[00:45] Charlie: I spent yesterday fixing the dashboard layout bugs. "
        "Today I'll start on the new notification component. "
        "I'm blocked on the design specs though - Sarah hasn't sent them yet.\n"
        "[01:10] Alice: I'll follow up with Sarah on those specs. "
        "For my update - I reviewed the Q3 roadmap yesterday and today I'll be "
        "finalizing the sprint planning for next week. Let's make sure we close "
        "out the remaining tickets by Friday.\n"
    )

    # Create session
    print("  Creating session...")
    if use_sdk:
        try:
            session = client.beta.sessions.create(
                agent=agent_id,
                environment_id=env_id,
                title="Kutana Agent Test Session",
            )
            session_id = session.id
        except Exception:
            # Fallback to HTTP
            use_sdk = False

    if not use_sdk:
        resp = httpx.post(
            "https://api.anthropic.com/v1/sessions",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "anthropic-beta": "managed-agents-2026-04-01",
                "content-type": "application/json",
            },
            json={
                "agent": agent_id,
                "environment_id": env_id,
                "title": "Kutana Agent Test Session",
            },
            timeout=30,
        )
        resp.raise_for_status()
        session_id = resp.json()["id"]

    print(f"  Session ID: {session_id}")

    # Per docs: open stream FIRST, then send message (API buffers events until stream attaches)
    import threading

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "managed-agents-2026-04-01",
    }

    events_collected: list[dict[str, Any]] = []
    tool_calls: list[str] = []
    text_parts: list[str] = []
    stream_ready = threading.Event()

    def send_message() -> None:
        """Send the user message after stream is open."""
        stream_ready.wait(timeout=10)
        time.sleep(0.5)  # small buffer for stream to fully attach
        print("  Sending test transcript...")
        resp = httpx.post(
            f"https://api.anthropic.com/v1/sessions/{session_id}/events",
            headers={**headers, "content-type": "application/json"},
            json={
                "events": [
                    {
                        "type": "user.message",
                        "content": [
                            {
                                "type": "text",
                                "text": test_transcript,
                            }
                        ],
                    }
                ]
            },
            timeout=30,
        )
        resp.raise_for_status()
        print("  Message sent.")

    sender = threading.Thread(target=send_message, daemon=True)
    sender.start()

    print("  Opening SSE stream...")
    with httpx.stream(
        "GET",
        f"https://api.anthropic.com/v1/sessions/{session_id}/stream",
        headers={**headers, "Accept": "text/event-stream"},
        timeout=httpx.Timeout(connect=10, read=180, write=10, pool=10),
    ) as sse_stream:
        stream_ready.set()  # signal that stream is open
        for line in sse_stream.iter_lines():
            if not line.startswith("data: "):
                continue
            json_str = line[6:]
            try:
                event = json.loads(json_str)
            except json.JSONDecodeError:
                continue

            events_collected.append(event)
            event_type = event.get("type", "")

            if event_type == "agent.message":
                for block in event.get("content", []):
                    if block.get("type") == "text":
                        text_parts.append(block["text"])
            elif event_type == "agent.custom_tool_use":
                tool_name = event.get("name", "unknown")
                tool_calls.append(tool_name)
                print(f"    [Tool call: {tool_name}]")
            elif event_type == "session.status_idle":
                print("  Agent finished (idle).")
                break

    sender.join(timeout=5)

    result = {
        "session_id": session_id,
        "text_response": "\n".join(text_parts),
        "tool_calls": tool_calls,
        "total_events": len(events_collected),
        "success": len(tool_calls) > 0,
    }

    print("\n  Results:")
    print(f"    Tool calls made: {len(tool_calls)}")
    for tc in tool_calls:
        print(f"      - {tc}")
    print(f"    Text response length: {len(result['text_response'])} chars")
    print(f"    Total events: {len(events_collected)}")
    print(f"    Success (has tool_use): {result['success']}")

    if text_parts:
        preview = result["text_response"][:500]
        print(f"\n  Response preview:\n    {preview}")

    return result


def list_resources(api_key: str) -> None:
    """List existing managed agent resources."""
    import httpx

    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "anthropic-beta": "managed-agents-2026-04-01",
    }

    print("\n=== Environments ===")
    resp = httpx.get("https://api.anthropic.com/v1/environments", headers=headers, timeout=30)
    if resp.status_code == 200:
        for env in resp.json().get("data", []):
            print(f"  {env['id']}: {env['name']}")
    else:
        print(f"  Error: {resp.status_code} {resp.text[:200]}")

    print("\n=== Agents ===")
    resp = httpx.get("https://api.anthropic.com/v1/agents", headers=headers, timeout=30)
    if resp.status_code == 200:
        for agent in resp.json().get("data", []):
            print(f"  {agent['id']}: {agent['name']} (v{agent['version']})")
    else:
        print(f"  Error: {resp.status_code} {resp.text[:200]}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Set up Kutana managed agents")
    parser.add_argument("--create-all", action="store_true", help="Create environment + all agents")
    parser.add_argument("--create-env", action="store_true", help="Create environment only")
    parser.add_argument("--create-agents", action="store_true", help="Create all agents")
    parser.add_argument("--test", action="store_true", help="Test a session")
    parser.add_argument("--list", action="store_true", help="List existing resources")
    parser.add_argument("--env-id", type=str, help="Environment ID (for --create-agents or --test)")
    parser.add_argument("--agent-name", type=str, default="Meeting Notetaker", help="Agent to test")
    parser.add_argument("--env-name", type=str, default="kutana-agents", help="Environment name")
    parser.add_argument("--use-http", action="store_true", help="Force HTTP instead of SDK")
    args = parser.parse_args()

    if not any([args.create_all, args.create_env, args.create_agents, args.test, args.list]):
        parser.print_help()
        sys.exit(1)

    # Load API key
    api_key = load_api_key()
    client = get_client(api_key)
    use_sdk = not args.use_http

    # Parse system prompts
    prompts = parse_system_prompts(SYSTEM_PROMPTS_FILE)
    print(f"Loaded {len(prompts)} system prompts: {', '.join(prompts.keys())}")

    # Load existing output if present
    output: dict[str, Any] = {}
    if OUTPUT_FILE.exists():
        output = json.loads(OUTPUT_FILE.read_text())

    if args.list:
        list_resources(api_key)
        return

    if args.create_all or args.create_env:
        try:
            if use_sdk:
                env_result = create_environment(client, args.env_name)
            else:
                env_result = create_environment_via_http(api_key, args.env_name)
            output["environment"] = env_result
            args.env_id = env_result["id"]
        except Exception as e:
            print(f"SDK environment creation failed: {e}")
            if use_sdk:
                print("Falling back to HTTP...")
                env_result = create_environment_via_http(api_key, args.env_name)
                output["environment"] = env_result
                args.env_id = env_result["id"]
            else:
                raise

    if args.create_all or args.create_agents:
        if not args.env_id:
            print("ERROR: --env-id required for --create-agents")
            sys.exit(1)

        agents = create_all_agents(api_key, client, prompts, use_sdk=use_sdk)
        output["agents"] = agents
        output["environment_id"] = args.env_id

    if args.test:
        if not args.env_id:
            print("ERROR: --env-id required for --test")
            sys.exit(1)

        # Find the agent ID
        agent_id = None
        for agent in output.get("agents", []):
            if agent["name"] == args.agent_name:
                agent_id = agent["id"]
                break

        if not agent_id:
            print(
                f"ERROR: Agent '{args.agent_name}' not found in output. Run --create-agents first."
            )
            sys.exit(1)

        test_result = test_session(api_key, client, agent_id, args.env_id, use_sdk=use_sdk)
        output["test_result"] = test_result

    # Save output
    if output:
        OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_FILE.write_text(json.dumps(output, indent=2))
        print(f"\n=== Output saved to {OUTPUT_FILE} ===")


if __name__ == "__main__":
    main()
