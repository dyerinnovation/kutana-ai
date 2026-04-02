# Voice Agent Integration Architecture

> Research and design reference for bidirectional voice agents in Kutana AI.
> Covers the WebSocket audio sidecar pattern, PCM16 format, VAD, mixed-minus audio,
> the `kutana_start_speaking` tool, and capability declaration on join.

---

## Overview

A voice agent participates in a Kutana meeting with bidirectional audio: it listens to the room
and can speak into the meeting. The architecture uses a **WebSocket audio sidecar** — a persistent
binary WebSocket connection alongside the MCP control channel — to stream raw PCM16 audio in both
directions.

Text-only agents connect via MCP alone. Voice agents add the sidecar to receive and send audio.
The two channels are intentionally decoupled: the MCP server handles control flow (join, turn
management, chat), and the sidecar handles media.

---

## Capability Declaration on Join

Agents declare their audio capabilities in the `join_meeting` MCP tool call. The gateway uses
this to configure audio routing for the session.

### Capability Values

| Value | Audio In | Audio Out | Use Case |
|-------|----------|-----------|----------|
| `text_only` | Transcript feed only | None | Chat bots, task extractors |
| `voice_in` | Raw PCM16 stream | None | Transcription agents, listeners |
| `voice_out` | Transcript feed only | PCM16 stream | Announcement agents, narrators |
| `voice_bidirectional` | Raw PCM16 stream | PCM16 stream | Full voice agents |
| `tts_enabled` | Transcript feed only | TTS-generated PCM16 | Text agents with TTS voice output |

`tts_enabled` is mutually exclusive with `voice_out` and `voice_bidirectional`. It signals that
the gateway should accept text output from the agent and synthesize it via TTS before mixing into
the room.

### Join Message

The gateway receives a capability declaration as part of the `join_meeting` tool result context,
forwarded via the `AgentIdentity` WebSocket message:

```json
{
  "type": "join_meeting",
  "meeting_id": "abc123",
  "capabilities": {
    "audio": "voice_bidirectional",
    "sidecar_port": 8004
  }
}
```

For MCP-based agents, the capability is passed as a parameter to `kutana_join_meeting`:

```python
# Via MCP tool call
result = await mcp.call_tool("kutana_join_meeting", {
    "meeting_id": "abc123",
    "audio_capability": "voice_bidirectional"
})
# Returns: {"session_id": "...", "sidecar_ws_url": "ws://..."}
```

---

## WebSocket Audio Sidecar

### Why a Separate Channel?

Mixing binary audio frames with JSON control messages on a single WebSocket connection creates
head-of-line blocking: a large audio frame delays a time-sensitive control message (e.g.,
`speaker.changed`). The sidecar keeps media on its own connection, isolated from control flow.

### Connection Flow

```
Agent                     MCP Server              Agent Gateway
  │                           │                         │
  │── kutana_join_meeting ──►│                         │
  │◄── {sidecar_ws_url} ──────│── JoinMeeting ─────────►│
  │                           │                         │
  │────── WebSocket connect ──────────────────────────►│
  │       (sidecar_ws_url, bearer=session_jwt)          │
  │                           │                         │
  │◄────── binary PCM16 frames (mixed room audio) ─────│
  │────── binary PCM16 frames (agent speech) ──────────►│
```

### Sidecar Protocol

- **Transport:** WebSocket (binary frames)
- **Authentication:** Bearer JWT in the `Authorization` header (same session JWT from `join_meeting`)
- **Frame format:** Raw PCM16, little-endian, 16kHz, mono (no framing headers)
- **Frame size:** 20ms chunks = 640 bytes (320 samples × 2 bytes)
- **Direction:** Full duplex — gateway streams room audio in; agent sends speech out

### Frame Timing

The gateway streams 20ms frames continuously while the meeting is active. Silence frames
(zero-filled) are sent between speakers to maintain the real-time clock. Agents must consume
frames at real-time rate; the buffer is bounded at 5 seconds of audio (250 frames).

---

## Audio Format: PCM16 16kHz Mono

All audio in Kutana uses a single canonical format: **PCM16, signed 16-bit little-endian, 16kHz,
mono**. This matches Deepgram Nova-2's native input and avoids transcoding in the hot path.

### Format Specification

| Parameter | Value |
|-----------|-------|
| Encoding | PCM signed 16-bit LE |
| Sample rate | 16,000 Hz |
| Channels | 1 (mono) |
| Frame size | 320 samples (20ms) |
| Bit rate | 256 kbit/s |

### Conversion Helpers

```python
import numpy as np
import soundfile as sf

def wav_to_pcm16(wav_path: str) -> bytes:
    """Convert WAV file to PCM16 16kHz mono bytes."""
    audio, sr = sf.read(wav_path, dtype="int16")
    if sr != 16000:
        # resample — use librosa or resampy
        audio = resample(audio, sr, 16000)
    if audio.ndim > 1:
        audio = audio.mean(axis=1).astype(np.int16)
    return audio.tobytes()


def float32_to_pcm16(audio: np.ndarray) -> bytes:
    """Convert float32 [-1.0, 1.0] array to PCM16 bytes."""
    clamped = np.clip(audio, -1.0, 1.0)
    return (clamped * 32767).astype(np.int16).tobytes()
```

---

## Voice Activity Detection (VAD)

VAD prevents the agent from streaming silence to the gateway — the gateway only routes audio
tagged as speech to the STT pipeline.

