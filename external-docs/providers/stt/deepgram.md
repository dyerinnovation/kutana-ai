# Deepgram STT (Cloud)

Real-time streaming speech-to-text using the Nova-2 model via WebSocket.

## Sign Up

1. Go to [https://console.deepgram.com/](https://console.deepgram.com/)
2. Create an account
3. Get your API key from the dashboard

## Free Tier

$200 credit on signup -- enough for significant development and testing.

## Environment Variables

```bash
DEEPGRAM_API_KEY=your-api-key-here
```

## Features

- **Real-time WebSocket streaming** -- low-latency transcription
- **Nova-2 model** -- latest and most accurate Deepgram model
- **Speaker diarization** -- speaker labels as `speaker_0`, `speaker_1`, etc.
- **Punctuation** -- automatic punctuation in transcripts
- Audio format: raw PCM16 at 16kHz mono (no base64 encoding needed)

## Usage

```python
from convene_providers.registry import default_registry, ProviderType

# Create provider
stt = default_registry.create(
    ProviderType.STT, "deepgram", api_key="your-api-key"
)

# Start streaming session
await stt.start_stream()

# Send audio chunks (raw PCM16, 16kHz, mono -- no base64 needed)
await stt.send_audio(audio_chunk)

# Receive transcript segments
async for segment in stt.get_transcript():
    print(f"[{segment.speaker_id}] {segment.text}")
    print(f"  Confidence: {segment.confidence:.2f}")
    print(f"  Time: {segment.start_time:.1f}s - {segment.end_time:.1f}s")

# Clean up
await stt.close()
```

## Implementation Details

- Class: `DeepgramSTT` in `packages/convene-providers/src/convene_providers/stt/deepgram_stt.py`
- WebSocket URL: `wss://api.deepgram.com/v1/listen`
- Stream params: `model=nova-2`, `punctuate=true`, `diarize=true`, `encoding=linear16`, `sample_rate=16000`
- Registered in `default_registry` as `ProviderType.STT, "deepgram"`

## Deepgram vs AssemblyAI

| Feature | Deepgram | AssemblyAI |
|---------|----------|------------|
| Latency | Lower | Moderate |
| Audio encoding | Raw bytes | Base64 JSON |
| Free tier | $200 credit | None |
| Speaker labels | `speaker_0` format | Word-level speaker |

## When to Use

- Production real-time transcription with lowest latency
- When you have the $200 free credit to burn through
- Simpler audio pipeline (no base64 encoding needed)
