# Voice Agent Quickstart

Build an AI agent that sends and receives raw audio in meetings. Voice agents use a WebSocket sidecar for bidirectional PCM16 audio streaming alongside the main MCP connection.

> **Most agents should use [TTS agents](/docs/connecting-agents/custom-agents/tts-agent-quickstart) instead.** Voice agents are for advanced use cases that require raw audio processing — real-time voice cloning, custom STT pipelines, or audio analysis.

## Architecture

```
Agent ──MCP──► Kutana MCP Server (tools, transcript, chat)
  │
  └──WebSocket──► Agent Gateway /audio/connect (PCM16 bidirectional)
                    ↓
              AudioRouter (mixed-minus distribution)
                    ↓
              Room participants hear the agent
```

The agent maintains two connections:
1. **MCP** — for meeting tools (join, speak, chat, transcript)
2. **Audio sidecar** — for raw PCM16 audio frames

## Prerequisites

- A Kutana API key (`cvn_...`) with **Agent** scope
- Python 3.12+ with `websockets` library
- Familiarity with PCM16 audio format

## Audio format

| Parameter | Value |
|-----------|-------|
| Encoding | PCM16 little-endian (signed 16-bit) |
| Sample rate | 16,000 Hz |
| Channels | Mono |
| Frame size | 20ms (640 bytes per frame) |

## Connection flow

### 1. Join with voice capabilities

```python
# Via MCP tool
result = kutana_join_meeting(
    meeting_id="...",
    capabilities=["voice_bidirectional"]
)
# Response includes:
# - audio_ws_url: WebSocket URL for the audio sidecar
# - audio_token: Short-lived JWT (5 min) for sidecar auth
```

### 2. Connect to the audio sidecar

```python
import websockets
import json

async def connect_audio(audio_ws_url: str, audio_token: str, meeting_id: str):
    uri = f"{audio_ws_url}?token={audio_token}&meeting_id={meeting_id}"
    async with websockets.connect(uri) as ws:
        # Send and receive PCM16 frames
        async for frame in ws:
            # frame is raw PCM16 bytes (640 bytes = 20ms at 16kHz)
            process_audio(frame)
```

### 3. Send audio

Send raw PCM16 frames as binary WebSocket messages. Each frame should be exactly 640 bytes (20ms at 16kHz mono).

```python
# Generate or capture PCM16 audio
pcm_frame = generate_audio_frame()  # 640 bytes
await ws.send(pcm_frame)
```

### 4. Receive audio

The gateway sends mixed-minus audio — room audio with the agent's own stream subtracted. This prevents echo.

```python
async for frame in ws:
    # frame is PCM16 bytes from other participants
    transcribe_or_process(frame)
```

## Capabilities

| Capability | Direction | Use case |
|------------|-----------|----------|
| `voice_in` | Agent → Room | Agent sends audio only (e.g., playback) |
| `voice_out` | Room → Agent | Agent receives audio only (e.g., analysis) |
| `voice_bidirectional` | Both | Full duplex audio (e.g., voice assistant) |

## Mixed-minus

When multiple participants are speaking, the agent receives a mix of all audio **except its own**. This is handled automatically by the AudioRouter in the gateway.

## VAD (Voice Activity Detection)

The gateway includes a VAD filter on inbound agent audio. Silence frames are suppressed before reaching the STT pipeline, reducing unnecessary processing.

## Sidecar auth

The audio token returned by `kutana_join_meeting` is a short-lived JWT (5 minutes). If the sidecar connection drops, call `kutana_join_meeting` again to get a fresh token.

## See also

- [TTS Agent Quickstart](/docs/connecting-agents/custom-agents/tts-agent-quickstart) — simpler text-to-speech agents
- [MCP Quickstart](/docs/connecting-agents/custom-agents/mcp-quickstart) — general MCP connection setup
- [MCP Authentication](/docs/connecting-agents/custom-agents/mcp-auth) — OAuth 2.1 Bearer token flow
