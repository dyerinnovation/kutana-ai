"""Mock eval runner: system prompt + transcript -> Messages API -> tool_use blocks.

Simulates agent behavior by sending the agent's system prompt and a
synthetic transcript through the Anthropic Messages API with Kutana
tool definitions, then captures the resulting tool_use blocks.

Optionally traces each eval run to Langfuse when a client is provided.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING, Any

import anthropic

if TYPE_CHECKING:
    from langfuse import Langfuse

    from evals.models import Scenario, TranscriptSegment

logger = logging.getLogger(__name__)

DEFAULT_MODEL = os.environ.get("EVAL_MODEL", "claude-sonnet-4-6")
DEFAULT_MAX_TOKENS = 4096

# Kutana MCP tool definitions (subset used in mock evals).
# These mirror the real tool schemas so the model generates realistic tool_use.
KUTANA_TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
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
        "name": "kutana_raise_hand",
        "description": "Request a turn to speak in the meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
            },
            "required": ["meeting_id"],
        },
    },
    {
        "name": "kutana_mark_finished_speaking",
        "description": "Signal that you have finished speaking.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
            },
            "required": ["meeting_id"],
        },
    },
    {
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
        "name": "kutana_get_participants",
        "description": "Get the list of participants in the meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
            },
            "required": ["meeting_id"],
        },
    },
    {
        "name": "kutana_get_meeting_status",
        "description": "Get the current meeting status snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
            },
            "required": ["meeting_id"],
        },
    },
    {
        "name": "kutana_get_tasks",
        "description": "Get tasks/action items tracked for this meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
            },
            "required": ["meeting_id"],
        },
    },
    {
        "name": "kutana_get_chat_messages",
        "description": "Read chat message history for this meeting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
            },
            "required": ["meeting_id"],
        },
    },
    {
        "name": "kutana_get_meeting_events",
        "description": "Get real-time meeting events (joins, leaves, etc.).",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
            },
            "required": ["meeting_id"],
        },
    },
    {
        "name": "kutana_get_queue_status",
        "description": "Check the speaker queue status.",
        "input_schema": {
            "type": "object",
            "properties": {
                "meeting_id": {"type": "string"},
            },
            "required": ["meeting_id"],
        },
    },
    {
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


def format_transcript(
    segments: list[TranscriptSegment],
    meeting_context_header: str,
) -> str:
    """Format transcript segments into a text block for the agent.

    Args:
        segments: Parsed transcript segments.
        meeting_context_header: Meeting context header (title, participants).

    Returns:
        Formatted transcript string.
    """
    lines: list[str] = [meeting_context_header, "", "## Transcript Update", ""]
    for seg in segments:
        minutes = int(seg.timestamp_seconds // 60)
        seconds = int(seg.timestamp_seconds % 60)
        lines.append(f"[{minutes:02d}:{seconds:02d}] {seg.speaker}: {seg.text}")
    return "\n".join(lines)


def _build_tool_results(tool_use_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build synthetic tool results for tool_use blocks so the conversation can continue.

    Args:
        tool_use_blocks: tool_use content blocks from the model response.

    Returns:
        List of tool_result messages.
    """
    results: list[dict[str, Any]] = []
    for block in tool_use_blocks:
        tool_name = block.get("name", "")
        result_content: str
        if tool_name == "kutana_get_transcript":
            result_content = '{"segments": [], "message": "No new segments"}'
        elif tool_name == "kutana_get_participants":
            result_content = (
                '{"participants": [{"name": "Alice"}, {"name": "Bob"}, {"name": "Charlie"}]}'
            )
        elif tool_name == "kutana_get_meeting_status":
            result_content = '{"status": "active", "title": "Meeting", "participants_count": 3}'
        elif tool_name == "kutana_get_tasks":
            result_content = '{"tasks": []}'
        elif tool_name == "kutana_get_chat_messages":
            result_content = '{"messages": []}'
        elif tool_name == "kutana_get_meeting_events":
            result_content = '{"events": []}'
        elif tool_name == "kutana_get_queue_status":
            result_content = '{"queue": [], "active_speaker": null}'
        elif tool_name == "kutana_send_chat_message":
            result_content = '{"status": "sent"}'
        elif tool_name == "kutana_create_task":
            result_content = '{"status": "created", "task_id": "eval-task-001"}'
        elif tool_name == "kutana_raise_hand":
            result_content = '{"position": 1}'
        elif tool_name == "kutana_mark_finished_speaking":
            result_content = '{"status": "ok"}'
        else:
            result_content = '{"status": "ok"}'

        results.append(
            {
                "type": "tool_result",
                "tool_use_id": block["id"],
                "content": result_content,
            }
        )
    return results


