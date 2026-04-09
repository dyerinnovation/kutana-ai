"""Eval tests for Business tier agents: Sprint Retro Coach, Sprint Planner,
User Interviewer, Initial Interviewer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from evals.conftest import (
    DATA_DIR,
    get_rubric_for_agent,
    load_scenario,
    load_transcript,
)
from evals.judge import judge_agent_response
from evals.mock_runner import format_transcript, run_mock_eval

if TYPE_CHECKING:
    from evals.models import Rubric, Scenario

# ---------------------------------------------------------------------------
# Discover scenarios
# ---------------------------------------------------------------------------

BUSINESS_AGENTS = [
    "sprint-retro-coach",
    "sprint-planner",
    "user-interviewer",
    "initial-interviewer",
]

_business_scenarios: list[tuple[str, Scenario]] = []
for _agent_slug in BUSINESS_AGENTS:
    _scenario_dir = DATA_DIR / "scenarios" / _agent_slug
    if _scenario_dir.exists():
        for _path in sorted(_scenario_dir.glob("*.json")):
            _scenario = load_scenario(_path)
            _business_scenarios.append((_path.stem, _scenario))


# ---------------------------------------------------------------------------
# Mock eval tests
# ---------------------------------------------------------------------------


@pytest.mark.mock
@pytest.mark.parametrize(
    "scenario_name,scenario",
    _business_scenarios,
    ids=[f"{s.agent_template}/{name}" for name, s in _business_scenarios],
)
async def test_business_agent_mock(
    scenario_name: str,
    scenario: Scenario,
    system_prompts: dict[str, str],
    all_rubrics: dict[str, Rubric],
    anthropic_api_key: str,
) -> None:
    """Run mock eval for a Business tier agent scenario."""
    prompt = system_prompts.get(scenario.agent_template)
    if not prompt:
        pytest.skip(f"System prompt not found for {scenario.agent_template}")

    transcript_path = DATA_DIR / scenario.transcript_ref
    if not transcript_path.exists():
        pytest.skip(f"Transcript not found: {scenario.transcript_ref}")
    segments = load_transcript(transcript_path)

    agent_response, tool_calls = await run_mock_eval(
        system_prompt=prompt,
        scenario=scenario,
        transcript_segments=segments,
        api_key=anthropic_api_key,
    )

    rubric = get_rubric_for_agent(scenario.agent_template, all_rubrics)

    ctx = scenario.meeting_context
    transcript_text = format_transcript(
        segments,
        f"## {ctx.title}\nParticipants: {', '.join(ctx.participants)}",
    )

    result = await judge_agent_response(
        scenario=scenario,
        rubric=rubric,
        transcript_text=transcript_text,
        agent_response=agent_response,
        api_key=anthropic_api_key,
    )

    assert result.overall_score >= scenario.passing_score, (
        f"Agent '{scenario.agent_template}' scored {result.overall_score:.1f} "
        f"(need {scenario.passing_score}) on {scenario.scenario_id}.\n"
        f"Scores: {[(s.criterion, s.score, s.reason) for s in result.scores]}"
    )


# ---------------------------------------------------------------------------
# E2E eval tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.parametrize(
    "scenario_name,scenario",
    [(name, s) for name, s in _business_scenarios if "happy-path" in name],
    ids=[f"{s.agent_template}/{name}" for name, s in _business_scenarios if "happy-path" in name],
)
async def test_business_agent_e2e(
    scenario_name: str,
    scenario: Scenario,
    e2e_runner: object,
    all_rubrics: dict[str, Rubric],
    anthropic_api_key: str,
) -> None:
    """Run E2E eval for a Business tier agent happy-path scenario."""
    from evals.e2e_runner import E2ERunner

    assert isinstance(e2e_runner, E2ERunner)
    runner = e2e_runner

    transcript_path = DATA_DIR / scenario.transcript_ref
    if not transcript_path.exists():
        pytest.skip(f"Transcript not found: {scenario.transcript_ref}")
    segments = load_transcript(transcript_path)

    meeting_id = await runner.create_meeting(scenario.meeting_context.title)
    try:
        await runner.activate_agent(meeting_id, scenario.agent_template)
        await runner.start_meeting(meeting_id)

        raw_segments = [
            {
                "speaker": s.speaker,
                "text": s.text,
                "timestamp_seconds": s.timestamp_seconds,
            }
            for s in segments
        ]
        await runner.inject_transcript(meeting_id, raw_segments)

        events = await runner.observe_agent_events(meeting_id, timeout=90.0)

        agent_response_parts: list[str] = []
        for evt in events:
            evt_type = evt.get("event_type", "")
            payload = evt.get("payload", {})
            if evt_type == "agent.message":
                agent_response_parts.append(str(payload.get("content", "")))
            elif evt_type == "agent.mcp_tool_use":
                agent_response_parts.append(f"[tool_use: {payload.get('tool_name', '')}]")

        agent_response = "\n".join(agent_response_parts) or "(no agent output observed)"

        rubric = get_rubric_for_agent(scenario.agent_template, all_rubrics)
        ctx = scenario.meeting_context
        transcript_text = format_transcript(
            segments,
            f"## {ctx.title}\nParticipants: {', '.join(ctx.participants)}",
        )

        result = await judge_agent_response(
            scenario=scenario,
            rubric=rubric,
            transcript_text=transcript_text,
            agent_response=agent_response,
            api_key=anthropic_api_key,
        )

        assert result.overall_score >= scenario.passing_score, (
            f"E2E: Agent '{scenario.agent_template}' scored {result.overall_score:.1f} "
            f"(need {scenario.passing_score}) on {scenario.scenario_id}"
        )

        await runner.end_meeting(meeting_id)
    finally:
        await runner.cleanup_meeting(meeting_id)
