# Whisper STT (Local)

Open-source speech-to-text using faster-whisper. Runs fully offline on your machine.

## Status

Planned -- not yet in the default registry. Will be registered as `whisper` under `ProviderType.STT`.

## Install

Already included with `uv sync --all-packages`. Models download automatically on first use.

## Model Sizes

| Model | Size | Speed | Accuracy | Recommended? |
|-------|------|-------|----------|-------------|
| `tiny` | 75 MB | Fastest | Lower | Quick testing |
| `small` | 461 MB | Balanced | Good | **Yes** |
| `medium` | 1.5 GB | Slower | Best | When accuracy matters |

## Environment Variables

None required. Fully local.

## Usage

```python
from convene_providers.registry import default_registry, ProviderType

# Create with default model size (small)
stt = default_registry.create(ProviderType.STT, "whisper")

# Create with specific model size
stt = default_registry.create(ProviderType.STT, "whisper", model_size="medium")

# Transcribe audio
async for segment in stt.get_transcript():
    print(f"[{segment.start_time:.1f}s] {segment.text}")
```

## Limitations

- **Batch processing only** -- not real-time streaming. Audio must be recorded first.
- **No speaker diarization** -- all text attributed to a single speaker.
- Requires audio file input, not live microphone.

## macOS Apple Silicon

Runs on CPU. Expect ~5-10 seconds per minute of audio with the `small` model. No GPU acceleration on macOS (CUDA not available), but performance is acceptable for development.

## When to Use

- Local development and testing without API keys
- Offline environments
- Quick prototyping before wiring up cloud STT
