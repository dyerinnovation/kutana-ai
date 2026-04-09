# Eval Framework

Guide for writing scenarios, running evaluations, and interpreting results for Kutana's managed agent evaluation system.

---

## Overview

The eval framework tests the 10 managed agents across two modes:

| Mode | Marker | What it does | Requirements |
|------|--------|-------------|--------------|
| **Mock** | `-m mock` | System prompt + transcript → Messages API → tool_use blocks → LLM-as-Judge | `ANTHROPIC_API_KEY` |
| **E2E** | `-m e2e` | Real meeting on dev cluster → activate agent → observe MCP calls → Judge | Dev cluster + `KUTANA_AUTH_TOKEN` |

## Directory Structure

```
evals/
├── __init__.py
├── conftest.py          # Fixtures: MinIO, Langfuse, Anthropic, data loaders
├── mock_runner.py       # Mock eval runner (Messages API + synthetic tool results)
├── e2e_runner.py        # E2E eval runner (dev cluster)
├── judge.py             # LLM-as-Judge scoring
├── minio_client.py      # MinIO data access
├── models.py            # Pydantic models (Scenario, Rubric, EvalResult, etc.)
├── data/
│   ├── transcripts/     # 8 synthetic transcript JSON files
│   ├── scenarios/       # 30 scenario files (10 agents × 3 each)
│   └── rubrics/         # 11 rubric files (1 common + 10 agent-specific)
├── test_basic_agents.py
├── test_pro_agents.py
└── test_business_agents.py
```

## Writing Scenarios

Each scenario is a JSON file in `evals/data/scenarios/<agent-slug>/`:

```json
{
  "scenario_id": "meeting-notetaker/happy-path-standup",
  "agent_template": "Meeting Notetaker",
  "transcript_ref": "transcripts/standup-10min-3speakers.json",
  "meeting_context": {
    "title": "Daily Standup",
    "participants": ["Alice", "Bob", "Charlie"],
    "duration_minutes": 10
  },
  "expected_behaviors": [
    "Posts structured notes organized by topic",
    "Attributes statements to correct speakers"
  ],
  "anti_patterns": [
    "Uses kutana_raise_hand or kutana_speak",
    "Waits until end to post all notes"
  ],
  "passing_score": 3.5
}
```

### Scenario Types

Each agent has three scenarios:

1. **Happy path** — standard meeting that exercises the agent's core behavior
2. **Edge case** — unusual conditions (short meeting, few participants, non-matching meeting type)
3. **Adversarial** — stresses the agent (long meeting, heated discussion, many items to track)

### Agent Slug Convention

The agent directory name is the agent template name in lowercase, hyphenated:

| Agent Template | Directory Slug |
|---------------|---------------|
| Meeting Notetaker | `meeting-notetaker` |
| Meeting Summarizer | `meeting-summarizer` |
| Action Item Tracker | `action-item-tracker` |
| Decision Logger | `decision-logger` |
| Standup Facilitator | `standup-facilitator` |
| Code Discussion Tracker | `code-discussion-tracker` |
| Sprint Retro Coach | `sprint-retro-coach` |
| Sprint Planner | `sprint-planner` |
| User Interviewer | `user-interviewer` |
| Initial Interviewer | `initial-interviewer` |

## Writing Rubrics

Rubrics define scoring criteria. There are two types:

1. **Common rubric** (`rubrics/common.json`) — applies to all agents
2. **Agent-specific rubric** (`rubrics/<agent-slug>.json`) — tailored criteria

```json
{
  "rubric_id": "meeting-notetaker",
  "agent_template": "Meeting Notetaker",
  "criteria": [
    {
      "name": "Note Structure",
      "description": "Notes organized by topic with clear headers and bullet points.",
      "weight": 1.2
    }
  ]
}
```

The `weight` field controls how much each criterion contributes to the overall score. Default is 1.0.

## Running Evals

### Prerequisites

```bash
# Required for mock evals
export ANTHROPIC_API_KEY="sk-ant-..."

# Required for E2E evals
export KUTANA_AUTH_TOKEN="eyJ..."
export KUTANA_API_BASE="https://api-dev.kutana.ai/v1"
export KUTANA_REDIS_URL="redis://localhost:6379/0"

# Optional: Langfuse tracing
export LANGFUSE_PUBLIC_KEY="pk-..."
export LANGFUSE_SECRET_KEY="sk-..."
export LANGFUSE_HOST="http://localhost:3100"
```

### Run Commands

```bash
# All mock evals
uv run pytest evals/ -m mock -v

# All E2E evals
uv run pytest evals/ -m e2e -v --timeout=120

# Single agent
uv run pytest evals/test_basic_agents.py -k "meeting_notetaker" -v

# Single scenario
uv run pytest evals/ -k "happy_path_standup" -v
```

### Upload Eval Data to MinIO

```bash
# Upload all transcripts, scenarios, rubrics
python scripts/upload_eval_data.py

# Dry run (list files without uploading)
python scripts/upload_eval_data.py --dry-run

# Custom endpoint
python scripts/upload_eval_data.py --endpoint http://minio.kutana.svc:9000
```

## Interpreting Results

### Score Scale

| Score | Meaning |
|-------|---------|
| 5 | Excellent — fully meets criterion |
| 4 | Good — meets with minor issues |
| 3 | Acceptable — partially meets |
| 2 | Poor — mostly fails |
| 1 | Failing — does not meet |

### Pass/Fail

A scenario passes if the overall score (weighted average) meets or exceeds `passing_score` (default 3.5).

### EvalResult Fields

| Field | Description |
|-------|-------------|
| `scenario_id` | Which scenario was tested |
| `agent_template` | Which agent was evaluated |
| `scores` | Per-criterion scores with reasons |
| `overall_score` | Weighted average (1-5) |
| `passed` | Whether overall_score >= passing_score |
| `tool_calls_captured` | Tool_use blocks from the agent |
| `raw_agent_response` | Full text response from the agent |

## Adding a New Agent

1. Create 3 scenario files in `evals/data/scenarios/<agent-slug>/`
2. Create a rubric in `evals/data/rubrics/<agent-slug>.json`
3. Add the agent's system prompt to `managed-agent-system-prompts.md`
4. Add test cases to the appropriate `test_*_agents.py` file
5. Upload data: `python scripts/upload_eval_data.py`

## Transcript Format

```json
{
  "metadata": {
    "title": "Meeting Title",
    "duration_minutes": 10,
    "speakers": ["Alice", "Bob"],
    "type": "standup"
  },
  "segments": [
    {
      "speaker": "Alice",
      "text": "What Alice said",
      "timestamp_seconds": 0.0
    }
  ]
}
```
