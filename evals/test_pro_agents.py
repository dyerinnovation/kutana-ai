"""Eval tests for Pro tier agents: Action Item Tracker, Decision Logger,
Standup Facilitator, Code Discussion Tracker."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from evals.conftest import (
    DATA_DIR,
    format_transcript,
    get_rubric_for_agent,
    load_scenario,
    load_transcript,
)
from evals.judge import judge_agent_response

if TYPE_CHECKING:
    from evals.models import Rubric, Scenario

# ---------------------------------------------------------------------------
# Discover scenarios
# ---------------------------------------------------------------------------

PRO_AGENTS = [
    "action-item-tracker",
    "decision-logger",
    "standup-facilitator",
    "code-discussion-tracker",
]

_pro_scenarios: list[tuple[str, Scenario]] = []
for _agent_slug in PRO_AGENTS:
    _scenario_dir = DATA_DIR / "scenarios" / _agent_slug
    if _scenario_dir.exists():
        for _path in sorted(_scenario_dir.glob("*.json")):
            _scenario = load_scenario(_path)
            _pro_scenarios.append((_path.stem, _scenario))


# ---------------------------------------------------------------------------
# E2E eval tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.parametrize(
    "scenario_name,scenario",
    [(name, s) for name, s in _pro_scenarios if "happy-path" in name],
    ids=[f"{s.agent_template}/{name}" for name, s in _pro_scenarios if "happy-path" in name],
)
async def test_pro_agent_e2e(
    scenario_name: str,
    scenario: Scenario,
    e2e_runner: object,
    all_rubrics: dict[str, Rubric],
    anthropic_api_key: str,
    langfuse_client: object,
) -> None:
    """Run E2E eval for a Pro tier agent happy-path scenario.

    Creates a real meeting on the dev cluster, runs the full managed-agent
    lifecycle via ``run_e2e_eval()``, and scores with LLM-as-Judge.
    Auto-skips when ``KUTANA_AUTH_TOKEN`` or ``ANTHROPIC_API_KEY`` are absent.
    """
    from evals.e2e_runner import E2ERunner

    assert isinstance(e2e_runner, E2ERunner)
    runner = e2e_runner

    transcript_path = DATA_DIR / scenario.transcript_ref
    if not transcript_path.exists():
        pytest.skip(f"Transcript not found: {scenario.transcript_ref}")
    segments = load_transcript(transcript_path)
    raw_segments = [
        {
            "speaker": s.speaker,
            "text": s.text,
            "timestamp_seconds": s.timestamp_seconds,
        }
        for s in segments
    ]

    # Run full lifecycle: create → activate → start → inject → observe → end → cleanup
    result = await runner.run_e2e_eval(
        title=scenario.meeting_context.title,
        template_name=scenario.agent_template,
        segments=raw_segments,
        observe_timeout=120.0,
    )

    # Assert no session errors before judging
    assert not result.errors, f"Agent session errors: {result.errors}"

    # Build agent response string for the judge
    agent_response_parts: list[str] = []
    for msg in result.agent_messages:
        agent_response_parts.append(msg)
    for tc in result.tool_calls:
        agent_response_parts.append(f"[tool_use: {tc.get('tool_name', '')}]")
    agent_response = "\n".join(agent_response_parts) or "(no agent output observed)"

    # Score via LLM-as-Judge
    rubric = get_rubric_for_agent(scenario.agent_template, all_rubrics)
    ctx = scenario.meeting_context
    transcript_text = format_transcript(
        segments,
        f"## {ctx.title}\nParticipants: {', '.join(ctx.participants)}",
    )

    eval_result = await judge_agent_response(
        scenario=scenario,
        rubric=rubric,
        transcript_text=transcript_text,
        agent_response=agent_response,
        api_key=anthropic_api_key,
        langfuse=langfuse_client,
    )

    assert eval_result.overall_score >= scenario.passing_score, (
        f"E2E: Agent '{scenario.agent_template}' scored {eval_result.overall_score:.1f} "
        f"(need {scenario.passing_score}) on {scenario.scenario_id}.\n"
        f"Scores: {[(s.criterion, s.score, s.reason) for s in eval_result.scores]}"
    )