async def run_mock_eval(
    system_prompt: str,
    scenario: Scenario,
    transcript_segments: list[TranscriptSegment],
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
    max_turns: int = 5,
    langfuse: Langfuse | None = None,
) -> tuple[str, list[dict[str, Any]], str | None]:
    """Run a mock eval: send system prompt + transcript, capture tool_use blocks.

    Performs a multi-turn conversation with the model, providing synthetic
    tool results after each tool_use response, up to ``max_turns``.

    Args:
        system_prompt: The agent's system prompt.
        scenario: Eval scenario with meeting context.
        transcript_segments: Synthetic transcript segments.
        api_key: Anthropic API key. Uses env var if None.
        model: Model to use for the eval.
        max_turns: Maximum conversation turns.
        langfuse: Optional Langfuse client for tracing.

    Returns:
        Tuple of (formatted agent response text, list of tool_use blocks,
        Langfuse trace ID or None if tracing disabled).
    """
    client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()

    ctx = scenario.meeting_context
    context_header = (
        f"## Meeting Started: {ctx.title}\n"
        f"**Participants:** {', '.join(ctx.participants)}\n"
        f"**Duration:** {ctx.duration_minutes} minutes"
    )

    transcript_text = format_transcript(transcript_segments, context_header)

    # Create Langfuse trace for this eval run (one trace per scenario;
    # the judge attaches to this same trace via trace_id).
    trace = None
    if langfuse is not None:
        trace = langfuse.trace(
            name=f"eval/{scenario.agent_template}/{scenario.scenario_id}",
            metadata={
                "scenario_id": scenario.scenario_id,
                "agent_template": scenario.agent_template,
                "model": model,
                "meeting_title": ctx.title,
                "participant_count": len(ctx.participants),
            },
            tags=["eval", "mock", scenario.agent_template.lower().replace(" ", "-")],
            session_id=scenario.scenario_id,
        )

    messages: list[dict[str, Any]] = [
        {"role": "user", "content": transcript_text},
    ]

    all_tool_calls: list[dict[str, Any]] = []
    all_text_parts: list[str] = []

    for turn in range(max_turns):
        # Create a generation span for each API call
        generation = None
        if trace is not None:
            generation = trace.generation(
                name=f"agent-turn-{turn}",
                model=model,
                input=messages[-1]["content"][:500] if messages else "",
                metadata={"turn": turn},
            )

        response = await client.messages.create(
            model=model,
            max_tokens=DEFAULT_MAX_TOKENS,
            system=system_prompt,
            tools=KUTANA_TOOL_DEFINITIONS,
            messages=messages,
        )

        # Extract text and tool_use blocks
        text_parts: list[str] = []
        tool_use_blocks: list[dict[str, Any]] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_use_blocks.append(
                    {
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )

        # End generation span with output and usage
        if generation is not None:
            generation.end(
                output="\n".join(text_parts) or f"[{len(tool_use_blocks)} tool calls]",
                usage={
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                },
            )

        all_text_parts.extend(text_parts)
        all_tool_calls.extend(tool_use_blocks)

        # If no tool calls, conversation is done
        if not tool_use_blocks:
            break

        # Add assistant response and synthetic tool results for next turn
        messages.append({"role": "assistant", "content": response.content})

        tool_results = _build_tool_results(tool_use_blocks)
        messages.append({"role": "user", "content": tool_results})

    agent_response = "\n".join(all_text_parts)
    if all_tool_calls:
        agent_response += "\n\n## Tool Calls\n"
        for tc in all_tool_calls:
            agent_response += f"- {tc['name']}({json.dumps(tc['input'], indent=2)})\n"

    # Update trace with final output
    if trace is not None:
        trace.update(
            output={
                "tool_call_count": len(all_tool_calls),
                "turns": min(turn + 1, max_turns),
                "response_length": len(agent_response),
            },
        )

    trace_id = trace.id if trace is not None else None
    return agent_response, all_tool_calls, trace_id
