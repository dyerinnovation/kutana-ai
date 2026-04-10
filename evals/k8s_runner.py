"""K8s in-cluster eval job runner.

Drives the full managed agent eval lifecycle against the internal cluster API.
Runs as a K8s Job — exits 0 on all pass, 1 on any fail.

Environment variables:
    KUTANA_API_URL: Internal API base URL
                   (default: http://api-server.kutana.svc:8000/api/v1)
    KUTANA_AUTH_TOKEN: Bearer token for API authentication
    REDIS_URL: Redis URL (default: redis://redis.kutana.svc:6379/0)
    KUTANA_AGENT_TIER: Model tier — haiku | sonnet | opus (default: haiku)
    EVAL_AGENTS: Comma-separated agent slugs or "all"
                 (default: meeting-notetaker)
    ANTHROPIC_API_KEY: Anthropic API key (used by the judge)
    LANGFUSE_PUBLIC_KEY: Optional — enables Langfuse score upload
    LANGFUSE_SECRET_KEY: Optional — enables Langfuse score upload
    LANGFUSE_HOST: Langfuse host (default: http://langfuse.kutana.svc:3000)

Usage:
    python evals/k8s_runner.py
    python evals/k8s_runner.py --agents meeting-notetaker,meeting-summarizer
    python evals/k8s_runner.py --agents all
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any

from evals.conftest import get_rubric_for_agent, load_rubric, load_scenario, load_transcript
from evals.e2e_runner import E2ERunner
from evals.judge import judge_agent_response
from evals.models import (  # noqa: TC001 — runtime usage
    EvalResult,
    Rubric,
    Scenario,
    TranscriptSegment,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_API_URL = "http://api-server.kutana.svc:8000/v1"
DEFAULT_REDIS_URL = "redis://redis.kutana.svc:6379/0"
DEFAULT_LANGFUSE_HOST = "http://langfuse.kutana.svc:3000"

TIER_MODELS: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}

ALL_AGENT_SLUGS: list[str] = [
    "meeting-notetaker",
    "meeting-summarizer",
    "action-item-tracker",
    "decision-logger",
    "standup-facilitator",
    "code-discussion-tracker",
    "sprint-retro-coach",
    "sprint-planner",
    "user-interviewer",
    "initial-interviewer",
]

EVALS_DIR = Path(__file__).parent
DATA_DIR = EVALS_DIR / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
RUBRICS_DIR = DATA_DIR / "rubrics"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def resolve_agent_slugs(agents_arg: str) -> list[str]:
    """Resolve the --agents CLI arg to a list of agent slugs.

    Args:
        agents_arg: "all" or a comma-separated list of slugs.

    Returns:
        List of agent slugs to evaluate.
    """
    if agents_arg.strip().lower() == "all":
        return list(ALL_AGENT_SLUGS)
    return [s.strip() for s in agents_arg.split(",") if s.strip()]


def load_all_rubrics() -> dict[str, Rubric]:
    """Load all rubric files from data/rubrics/. Keyed by rubric_id."""
    rubrics: dict[str, Rubric] = {}
    if not RUBRICS_DIR.exists():
        return rubrics
    for path in sorted(RUBRICS_DIR.glob("*.json")):
        rubric = load_rubric(path)
        rubrics[rubric.rubric_id] = rubric
    return rubrics


def load_scenarios_for_agents(slugs: list[str]) -> list[tuple[str, Scenario]]:
    """Load all scenarios for the given agent slugs.

    Args:
        slugs: Agent slug names (e.g. "meeting-notetaker").

    Returns:
        List of (scenario_slug, Scenario) pairs.
    """
    results: list[tuple[str, Scenario]] = []
    for slug in slugs:
        agent_dir = SCENARIOS_DIR / slug
        if not agent_dir.exists():
            logger.warning("No scenario directory for agent '%s' at %s", slug, agent_dir)
            continue
        for path in sorted(agent_dir.glob("*.json")):
            scenario = load_scenario(path)
            results.append((path.stem, scenario))
    return results


def format_transcript(segments: list[TranscriptSegment]) -> str:
    """Format transcript segments as a plain text string for the judge prompt.

    Args:
        segments: List of transcript segments.

    Returns:
        Formatted transcript string.
    """
    lines: list[str] = []
    for seg in segments:
        ts = f"[{seg.timestamp_seconds:.0f}s] " if seg.timestamp_seconds else ""
        lines.append(f"{ts}{seg.speaker}: {seg.text}")
    return "\n".join(lines)


def make_langfuse_client() -> Any | None:
    """Create a Langfuse client from environment variables, or return None."""
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    host = os.environ.get("LANGFUSE_HOST", DEFAULT_LANGFUSE_HOST)

    if not public_key or not secret_key:
        logger.info("Langfuse env vars not set — score upload disabled")
        return None

    try:
        from langfuse import Langfuse

        client = Langfuse(public_key=public_key, secret_key=secret_key, host=host)
        logger.info("Langfuse client initialised (host=%s)", host)
        return client
    except ImportError:
        logger.warning("langfuse package not installed — score upload disabled")
        return None


# ---------------------------------------------------------------------------
# Core eval loop
# ---------------------------------------------------------------------------


async def run_scenario(
    runner: E2ERunner,
    scenario: Scenario,
    rubrics: dict[str, Rubric],
    model: str,
    langfuse: Any | None,
) -> EvalResult:
    """Run one scenario end-to-end and return a judged EvalResult.

    Args:
        runner: Connected E2ERunner (context manager already entered).
        scenario: The scenario to evaluate.
        rubrics: All loaded rubrics keyed by rubric_id.
        model: Model ID to pass when activating the agent.
        langfuse: Optional Langfuse client for score upload.

    Returns:
        Judged EvalResult.
    """
    # Load transcript segments
    transcript_path = TRANSCRIPTS_DIR / scenario.transcript_ref.replace("transcripts/", "")
    if not transcript_path.exists():
        # try relative from DATA_DIR
        transcript_path = DATA_DIR / scenario.transcript_ref
    segments_raw = load_transcript(transcript_path)
    segments: list[dict[str, Any]] = [
        {
            "speaker": s.speaker,
            "text": s.text,
            "timestamp_seconds": s.timestamp_seconds,
        }
        for s in segments_raw
    ]

    title = f"[eval] {scenario.meeting_context.title}"
    logger.info(
        "Running scenario %s | template=%s | segments=%d",
        scenario.scenario_id,
        scenario.agent_template,
        len(segments),
    )

    e2e_result = await runner.run_e2e_eval(
        title=title,
        template_name=scenario.agent_template,
        segments=segments,
        participants=scenario.meeting_context.participants,
        segment_delay=1.0,
        observe_timeout=120.0,
        max_events=200,
        model=model,
    )

    transcript_text = format_transcript(segments_raw)
    agent_response = e2e_result.summary_text or "\n".join(e2e_result.agent_messages)
    if e2e_result.tool_calls:
        tool_summary = "\n".join(f"- {tc['tool_name']}" for tc in e2e_result.tool_calls)
        agent_response = f"{agent_response}\n\nTool calls:\n{tool_summary}".strip()

    rubric = get_rubric_for_agent(scenario.agent_template, rubrics)

    eval_result = await judge_agent_response(
        scenario=scenario,
        rubric=rubric,
        transcript_text=transcript_text,
        agent_response=agent_response,
        langfuse=langfuse,
    )
    eval_result.tool_calls_captured = e2e_result.tool_calls

    status = "PASS" if eval_result.passed else "FAIL"
    logger.info(
        "[%s] %s — overall=%.2f (threshold=%.1f)",
        status,
        scenario.scenario_id,
        eval_result.overall_score,
        scenario.passing_score,
    )
    for score in eval_result.scores:
        logger.info(
            "  criterion=%s score=%.1f reason=%s",
            score.criterion,
            score.score,
            score.reason[:80],
        )

    return eval_result


async def main(agent_slugs: list[str]) -> int:
    """Drive the full eval lifecycle.

    Args:
        agent_slugs: Agent slugs to evaluate.

    Returns:
        0 if all scenarios passed, 1 if any failed.
    """
    api_url = os.environ.get("KUTANA_API_URL", DEFAULT_API_URL)
    auth_token = os.environ.get("KUTANA_AUTH_TOKEN", "")
    redis_url = os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
    tier = os.environ.get("KUTANA_AGENT_TIER", "haiku")
    model = TIER_MODELS.get(tier, TIER_MODELS["haiku"])

    if not auth_token:
        logger.error("KUTANA_AUTH_TOKEN is not set — cannot authenticate with the cluster API")
        return 1

    logger.info("Eval job starting")
    logger.info("  api_url=%s", api_url)
    logger.info("  redis_url=%s", redis_url)
    logger.info("  model=%s (tier=%s)", model, tier)
    logger.info("  agents=%s", agent_slugs)

    rubrics = load_all_rubrics()
    scenario_pairs = load_scenarios_for_agents(agent_slugs)

    if not scenario_pairs:
        logger.error("No scenarios found for agents: %s", agent_slugs)
        return 1

    logger.info("Loaded %d scenarios across %d agents", len(scenario_pairs), len(agent_slugs))

    langfuse = make_langfuse_client()

    results: list[EvalResult] = []
    failed: list[str] = []

    async with E2ERunner(
        api_base=api_url,
        auth_token=auth_token,
        redis_url=redis_url,
        model=model,
    ) as runner:
        for _scenario_slug, scenario in scenario_pairs:
            try:
                result = await run_scenario(
                    runner=runner,
                    scenario=scenario,
                    rubrics=rubrics,
                    model=model,
                    langfuse=langfuse,
                )
                results.append(result)
                if not result.passed:
                    failed.append(scenario.scenario_id)
            except Exception:
                logger.exception("Scenario %s raised an exception", scenario.scenario_id)
                failed.append(scenario.scenario_id)

    # Flush Langfuse
    if langfuse is not None:
        try:
            langfuse.flush()
            langfuse.shutdown()
        except Exception:
            logger.warning("Langfuse flush failed", exc_info=True)

    # Summary
    total = len(scenario_pairs)
    passed_count = len(results) - len(failed)
    logger.info("=" * 60)
    logger.info("Eval summary: %d/%d passed", passed_count, total)
    if failed:
        logger.error("Failed scenarios:")
        for fid in failed:
            logger.error("  - %s", fid)
    else:
        logger.info("All scenarios passed.")
    logger.info("=" * 60)

    return 0 if not failed else 1


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Kutana K8s eval job runner")
    default_agents = os.environ.get("EVAL_AGENTS", "meeting-notetaker")
    parser.add_argument(
        "--agents",
        default=default_agents,
        help=(
            'Comma-separated agent slugs or "all". '
            'Default: EVAL_AGENTS env var or "meeting-notetaker".'
        ),
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    slugs = resolve_agent_slugs(args.agents)
    exit_code = asyncio.run(main(slugs))
    sys.exit(exit_code)
