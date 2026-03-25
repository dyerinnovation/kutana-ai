# Piper TTS (Local)

Neural text-to-speech running fully offline. Real-time synthesis on CPU.

## Status

Planned -- not yet in the default registry. Will be registered as `piper` under `ProviderType.TTS`.

## Install

Already included with `uv sync --all-packages`. Voice models download on first use.

## Available Voices

| Voice | Quality | Description |
|-------|---------|-------------|
| `en_US-lessac-medium` | **Recommended** | Clear American English, balanced quality/speed |
| `en_US-amy-medium` | Good | Female American English |
| `en_GB-alan-medium` | Good | British English male |
| + 20 more | Varies | Various languages and accents |

## Environment Variables

None required. Fully local.

## Usage

```python
from convene_providers.registry import default_registry, ProviderType

# Create with default voice
tts = default_registry.create(ProviderType.TTS, "piper")

# Create with specific voice
tts = default_registry.create(
    ProviderType.TTS, "piper", voice="en_US-lessac-medium"
)

# Synthesize text to audio
async for audio_chunk in tts.synthesize("Hello from the meeting assistant."):
    # audio_chunk is raw PCM bytes
    audio_buffer.write(audio_chunk)

# List available voices
voices = await tts.get_voices()
for voice in voices:
    print(f"{voice.name} ({voice.language})")
```

## Quality

Good neural TTS quality. Noticeably less natural than cloud providers (Cartesia, ElevenLabs), but perfectly usable for development and testing. Real-time performance on modern CPUs.

## When to Use

- Local development and testing without API keys
- Offline environments
- Prototyping voice interactions before using cloud TTS
- Cost-sensitive deployments where naturalness is less critical
