# Ollama LLM (Local)

Run LLMs locally with zero configuration. Full offline support.

## Status

Planned -- not yet in the default registry. Will be registered as `ollama` under `ProviderType.LLM`.

## Install

```bash
# macOS
brew install ollama

# Or download from https://ollama.com/
```

## Pull a Model

```bash
# Recommended for task extraction (4.1 GB)
ollama pull mistral

# General purpose (4.7 GB)
ollama pull llama3.1

# Smallest option (2.3 GB)
ollama pull phi3
```

## Start Ollama

```bash
ollama serve
# Runs on http://localhost:11434
```

## Environment Variables

```bash
OLLAMA_HOST=http://localhost:11434    # default
OLLAMA_MODEL=mistral                  # default
```

## Recommended Models

| Model | Size | Best For | Notes |
|-------|------|----------|-------|
| `mistral` | 4.1 GB | **Task extraction** | Best instruction-following at this size |
| `llama3.1` | 4.7 GB | General purpose | Strong all-around performance |
| `phi3` | 2.3 GB | Resource-constrained | Smallest, still capable |

## Usage

```python
from convene_providers.registry import default_registry, ProviderType

# Create with defaults (mistral on localhost:11434)
llm = default_registry.create(ProviderType.LLM, "ollama")

# Create with specific model and host
llm = default_registry.create(
    ProviderType.LLM, "ollama",
    model="llama3.1",
    host="http://localhost:11434",
)

# Extract tasks from transcript segments
tasks = await llm.extract_tasks(segments, context="Weekly standup")

# Summarize transcript
summary = await llm.summarize(segments)
```

## Apple Silicon

Automatic Metal GPU acceleration on M1/M2/M3/M4 Macs. Performance is significantly better than CPU-only inference.

## Limitations

- Slower than cloud providers (especially on first token)
- Extraction quality depends on model size -- smaller models miss nuance
- No tool_use support like Anthropic -- relies on prompt-based extraction
- Models require disk space (2-5 GB each)

## When to Use

- Local development without API keys
- Offline environments or air-gapped systems
- Quick iteration without worrying about API costs
- Testing pipeline logic before switching to production LLM
