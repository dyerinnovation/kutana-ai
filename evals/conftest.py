"""Pytest fixtures for the eval framework.

Provides fixtures for MinIO, Langfuse, Anthropic, and dev cluster access.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import pytest

from evals.e2e_runner import E2ERunner
from evals.minio_client import EvalMinioClient
from evals.models import Rubric, Scenario, TranscriptSegment

logger = logging.getLogger(__name__)

# Try to import Langfuse; it's optional for evals
try:
    from langfuse import Langfuse
except ImportError:
    Langfuse = None  # type: ignore[assignment, misc]

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

EVALS_DIR = Path(__file__).parent
DATA_DIR = EVALS_DIR / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"
TRANSCRIPTS_DIR = DATA_DIR / "transcripts"
RUBRICS_DIR = DATA_DIR / "rubrics"

# Path to system prompts doc (parsed for agent prompt lookup)
SYSTEM_PROMPTS_PATH = (
    EVALS_DIR.parent / "internal-docs" / "development" / "managed-agent-system-prompts.md"
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anthropic_api_key() -> str:
    """Anthropic API key from environment."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        pytest.skip("ANTHROPIC_API_KEY not set")
    return key


@pytest.fixture(scope="session")
def langfuse_config() -> dict[str, str]:
    """Langfuse connection config from environment."""
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    host = os.environ.get("LANGFUSE_HOST", "http://localhost:3100")
    if not public_key or not secret_key:
        pytest.skip("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set")
    return {
        "public_key": public_key,
        "secret_key": secret_key,
        "host": host,
    }


@pytest.fixture(scope="session")
def langfuse_client() -> Langfuse | None:  # type: ignore[type-arg]
    """Optional Langfuse client for eval tracing.

    Returns None (tracing disabled) when Langfuse is not installed or
    LANGFUSE env vars are missing. Tests continue without tracing.
    """
    if Langfuse is None:
        logger.debug("Langfuse not installed — eval tracing disabled")
        return None

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY", "")
    host = os.environ.get("LANGFUSE_HOST", "http://localhost:3100")

    if not public_key or not secret_key:
        logger.debug("LANGFUSE env vars not set — eval tracing disabled")
        return None

    client = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
    )
    logger.info("Langfuse eval tracing enabled (host=%s)", host)
    yield client  # type: ignore[misc]
    client.flush()
    client.shutdown()


@pytest.fixture(scope="session")
def dev_cluster_config() -> dict[str, str]:
    """Dev cluster connection config from environment."""
    api_base = os.environ.get("KUTANA_API_BASE", "https://api-dev.kutana.ai/v1")
    auth_token = os.environ.get("KUTANA_AUTH_TOKEN", "")
    redis_url = os.environ.get("KUTANA_REDIS_URL", "redis://localhost:6379/0")
    if not auth_token:
        pytest.skip("KUTANA_AUTH_TOKEN not set")
    return {
        "api_base": api_base,
        "auth_token": auth_token,
        "redis_url": redis_url,
    }


# ---------------------------------------------------------------------------
# MinIO
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def minio_client() -> EvalMinioClient:
    """MinIO client for loading eval data."""
    return EvalMinioClient(
        endpoint_url=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        access_key=os.environ.get("MINIO_ACCESS_KEY", "kutana"),
        secret_key=os.environ.get("MINIO_SECRET_KEY", "kutana-minio-secret"),
        bucket=os.environ.get("MINIO_EVAL_BUCKET", "kutana-eval-data"),
    )


# ---------------------------------------------------------------------------
# E2E runner
# ---------------------------------------------------------------------------


@pytest.fixture
async def e2e_runner(dev_cluster_config: dict[str, str]) -> E2ERunner:
    """E2E runner connected to the dev cluster."""
    async with E2ERunner(
        api_base=dev_cluster_config["api_base"],
        auth_token=dev_cluster_config["auth_token"],
        redis_url=dev_cluster_config["redis_url"],
    ) as runner:
        yield runner


# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def system_prompts() -> dict[str, str]:
    """Load all 10 agent system prompts from the markdown doc.

    Returns:
        Mapping of agent template name -> system prompt text.
    """
    if not SYSTEM_PROMPTS_PATH.exists():
        pytest.skip(f"System prompts not found: {SYSTEM_PROMPTS_PATH}")

    content = SYSTEM_PROMPTS_PATH.read_text()
    prompts: dict[str, str] = {}

    # Parse code blocks after ### N. <Name> headings
    import re

    pattern = re.compile(
        r"###\s+\d+\.\s+(.+?)\n\s*```\n(.*?)```",
        re.DOTALL,
    )
    for match in pattern.finditer(content):
        name = match.group(1).strip()
        prompt = match.group(2).strip()
        prompts[name] = prompt

    return prompts


def load_scenario(path: Path) -> Scenario:
    """Load a scenario from a JSON file.

    Args:
        path: Path to the scenario JSON file.

    Returns:
        Parsed Scenario model.
    """
    return Scenario.model_validate_json(path.read_text())


def load_transcript(path: Path) -> list[TranscriptSegment]:
    """Load transcript segments from a JSON file.

    Args:
        path: Path to the transcript JSON file.

    Returns:
        List of parsed TranscriptSegment models.
    """
    data = json.loads(path.read_text())
    segments_raw = data.get("segments", data)
    return [TranscriptSegment.model_validate(s) for s in segments_raw]


def load_rubric(path: Path) -> Rubric:
    """Load a rubric from a JSON file.

    Args:
        path: Path to the rubric JSON file.

    Returns:
        Parsed Rubric model.
    """
    return Rubric.model_validate_json(path.read_text())


@pytest.fixture(scope="session")
def all_scenarios() -> list[Scenario]:
    """Load all scenario files from the data directory."""
    scenarios: list[Scenario] = []
    if not SCENARIOS_DIR.exists():
        return scenarios
    for agent_dir in sorted(SCENARIOS_DIR.iterdir()):
        if not agent_dir.is_dir():
            continue
        for path in sorted(agent_dir.glob("*.json")):
            scenarios.append(load_scenario(path))
    return scenarios


@pytest.fixture(scope="session")
def all_rubrics() -> dict[str, Rubric]:
    """Load all rubric files. Keyed by rubric_id."""
    rubrics: dict[str, Rubric] = {}
    if not RUBRICS_DIR.exists():
        return rubrics
    for path in sorted(RUBRICS_DIR.glob("*.json")):
        rubric = load_rubric(path)
        rubrics[rubric.rubric_id] = rubric
    return rubrics


def get_rubric_for_agent(
    agent_template: str,
    rubrics: dict[str, Rubric],
) -> Rubric:
    """Get the appropriate rubric for an agent (agent-specific or common).

    Args:
        agent_template: Agent template name.
        rubrics: All loaded rubrics keyed by rubric_id.

    Returns:
        Agent-specific rubric if available, otherwise the common rubric.

    Raises:
        KeyError: If no suitable rubric found.
    """
    # Try agent-specific first
    slug = agent_template.lower().replace(" ", "-")
    if slug in rubrics:
        return rubrics[slug]
    # Fall back to common
    if "common" in rubrics:
        return rubrics["common"]
    raise KeyError(f"No rubric found for agent '{agent_template}' and no common rubric")
