# Voice Agent Quickstart

Build an AI agent that sends and receives raw PCM16 audio in Kutana meetings. Voice agents use a WebSocket audio sidecar alongside the main MCP connection for bidirectional audio streaming.

> **Most agents should use [TTS agents](./TTS_AGENT_QUICKSTART.md) instead.** Voice agents are for advanced use cases: custom STT pipelines, real-time voice cloning, or audio analysis.

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
1. **MCP** — meeting tools (join, chat, transcript, tasks)
2. **Audio sidecar** — raw PCM16 audio frames via WebSocket

## Prerequisites

- A Kutana API key (`cvn_...`) with **Agent** scope
- Python 3.12+ with `websockets`
- Familiarity with PCM16 audio format

## Audio Format

| Parameter | Value |
|-----------|-------|
| Encoding | PCM16 little-endian (signed 16-bit) |
| Sample rate | 16,000 Hz |
| Channels | Mono |
| Frame size | 20ms (640 bytes per frame) |

## Step 1: Join with Voice Capabilities

```python
# Via MCP tool
result = kutana_join_meeting(
    meeting_id="...",
    capabilities=["voice"]
)
# Response includes:
# - audio_ws_url: WebSocket URL for the audio sidecar
# - audio_token: Short-lived JWT (5 min) for sidecar auth
```

## Step 2: Connect to the Audio Sidecar

Two endpoints are available — both use the same protocol after handshake.

### Option A: Query-string auth (simpler)

```python
import websockets
import json

GATEWAY_URL = "wss://dev.kutana.ai"

async def connect_audio(audio_token: str, meeting_id: str):
    uri = (
        f"{GATEWAY_URL}/audio/connect"
        f"?token={audio_token}"
        f"&meeting_id={meeting_id}"
        f"&audio_format=pcm16"
    )
    async with websockets.connect(uri) as ws:
        # First message is audio_session_joined confirmation
        joined = json.loads(await ws.recv())
        print(f"Audio session: {joined['session_id']}")

        # Now send/receive PCM16 frames
        await audio_loop(ws)
```

### Option B: v1 endpoint (Bearer JWT in first message)

```python
async def connect_audio_v1(session_id: str, audio_token: str, meeting_id: str):
    uri = f"{GATEWAY_URL}/v1/audio/{session_id}?audio_format=pcm16"
    async with websockets.connect(uri) as ws:
        # Send auth message first
        await ws.send(json.dumps({
            "type": "auth",
            "token": audio_token,
            "meeting_id": meeting_id,
        }))

        # Server responds with audio_session_joined
        joined = json.loads(await ws.recv())
        print(f"Audio session: {joined['session_id']}")

        await audio_loop(ws)
```

## Step 3: Send Audio

Signal that you're speaking, then send raw PCM16 frames as base64 JSON messages:

```python
import base64
import time

# Tell the gateway you're starting to speak
await ws.send(json.dumps({"type": "start_speaking"}))

# Send PCM16 frames (640 bytes = 20ms at 16kHz mono)
pcm_frame = generate_audio_frame()  # 640 bytes
await ws.send(json.dumps({
    "type": "audio_data",
    "data": base64.b64encode(pcm_frame).decode(),
    "timestamp": int(time.time() * 1000),
}))

# When done speaking
await ws.send(json.dumps({"type": "stop_speaking"}))
```

## Step 4: Receive Audio

The gateway sends **mixed-minus** audio — room audio with the agent's own stream subtracted (prevents echo):

```python
async def audio_loop(ws):
    async for raw in ws:
        msg = json.loads(raw)

        if msg["type"] == "mixed_audio":
            # Decode PCM16 audio from other participants
            pcm_bytes = base64.b64decode(msg["data"])
            speakers = msg.get("speakers", [])
            transcribe_or_process(pcm_bytes)

        elif msg["type"] == "speaker_changed":
            print(f"{msg['participant_id']} {msg['action']} speaking")

        elif msg["type"] == "pong":
            pass  # keepalive response
```

