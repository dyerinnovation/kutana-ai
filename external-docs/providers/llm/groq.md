# Groq LLM (Free Cloud)

Fastest LLM inference available. Free tier with no credit card required.

## Status

Planned -- not yet in the default registry. Will be registered as `groq` under `ProviderType.LLM`.

## Sign Up

1. Go to [https://console.groq.com/](https://console.groq.com/)
2. Create a free account (no credit card needed)
3. Get your API key from the dashboard

## Environment Variables

```bash
GROQ_API_KEY=gsk_...
```

## Recommended Models

| Model | Speed | Quality | Best For |
|-------|-------|---------|----------|
| `llama-3.1-8b-instant` | Fastest | Good | Development, quick iteration |
| `llama-3.3-70b-versatile` | Fast | Best | Quality-sensitive dev work |

## Free Tier Limits

Rate-limited but generous for development:
- Requests per minute and tokens per minute limits vary by model
- More than enough for development and testing workflows
- No credit card required

## Why Groq for Development

- **Blazing fast inference** -- built on custom LPU (Language Processing Unit) hardware
- **Free** -- no cost for development usage
- **No credit card** -- sign up and start immediately
- **Great models** -- access to Llama 3.1 and 3.3 variants
- **OpenAI-compatible API** -- familiar SDK patterns

## Usage

```python
from convene_providers.registry import default_registry, ProviderType

# Create with default model
llm = default_registry.create(
    ProviderType.LLM, "groq", api_key="gsk_..."
)

# Create with specific model
llm = default_registry.create(
    ProviderType.LLM, "groq",
    api_key="gsk_...",
    model="llama-3.3-70b-versatile",
)

# Extract tasks from transcript segments
tasks = await llm.extract_tasks(segments, context="Sprint planning")

# Summarize transcript
summary = await llm.summarize(segments)
```

## API Compatibility

Groq uses an OpenAI-compatible API. If you are familiar with the OpenAI Python SDK, the patterns are the same with a different base URL and API key.

## When to Use

- Development when you want cloud-quality results for free
- Quick prototyping without setting up Ollama
- When speed matters more than extraction precision
- Bridge between local dev (Ollama) and production (Anthropic)
