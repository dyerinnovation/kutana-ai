"""Pydantic models for the eval framework."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    """A single transcript segment from a synthetic transcript file."""

    speaker: str
    text: str
    timestamp_seconds: float = 0.0


class MeetingContext(BaseModel):
    """Meeting metadata injected into the agent's context."""

    title: str
    participants: list[str]
    duration_minutes: int


class Scenario(BaseModel):
    """A single evaluation scenario for an agent.

    Loaded from ``/evals/data/scenarios/<agent>/<scenario>.json``.
    """

    scenario_id: str = Field(
        description="Unique ID, e.g. 'meeting-notetaker/happy-path-standup'",
    )
    agent_template: str = Field(
        description="Agent template name, e.g. 'Meeting Notetaker'",
    )
    transcript_ref: str = Field(
        description="Relative path to transcript JSON, e.g. 'transcripts/standup-10min-3speakers.json'",
    )
    meeting_context: MeetingContext
    expected_behaviors: list[str] = Field(
        description="Behaviors the agent should exhibit",
    )
    anti_patterns: list[str] = Field(
        default_factory=list,
        description="Behaviors the agent must NOT exhibit",
    )
    passing_score: float = Field(
        default=3.5,
        description="Minimum overall score (1-5) to pass",
    )


class RubricCriterion(BaseModel):
    """A single scoring criterion within a rubric."""

    name: str
    description: str
    weight: float = Field(default=1.0, ge=0.0)


class Rubric(BaseModel):
    """Scoring rubric applied by the LLM-as-Judge.

    Loaded from ``/evals/data/rubrics/<agent>.json`` or ``common.json``.
    """

    rubric_id: str
    agent_template: str | None = Field(
        default=None,
        description="None for common rubric, agent name for agent-specific",
    )
    criteria: list[RubricCriterion]


class JudgeScore(BaseModel):
    """Score for a single criterion returned by the LLM judge."""

    criterion: str
    score: float = Field(ge=1.0, le=5.0)
    reason: str


class EvalResult(BaseModel):
    """Complete evaluation result for a single scenario run."""

    scenario_id: str
    agent_template: str
    scores: list[JudgeScore]
    overall_score: float = Field(ge=1.0, le=5.0)
    passed: bool
    tool_calls_captured: list[dict[str, object]] = Field(default_factory=list)
    raw_agent_response: str = ""