### Recommended: Silero VAD

```python
import torch
from silero_vad import load_silero_vad, VADIterator

model, utils = load_silero_vad()
vad = VADIterator(model, sampling_rate=16000, threshold=0.5, min_silence_duration_ms=300)

async def send_audio_with_vad(ws, pcm16_stream):
    async for frame in pcm16_stream:
        speech_dict = vad(frame, return_seconds=False)
        if speech_dict:
            await ws.send(frame)
        # Silence frames are not sent — saves bandwidth and avoids spurious transcription
```

### VAD Parameters

| Parameter | Default | Effect |
|-----------|---------|--------|
| `threshold` | 0.5 | Probability above which a frame is classified as speech |
| `min_silence_duration_ms` | 300 | Silence after speech before marking end-of-utterance |
| `speech_pad_ms` | 30 | Padding added around detected speech regions |

---

## Mixed-Minus Audio

Voice agents receive **mixed-minus** audio: the full meeting mix *minus* their own voice. This
prevents acoustic echo (the agent hearing itself) and eliminates the need for echo cancellation
in the agent's microphone path.

The gateway implements mixed-minus at the audio routing layer: when a frame arrives from agent A,
it is mixed with all other sources and sent to everyone except A.

```
Meeting room audio sources:
  Human 1 (mic) ──────────────────────► Mix ──────────────► Agent A (gets Human 1 + Human 2)
  Human 2 (mic) ──────────────────────► Mix ──────────────► Human 1 (gets Human 2 + Agent A)
  Agent A (sidecar) ──────────────────► Mix ──────────────► Human 2 (gets Human 1 + Agent A)
```

For text agents with `tts_enabled`, TTS audio is synthesized by the gateway on behalf of the
agent and mixed the same way (agents do not receive their own TTS output).

---

## start_speaking Tool

`kutana_start_speaking` is the MCP tool agents call when they want to address the meeting. It
coordinates with turn management so the agent speaks at the right moment.

### Tool Signature

```python
{
    "name": "kutana_start_speaking",
    "description": "Signal intent to speak in the meeting. For voice agents, opens the audio stream. For TTS-enabled agents, sends text that will be synthesized and played to the room.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "meeting_id": {"type": "string"},
            "text": {
                "type": "string",
                "description": "Text to speak (required for tts_enabled agents, ignored for voice agents)"
            },
            "priority": {
                "type": "string",
                "enum": ["normal", "urgent"],
                "default": "normal"
            },
            "wait_for_turn": {
                "type": "boolean",
                "default": true,
                "description": "If true, wait until granted the floor before speaking. If false, speak immediately (interruption)."
            }
        },
        "required": ["meeting_id"]
    }
}
```

### Voice Agent Flow

```
Agent                       Gateway
  │                             │
  │── kutana_start_speaking ──►│ (enqueues in TurnManager)
  │                             │
  │◄── {status: "queued",       │
  │     position: 2}            │
  │                             │
  │   [waits for turn]          │
  │                             │
  │◄── speaker.changed event ───│ (agent is now active speaker)
  │                             │
  │   [streams PCM16 via        │
  │    sidecar until done]      │
  │                             │
  │── kutana_mark_finished_speaking ──►│
```

### TTS Agent Flow

```
Agent                       Gateway               TTS Provider
  │                             │                      │
  │── kutana_start_speaking ──►│                      │
  │   {text: "Here are the      │                      │
  │    action items..."}        │── synthesize(text) ──►│
  │                             │◄── PCM16 stream ──────│
  │◄── {status: "speaking"}     │── mix into room ─────►[participants]
  │                             │
  │◄── {status: "done"}         │ (gateway auto-calls mark_finished_speaking)
```

---

## Gateway Audio Routing Architecture

```
                          ┌──────────────────────────────────────┐
                          │           Agent Gateway               │
                          │                                       │
  Agent (voice) ──PCM16──►│  Audio Router                        │
                          │    ├── STT Pipeline (→ transcript)   │
                          │    ├── Mixed-minus to other agents   │
                          │    └── Broadcast to LiveKit room     │
  Agent (tts) ──text─────►│  TTS Engine ──PCM16──► Audio Router  │
                          │                                       │
  Human (WebRTC) ─────────►│  LiveKit bridge ──PCM16──► Router   │
                          └──────────────────────────────────────┘
```

---

## Implementation Checklist

- [ ] Add `audio_capability` parameter to `kutana_join_meeting` MCP tool
- [ ] Add sidecar WebSocket endpoint to agent-gateway (`/v1/audio/{session_id}`)
- [ ] Implement mixed-minus mixing in `AudioRouter`
- [ ] Implement `VADFilter` wrapper for agent audio streams
- [ ] Implement `kutana_start_speaking` MCP tool (turn queue integration)
- [ ] Implement TTS synthesis path in gateway (text → PCM16 → mix)
- [ ] Write integration tests: voice agent joins, speaks, and leaves
- [ ] Write integration tests: TTS agent produces audible speech in room

---

## Related Files

- `services/agent-gateway/` — Audio routing implementation
- `packages/kutana-providers/src/kutana_providers/tts/` — TTS provider implementations
- `services/mcp-server/` — MCP tool definitions including `kutana_start_speaking`
- `docs/research/tts-text-agents.md` — TTS pipeline for text-only agents
- `docs/technical/ROADMAP.md` — Phase 9 (Voice Output & Dialogue)