## Sidecar Protocol Reference

### Client → Server

| Message | Fields | Description |
|---------|--------|-------------|
| `start_speaking` | — | Signal that the agent is about to send audio |
| `stop_speaking` | — | Signal that the agent has finished sending audio |
| `audio_data` | `data` (base64), `timestamp` (ms) | A PCM16 audio frame |
| `ping` | — | Keepalive |

### Server → Client

| Message | Fields | Description |
|---------|--------|-------------|
| `audio_session_joined` | `session_id`, `meeting_id`, `format` | Connection confirmed |
| `mixed_audio` | `data` (base64), `speakers` | Mixed-minus audio from other participants |
| `speaker_changed` | `participant_id`, `action` | A participant started or stopped speaking |
| `pong` | — | Keepalive response |
| `error` | `code`, `message` | Error notification |

## Capabilities

| Capability | Effect |
|------------|--------|
| `text_only` | Default. Receive transcript, send/receive chat. No audio. |
| `tts_enabled` | Speak via gateway TTS — send text, gateway synthesizes audio. |
| `voice` | Bidirectional raw PCM16 audio via the sidecar WebSocket. |

Use `voice` when your agent needs to process or generate raw audio (custom STT, voice cloning, audio analysis, real-time interpreter). If you only need one direction, simply don't send or don't read — the gateway doesn't enforce directionality.

> **Not processing raw audio?** Use [`tts_enabled`](./TTS_AGENT_QUICKSTART.md) instead — the gateway handles synthesis and you just send text.

## VAD (Voice Activity Detection)

The gateway applies a VAD filter on inbound agent audio. Silence frames are suppressed before reaching the STT pipeline.

## Sidecar Auth

The `audio_token` returned by `kutana_join_meeting` is a short-lived JWT (5 min). If the connection drops, call `kutana_join_meeting` again for a fresh token.

## Full Example

```python
import asyncio
import base64
import json
import os
import time

import websockets

GATEWAY_URL = os.environ.get("KUTANA_GATEWAY_URL", "wss://dev.kutana.ai")


async def voice_agent(audio_token: str, meeting_id: str):
    """Connect to the audio sidecar and echo received audio back."""
    uri = (
        f"{GATEWAY_URL}/audio/connect"
        f"?token={audio_token}"
        f"&meeting_id={meeting_id}"
        f"&audio_format=pcm16"
    )

    async with websockets.connect(uri) as ws:
        # Wait for session confirmation
        joined = json.loads(await ws.recv())
        assert joined["type"] == "audio_session_joined"
        print(f"Connected: session={joined['session_id']}, format={joined['format']}")

        # Process incoming audio
        async for raw in ws:
            msg = json.loads(raw)

            if msg["type"] == "mixed_audio":
                pcm_bytes = base64.b64decode(msg["data"])
                # Process the audio — run your own STT, analysis, etc.
                print(f"Received {len(pcm_bytes)} bytes from {msg.get('speakers', [])}")

                # Example: echo the audio back (replace with your logic)
                await ws.send(json.dumps({"type": "start_speaking"}))
                await ws.send(json.dumps({
                    "type": "audio_data",
                    "data": msg["data"],
                    "timestamp": int(time.time() * 1000),
                }))
                await ws.send(json.dumps({"type": "stop_speaking"}))

            elif msg["type"] == "speaker_changed":
                print(f"{msg['participant_id']} {msg['action']} speaking")


# Usage:
# 1. Join a meeting via MCP with capabilities=["voice"]
# 2. Extract audio_token and meeting_id from the join response
# 3. Run: asyncio.run(voice_agent(audio_token, meeting_id))
```

## See Also

- [TTS Agent Quickstart](./TTS_AGENT_QUICKSTART.md) — Simpler text-to-speech agents
- [MCP Quickstart](/docs/connecting-agents/custom-agents/mcp-quickstart) — General MCP setup
- [Claude Code Channel](./CLAUDE_CODE_CHANNEL.md) — Claude Code integration
