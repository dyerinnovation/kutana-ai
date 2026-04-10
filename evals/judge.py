"""LLM-as-Judge scoring for agent evaluation.

Uses the Anthropic Messages API with a structured scoring prompt to
evaluate agent behavior against rubric criteria.

Optionally traces judge calls and attaches scores to Langfuse when
a client is provided.
"""

from __future__ import annotations

import json
import logging
import os
from typing import TYPE_CHECKING

import anthropic

from evals.models import EvalResult, JudgeScore, Rubric, Scenario

if TYPE_CHECKING:
    from langfuse import Langfuse

logger = logging.getLogger(__name__)

JUDGE_MODEL = os.environ.get("EVAL_MODEL", "claude-sonnet-4-6")
JUDGE_MAX_TOKENS = 2048

JUDGE_SYSTEM_PROMPT = """\
You are an expert evaluator for AI meeting agents. You score agent behavior \
against specific criteria on a 1-5 scale.

Scoring guide:
  5 = Excellent — fully meets the criterion with no issues
  4 = Good — meets the criterion with minor issues
  3 = Acceptable — partially meets the criterion
  2 = Poor — mostly fails to meet the criterion
  1 = Failing — does not meet the criterion at all

You MUST respond with valid JSON only. No markdown, no explanations outside the JSON.
"""

JUDGE_USER_TEMPLATE = """\
## Scenario
Agent: {agent_template}
Scenario: {scenario_id}
Meeting: {meeting_title} ({duration_minutes} min, {participant_count} participants)

## Transcript (input to agent)
{transcript_text}

## Agent Response / Tool Calls
{agent_response}

## Expected Behaviors
{expected_behaviors}

## Anti-Patterns (should NOT occur)
{anti_patterns}

## Scoring Criteria
{criteria_text}

---

Rate the agent's response for EACH criterion on a 1-5 scale.

Respond with this exact JSON structure:
{{
  "scores": [
    {{"criterion": "<name>", "score": <1-5>, "reason": "<brief explanation>"}},
    ...
  ],
  "overall": <weighted average 1-5>
}}
"""


async def judge_agent_response(
    scenario: Scenario,
    rubric: Rubric,
    transcript_text: str,
    agent_response: str,
    api_key: str | None = None,
    langfuse: Langfuse | None = None,
    trace_id: str | None = None,
) -> EvalResult:
    """Score an agent's response using LLM-as-Judge.

    Args:
        scenario: The eval scenario being tested.
        rubric: Scoring rubric with criteria.
        transcript_text: Formatted transcript the agent received.
        agent_response: Agent's output (text + tool_use blocks).
        api_key: Anthropic API key. Uses ``ANTHROPIC_API_KEY`` env var if None.
        langfuse: Optional Langfuse client for tracing.
        trace_id: Optional trace ID to attach the judge span and scores to.

    Returns:
        Complete :class:`EvalResult` with per-criterion and overall scores.
    """
    client = anthropic.AsyncAnthropic(api_key=api_key) if api_key else anthropic.AsyncAnthropic()

    criteria_text = "\n".join(
        f"- **{c.name}** (weight {c.weight}): {c.description}" for c in rubric.criteria
    )

    user_content = JUDGE_USER_TEMPLATE.format(
        agent_template=scenario.agent_template,
        scenario_id=scenario.scenario_id,
        meeting_title=scenario.meeting_context.title,
        duration_minutes=scenario.meeting_context.duration_minutes,
        participant_count=len(scenario.meeting_context.participants),
        transcript_text=transcript_text,
        agent_response=agent_response,
        expected_behaviors="\n".join(f"- {b}" for b in scenario.expected_behaviors),
        anti_patterns="\n".join(f"- {a}" for a in scenario.anti_patterns) or "(none)",
        criteria_text=criteria_text,
    )

    # Create a Langfuse generation span for the judge call (v4 API)
    generation = None
    resolved_trace_id = trace_id
    if langfuse is not None:
        if not resolved_trace_id:
            # No trace from mock_runner — create a standalone trace ID
            resolved_trace_id = langfuse.create_trace_id(
                seed=f"eval-judge-{scenario.agent_template}/{scenario.scenario_id}",
            )
        trace_ctx = {"trace_id": resolved_trace_id, "parent_span_id": ""}
        generation = langfuse.start_observation(
            name="judge-scoring",
            trace_context=trace_ctx,
            as_type="generation",
            model=JUDGE_MODEL,
            input=user_content[:1000],
            metadata={
                "scenario_id": scenario.scenario_id,
                "rubric_id": rubric.rubric_id,
                "criteria_count": len(rubric.criteria),
                "agent_template": scenario.agent_template,
            },
        )

    response = await client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=JUDGE_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": JUDGE_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": "{"},
        ],
    )

    raw_text = "{" + response.content[0].text
    parsed = json.loads(raw_text)

    scores = [
        JudgeScore(
            criterion=s["criterion"],
            score=s["score"],
            reason=s["reason"],
        )
        for s in parsed["scores"]
    ]
    overall = float(parsed["overall"])

    # End generation span with judge output
    if generation is not None:
        generation.update(
            output=raw_text[:1000],
            usage_details={
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
            },
        )
        generation.end()

    # Attach scores to the trace
    if langfuse is not None and resolved_trace_id:
        langfuse.create_score(
            trace_id=resolved_trace_id,
            name="overall",
            value=overall,
            comment=f"{scenario.agent_template} / {scenario.scenario_id}",
        )
        for s in scores:
            langfuse.create_score(
                trace_id=resolved_trace_id,
                name=s.criterion,
                value=s.score,
                comment=s.reason,
            )

    return EvalResult(
        scenario_id=scenario.scenario_id,
        agent_template=scenario.agent_template,
        scores=scores,
        overall_score=overall,
        passed=overall >= scenario.passing_score,
        raw_agent_response=agent_response,
    )
