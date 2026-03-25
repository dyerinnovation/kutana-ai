# Anthropic LLM (Cloud)

Claude models for highest quality task extraction and summarization.

## Sign Up

1. Go to [https://console.anthropic.com/](https://console.anthropic.com/)
2. Create an account and add billing
3. Get your API key from the API Keys section

## Environment Variables

```bash
ANTHROPIC_API_KEY=sk-ant-...
```

## Recommended Models

| Model | Speed | Cost | Best For |
|-------|-------|------|----------|
| `claude-sonnet-4-20250514` | Balanced | Moderate | **Production** (default) |
| `claude-haiku-4-5` | Fastest | Cheapest | High-volume, cost-sensitive |

## Features

- **tool_use for structured extraction** -- Claude returns tasks as structured JSON via tool calls, not free-form text. This is the most reliable extraction method.
- **Best extraction quality** -- Claude excels at understanding meeting context, identifying commitments, and attributing tasks to speakers.
- **Summarization** -- generates concise, well-structured meeting summaries.
- **Report generation** -- creates professional task reports grouped by status.

## Usage

```python
from convene_providers.registry import default_registry, ProviderType

# Create with default model (claude-sonnet-4-20250514)
llm = default_registry.create(
    ProviderType.LLM, "anthropic", api_key="sk-ant-..."
)

# Create with specific model
llm = default_registry.create(
    ProviderType.LLM, "anthropic",
    api_key="sk-ant-...",
    model="claude-haiku-4-5",
)

# Extract tasks from transcript segments
tasks = await llm.extract_tasks(
    segments,
    context="Participant names: Alice, Bob. This is a weekly standup."
)
for task in tasks:
    print(f"[{task.priority.value}] {task.description}")
    print(f"  Due: {task.due_date}, Source: {task.source_utterance}")

# Summarize transcript
summary = await llm.summarize(segments)

# Generate formatted report
report = await llm.generate_report(tasks)

# Clean up
await llm.close()
```

## Implementation Details

- Class: `AnthropicLLM` in `packages/convene-providers/src/convene_providers/llm/anthropic_llm.py`
- Uses `anthropic.AsyncAnthropic` client
- Task extraction: temperature 0.0, max 4096 tokens, forced `tool_use`
- Summarization: temperature 0.3, max 2048 tokens
- Reports: temperature 0.2, max 4096 tokens
- Registered in `default_registry` as `ProviderType.LLM, "anthropic"`

## Task Extraction Tool Schema

The `extract_tasks` tool returns structured data with these fields per task:
- `description` (required) -- clear, actionable task description
- `priority` (required) -- one of: low, medium, high, critical
- `source_utterance` (required) -- the original transcript text
- `assignee_name` (optional) -- person assigned
- `due_date` (optional) -- ISO 8601 date string

## When to Use

- Production deployments where extraction quality matters most
- When you need structured tool_use responses (not prompt-hacked JSON)
- Meeting summarization and report generation
