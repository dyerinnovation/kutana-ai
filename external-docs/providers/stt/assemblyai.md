# AssemblyAI STT (Cloud)

Real-time streaming speech-to-text with speaker diarization via WebSocket.

## Sign Up

1. Go to [https://www.assemblyai.com/](https://www.assemblyai.com/)
2. Create an account
3. Copy your API key from the dashboard

## Environment Variables

```bash
ASSEMBLYAI_API_KEY=your-api-key-here
```

## Features

- **Real-time WebSocket streaming** -- transcription as audio arrives
- **Speaker diarization** -- identifies who said what
- **Word-level timestamps** -- precise timing for each word
- **Finalized transcripts** -- only emits confirmed results (no partial/interim)
- Audio format: PCM16 at 16kHz mono, base64-encoded over WebSocket

## Usage

```python
from convene_providers.registry import default_registry, ProviderType

# Create provider
stt = default_registry.create(
    ProviderType.STT, "assemblyai", api_key="your-api-key"
)

# Start streaming session
await stt.start_stream()

# Send audio chunks (PCM16, 16kHz, mono)
await stt.send_audio(audio_chunk)

# Receive transcript segments
async for segment in stt.get_transcript():
    print(f"[{segment.speaker_id}] {segment.text}")
    print(f"  Confidence: {segment.confidence:.2f}")
    print(f"  Time: {segment.start_time:.1f}s - {segment.end_time:.1f}s")

# Clean up
await stt.close()
```

## Pricing

Pay-per-use, approximately $0.15 per hour of audio. No minimum commitment.

## Implementation Details

- Class: `AssemblyAISTT` in `packages/convene-providers/src/convene_providers/stt/assemblyai_stt.py`
- WebSocket URL: `wss://api.assemblyai.com/v2/realtime/ws`
- Registered in `default_registry` as `ProviderType.STT, "assemblyai"`

## When to Use

- Production real-time transcription
- When you need speaker diarization
- High-accuracy transcription requirements
