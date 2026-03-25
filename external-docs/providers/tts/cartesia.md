# Cartesia TTS (Cloud)

Ultra-low latency cloud text-to-speech with streaming HTTP API.

## Sign Up

1. Go to [https://cartesia.ai/](https://cartesia.ai/)
2. Create an account
3. Get your API key from the dashboard

## Environment Variables

```bash
CARTESIA_API_KEY=your-api-key-here
```

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `voice_id` | `"default"` | Voice identifier (get IDs from `get_voices()`) |
| `model_id` | `"sonic-english"` | Cartesia model for synthesis |

## Features

- **HTTP streaming** -- audio chunks arrive as they are generated
- **Low latency** -- optimized for real-time voice applications
- **Multiple voices** -- browse via `get_voices()` API
- Output format: raw PCM s16le at 24kHz

## Usage

```python
from convene_providers.registry import default_registry, ProviderType

# Create provider
tts = default_registry.create(
    ProviderType.TTS, "cartesia",
    api_key="your-api-key",
    voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",
)

# Synthesize text to streaming audio
async for audio_chunk in tts.synthesize("The meeting summary is ready."):
    # audio_chunk is raw PCM s16le at 24kHz
    await play_audio(audio_chunk)

# List available voices
voices = await tts.get_voices()
for voice in voices:
    print(f"{voice.id}: {voice.name} ({voice.language})")

# Clean up
await tts.close()
```

## Implementation Details

- Class: `CartesiaTTS` in `packages/convene-providers/src/convene_providers/tts/cartesia_tts.py`
- API base: `https://api.cartesia.ai`
- Uses `httpx.AsyncClient` with streaming response
- Registered in `default_registry` as `ProviderType.TTS, "cartesia"`

## When to Use

- Production deployments needing low-latency voice
- Real-time meeting assistant responses
- Best balance of quality and speed for cloud TTS
