# ElevenLabs TTS (Cloud)

Premium cloud text-to-speech with voice cloning and high-quality synthesis.

## Sign Up

1. Go to [https://elevenlabs.io/](https://elevenlabs.io/)
2. Create an account
3. Get your API key from your profile settings

## Free Tier

10,000 characters per month on the free plan.

## Environment Variables

```bash
ELEVENLABS_API_KEY=your-api-key-here
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `voice_id` | `"default"` | Voice identifier (get IDs from `get_voices()`) |
| `model_id` | `"eleven_monolingual_v1"` | ElevenLabs model for synthesis |

## Features

- **Voice cloning** -- create custom voices from audio samples
- **High-quality synthesis** -- among the most natural-sounding TTS
- **Large voice library** -- many pre-built voices available
- **Voice settings** -- adjustable stability (0.5) and similarity boost (0.75)
- Output format: MP3 streaming

## Usage

```python
from convene_providers.registry import default_registry, ProviderType

# Create provider
tts = default_registry.create(
    ProviderType.TTS, "elevenlabs",
    api_key="your-api-key",
    voice_id="21m00Tcm4TlvDq8ikWAM",  # "Rachel" voice
)

# Synthesize text to streaming audio
async for audio_chunk in tts.synthesize("Here are the action items from today."):
    # audio_chunk is MP3 bytes
    await play_audio(audio_chunk)

# List available voices
voices = await tts.get_voices()
for voice in voices:
    print(f"{voice.id}: {voice.name} ({voice.language})")

# Clean up
await tts.close()
```

## Implementation Details

- Class: `ElevenLabsTTS` in `packages/convene-providers/src/convene_providers/tts/elevenlabs_tts.py`
- API base: `https://api.elevenlabs.io/v1`
- Uses `httpx.AsyncClient` with streaming response
- Registered in `default_registry` as `ProviderType.TTS, "elevenlabs"`

## ElevenLabs vs Cartesia

| Feature | ElevenLabs | Cartesia |
|---------|-----------|----------|
| Quality | Highest | Very good |
| Latency | Moderate | Lowest |
| Voice cloning | Yes | No |
| Free tier | 10k chars/mo | None |
| Output format | MP3 | Raw PCM |

## When to Use

- When voice quality is the top priority
- When you need custom cloned voices
- Free tier is enough for light development
