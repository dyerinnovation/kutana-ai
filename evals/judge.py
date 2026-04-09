"""LLM-as-Judge scoring for agent evaluation.

Uses the Anthropic Messages API with a structured scoring prompt to
evaluate agent behavior against rubric criteria.
"""

from __future__ import annotations

import json
import logging
import os

import anthropic

from evals.models import EvalResult, JudgeScore, Rubric, Scenario

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
) -> EvalResult:
    """Score an agent's response using LLM-as-Judge.

    Args:
        scenario: The eval scenario being tested.
        rubric: Scoring rubric with criteria.
        transcript_text: Formatted transcript the agent received.
        agent_response: Agent's output (text + tool_use blocks).
        api_key: Anthropic API key. Uses ``ANTHROPIC_API_KEY`` env var if None.

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

    response = await client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=JUDGE_MAX_TOKENS,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )

    raw_text = response.content[0].text
    # Strip markdown fences if the model wrapped its JSON
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]  # drop ```json line
        cleaned = cleaned.rsplit("```", 1)[0]  # drop trailing ```
    parsed = json.loads(cleaned)

    scores = [
        JudgeScore(
            criterion=s["criterion"],
            score=s["score"],
            reason=s["reason"],
        )
        for s in parsed["scores"]
    ]
    overall = float(parsed["overall"])

    return EvalResult(
        scenario_id=scenario.scenario_id,
        agent_template=scenario.agent_template,
        scores=scores,
        overall_score=overall,
        passed=overall >= scenario.passing_score,
        raw_agent_response=agent_response,
    )
