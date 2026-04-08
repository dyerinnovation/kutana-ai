"""Kutana AI Demo Agent — minimal Claude-powered meeting agent.

Connects directly to the Kutana AI agent gateway via WebSocket, receives
live transcript segments and entity extraction events, and uses Claude Sonnet
with tool use to respond intelligently.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    export KUTANA_API_KEY=ktn_...
    export KUTANA_API_URL=http://localhost:8000
    python agent.py --meeting-id <uuid>
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Any

SYSTEM_PROMPT = """You are a demo AI agent connected to a Kutana AI meeting via WebSocket.
You receive live transcript segments and entity extraction events from the meeting.

Your role:
1. Monitor the transcript for action items, decisions, and key points.
2. When someone assigns a task or requests follow-up, use accept_task to acknowledge it.
3. When asked a direct question or prompted to respond, use reply.
4. Use get_meeting_recap to summarize what has been extracted so far.

Keep responses concise. Only act when there is something meaningful to respond to."""

TOOLS: list[dict[str, Any]] = [
    {
        "name": "accept_task",
        "description": "Acknowledge and accept a task or action item from the meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "The task description to accept.",
                },
                "comment": {
                    "type": "string",
                    "description": "Optional comment on the task (e.g. expected timeline).",
                },
            },
            "required": ["description"],
        },
    },
    {
        "name": "reply",
        "description": "Send a text message to the meeting channel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The message to send to participants.",
                },
            },
            "required": ["message"],
        },
    },
    {
        "name": "get_meeting_recap",
        "description": (
            "Get the current meeting recap: recent transcript and all extracted entities "
            "(tasks, decisions, key points, etc.)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]


class DemoAgent:
    """Minimal Kutana AI demo agent using the Anthropic SDK directly.

    Attributes:
        meeting_id: UUID of the meeting to join.
        kutana_api_url: Base URL of the Kutana AI API server.
        kutana_api_key: Agent API key (ktn_...) for token exchange.
        gateway_url: WebSocket URL of the agent gateway.
        anthropic_api_key: Anthropic API key for Claude.
    """

    def __init__(
        self,
        meeting_id: str,
        kutana_api_key: str,
        kutana_api_url: str,
        anthropic_api_key: str,
        gateway_url: str,
    ) -> None:
        """Initialise the demo agent.

        Args:
            meeting_id: UUID of the meeting to join.
            kutana_api_key: Agent API key for gateway token exchange.
            kutana_api_url: HTTP base URL of the Kutana AI API server.
            anthropic_api_key: Anthropic API key.
            gateway_url: WebSocket base URL of the agent gateway.
        """
        self.meeting_id = meeting_id
        self.kutana_api_url = kutana_api_url
        self.kutana_api_key = kutana_api_key
        self.gateway_url = gateway_url
        self.event_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.transcript_buffer: list[str] = []
        self.entity_buffer: list[dict[str, Any]] = []
        self._anthropic_api_key = anthropic_api_key

    async def _get_gateway_token(self) -> str:
        """Exchange the agent API key for a short-lived gateway JWT.

        Returns:
            The gateway JWT string.

        Raises:
            SystemExit: If the exchange fails.
        """
        try:
            import httpx
        except ImportError:
            print("httpx not installed. Run: pip install httpx")
            sys.exit(1)

        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(
                f"{self.kutana_api_url}/api/v1/token/gateway",
                headers={"X-API-Key": self.kutana_api_key},
            )
            if resp.status_code != 200:
                print(f"Token exchange failed ({resp.status_code}): {resp.text}")
                sys.exit(1)
            return resp.json()["token"]

    async def _listen(self, ws: Any) -> None:
        """Background task: receive WebSocket messages and push to queue.

        Args:
            ws: The open WebSocket connection.
        """
        try:
            async for message in ws:
                try:
                    data = json.loads(message)
                    await self.event_queue.put(data)
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass  # Connection closed

    def _print_event(self, data: dict[str, Any]) -> None:
        """Print a WebSocket event in a readable format.

        Args:
            data: Parsed JSON message dict.
        """
        msg_type = data.get("type", "unknown")
        if msg_type == "transcript":
            speaker = data.get("speaker_id") or "?"
            text = data.get("text", "")
            print(f"  [TRANSCRIPT] {speaker}: {text}")
        elif msg_type == "event":
            event_type = data.get("event_type", "?")
            payload = data.get("payload", {})
            entity_count = len(payload.get("entities", []))
            if entity_count:
                print(f"  [EVENT:{event_type}] {entity_count} entities extracted")
            else:
                summary = json.dumps(payload)[:60]
                print(f"  [EVENT:{event_type}] {summary}")
        elif msg_type == "participant_update":
            action = data.get("action", "?")
            name = data.get("name", "?")
            print(f"  [PARTICIPANT] {action}: {name}")
        elif msg_type == "joined":
            caps = data.get("granted_capabilities", [])
            print(f"  [JOINED] meeting={data.get('meeting_id', '?')} caps={caps}")
        elif msg_type == "error":
            print(f"  [ERROR] {data.get('code', '?')}: {data.get('message', '?')}")

    async def _drain_events(self) -> str:
        """Drain the event queue and return a summary string for Claude.

        Returns:
            Newline-separated summary of new events, or a no-events message.
        """
        lines: list[str] = []
        while not self.event_queue.empty():
            data = await self.event_queue.get()
            self._print_event(data)
            msg_type = data.get("type")
            if msg_type == "transcript":
                speaker = data.get("speaker_id") or "Unknown"
                text = data.get("text", "")
                entry = f"{speaker}: {text}"
                self.transcript_buffer.append(entry)
                lines.append(f"[Transcript] {entry}")
            elif msg_type == "event":
                event_type = data.get("event_type", "")
                payload = data.get("payload", {})
                entities = payload.get("entities", [])
                if entities:
                    for entity in entities:
                        self.entity_buffer.append(entity)
                    lines.append(
                        f"[Extraction:{event_type}] {len(entities)} new entities"
                    )
        return "\n".join(lines) if lines else "(no new events)"

    async def _execute_tool(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        ws: Any,
    ) -> str:
        """Execute a tool call and return the result string.

        Args:
            tool_name: Name of the tool to execute.
            tool_input: Input parameters for the tool.
            ws: The open WebSocket connection.

        Returns:
            Result string to feed back to Claude.
        """
        if tool_name == "accept_task":
            description = tool_input.get("description", "")
            comment = tool_input.get("comment", "")
            msg = {
                "type": "data",
                "channel": "task.accepted",
                "payload": {"description": description, "comment": comment},
            }
            await ws.send(json.dumps(msg))
            result = f"Task accepted: {description}"
            print(f"  [TOOL:accept_task] {result}")
            return result

        if tool_name == "reply":
            message = tool_input.get("message", "")
            msg = {
                "type": "data",
                "channel": "agent.reply",
                "payload": {"message": message, "meeting_id": self.meeting_id},
            }
            await ws.send(json.dumps(msg))
            result = f"Reply sent: {message[:60]}"
            print(f"  [TOOL:reply] Sent: {message[:60]}")
            return result

        if tool_name == "get_meeting_recap":
            recap = {
                "transcript_segments": len(self.transcript_buffer),
                "recent_transcript": self.transcript_buffer[-10:],
                "extracted_entities_count": len(self.entity_buffer),
                "recent_entities": self.entity_buffer[-10:],
            }
            result = json.dumps(recap, default=str, indent=2)
            print(
                f"  [TOOL:get_meeting_recap] "
                f"{len(self.transcript_buffer)} segments, "
                f"{len(self.entity_buffer)} entities"
            )
            return result

        return f"Unknown tool: {tool_name}"

    async def _run_agent_turn(self, context: str, ws: Any) -> None:
        """Run one agentic turn with Claude Sonnet.

        Builds the user message from recent context, invokes Claude with
        tools, executes any tool calls, and loops until Claude stops.

        Args:
            context: Summary of new meeting events since the last turn.
            ws: The open WebSocket connection.
        """
        try:
            import anthropic
        except ImportError:
            print("anthropic not installed. Run: pip install anthropic")
            return

        client = anthropic.AsyncAnthropic(api_key=self._anthropic_api_key)

        recent_transcript = "\n".join(self.transcript_buffer[-10:])
        user_content = (
            f"New meeting events:\n{context}\n\n"
            f"Recent transcript (last 10 lines):\n{recent_transcript}\n\n"
            "Analyze the new events and take action if appropriate. "
            "Only use tools when there is something genuinely worth acting on."
        )
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

        while True:
            response = await client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                tools=TOOLS,  # type: ignore[arg-type]
                messages=messages,  # type: ignore[arg-type]
            )

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            text_blocks = [b for b in response.content if b.type == "text"]

            if text_blocks:
                text = " ".join(b.text for b in text_blocks)
                if text.strip():
                    print(f"\n[AGENT] {text}\n")

            if response.stop_reason == "end_turn" or not tool_uses:
                break

            # Execute tools and feed results back
            messages.append({"role": "assistant", "content": response.content})  # type: ignore[arg-type]
            tool_results: list[dict[str, Any]] = []
            for tool_use in tool_uses:
                result = await self._execute_tool(
                    tool_use.name,
                    tool_use.input,  # type: ignore[arg-type]
                    ws,
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result,
                    }
                )
            messages.append({"role": "user", "content": tool_results})

    async def run(self) -> None:
        """Run the demo agent: authenticate, connect, and process events."""
        try:
            import websockets
        except ImportError:
            print("websockets not installed. Run: pip install websockets")
            sys.exit(1)

        print(f"Getting gateway token from {self.kutana_api_url} ...")
        token = await self._get_gateway_token()

        ws_url = f"{self.gateway_url}/agent/connect?token={token}"
        print(f"Connecting to {self.gateway_url} ...")

        async with websockets.connect(ws_url) as ws:
            print("WebSocket connected. Joining meeting ...")

            join_msg = {
                "type": "join_meeting",
                "meeting_id": self.meeting_id,
                "capabilities": ["listen", "transcribe", "extract_tasks"],
            }
            await ws.send(json.dumps(join_msg))

            listener = asyncio.create_task(self._listen(ws))
            print("Listening for events. Press Ctrl+C to stop.\n")

            turn = 0
            try:
                while True:
                    await asyncio.sleep(15)
                    context = await self._drain_events()
                    if context != "(no new events)":
                        turn += 1
                        print(f"\n--- Agent turn {turn} ---")
                        try:
                            await self._run_agent_turn(context, ws)
                        except Exception as exc:
                            print(f"[ERROR] Agent turn failed: {exc}")
            except (asyncio.CancelledError, KeyboardInterrupt):
                pass
            finally:
                listener.cancel()
                await asyncio.gather(listener, return_exceptions=True)
                print("\nAgent disconnected.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kutana AI demo agent — joins a meeting and monitors with Claude"
    )
    parser.add_argument(
        "--meeting-id",
        required=True,
        help="UUID of the meeting to join",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("KUTANA_API_URL", "http://localhost:8000"),
        help="Kutana AI API server URL (default: $KUTANA_API_URL or http://localhost:8000)",
    )
    parser.add_argument(
        "--gateway-url",
        default=os.environ.get("KUTANA_GATEWAY_URL", "ws://localhost:8003"),
        help="Agent gateway WebSocket URL (default: $KUTANA_GATEWAY_URL or ws://localhost:8003)",
    )
    return parser.parse_args()


async def main() -> None:
    """Entry point for the demo agent."""
    args = _parse_args()

    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    kutana_api_key = os.environ.get("KUTANA_API_KEY", "")

    if not anthropic_api_key:
        print("ANTHROPIC_API_KEY is not set. Export it before running.")
        sys.exit(1)
    if not kutana_api_key:
        print(
            "KUTANA_API_KEY is not set.\n"
            "Generate one via the dashboard or API:\n"
            "  POST /api/v1/agents/{id}/keys\n"
            "Then: export KUTANA_API_KEY=ktn_..."
        )
        sys.exit(1)

    print("Kutana AI Demo Agent")
    print(f"  Meeting ID : {args.meeting_id}")
    print(f"  API URL    : {args.api_url}")
    print(f"  Gateway URL: {args.gateway_url}")
    print()

    agent = DemoAgent(
        meeting_id=args.meeting_id,
        kutana_api_key=kutana_api_key,
        kutana_api_url=args.api_url,
        anthropic_api_key=anthropic_api_key,
        gateway_url=args.gateway_url,
    )
    await agent.run()


if __name__ == "__main__":
    asyncio.run(main())
