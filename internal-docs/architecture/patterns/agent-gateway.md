# Agent Gateway Architecture

## Overview

The Agent Gateway (`services/agent-gateway/`) is the WebSocket entry point for AI agents connecting to Kutana meetings. It provides authentication, bidirectional audio/data streaming, and event relay.

## Service Structure

```
services/agent-gateway/
  src/agent_gateway/
    main.py              # FastAPI app, /health, /agent/connect WebSocket
    settings.py          # AgentGatewaySettings (env prefix: AGENT_GATEWAY_)
    protocol.py          # Pydantic message schemas (client/server)
    auth.py              # JWT validation + token creation
    connection_manager.py # Registry of active agent sessions
    agent_session.py     # Per-agent lifecycle (message routing)
    event_relay.py       # Redis Streams -> agent WebSocket forwarding
```

## WebSocket Protocol

### Connection: `ws://gateway:8003/agent/connect?token=<jwt>`

### JWT Claims
- `sub`: agent_config_id (UUID)
- `name`: display name
- `capabilities`: list of capability strings
- `exp`: expiry timestamp

### Client -> Server Messages
| Type | Fields | Description |
|------|--------|-------------|
| `join_meeting` | meeting_id, capabilities | Join a meeting room |
| `audio_data` | data (base64 PCM16), sequence | Send audio |
| `data` | channel, payload | Send structured data |
| `leave_meeting` | reason | Leave the meeting |

### Server -> Client Messages
| Type | Fields | Description |
|------|--------|-------------|
| `joined` | meeting_id, room_name, participants, granted_capabilities | Join confirmation |
| `transcript` | meeting_id, speaker_id, text, start/end_time, confidence | Transcript segment |
| `audio` | data (base64), speaker_id | Meeting audio |
| `event` | event_type, payload | Domain event from Redis Streams |
| `participant_update` | action, participant_id, name, role | Join/leave notification |
| `error` | code, message, details | Error |

### Capabilities
- `listen` — receive transcript events
- `speak` — send audio to meeting
- `transcribe` — receive raw transcript segments
- `extract_tasks` — receive task extraction events
- `data_only` — data channel only, no audio

## AudioBridge (M3)

The `AudioBridge` (`audio_bridge.py`) manages per-meeting `AudioPipeline` instances. When an agent joins a meeting with `speak` capability, an STT pipeline is created.

### Flow
```
Agent audio_data → base64 decode → AudioBridge.process_audio()
→ AudioPipeline → STT Provider → TranscriptSegment
→ EventPublisher → Redis Streams → EventRelay → session.send_transcript()
```

### Key Design
- One `AudioPipeline` per meeting (shared across agents in the same meeting)
- Background `_consume_segments` task drives the async iterator from `pipeline.get_segments()`
- Segments are published to Redis via `EventPublisher` inside the pipeline
- `EventRelay` detects `transcript.segment.final` and calls `send_transcript()` (not generic `send_event()`)
- agent-gateway depends on `audio-service` and `kutana-providers` as workspace deps (embeds AudioPipeline, no inter-service calls)

### STT Settings
The gateway reads `AGENT_GATEWAY_STT_PROVIDER`, `AGENT_GATEWAY_STT_API_KEY`, `AGENT_GATEWAY_WHISPER_MODEL_SIZE`, `AGENT_GATEWAY_WHISPER_API_URL` for STT configuration.

## Event Relay

The `EventRelay` consumes from Redis Streams (`kutana:events`) using consumer group `agent-gateway`. Events are routed to agents by:
1. Match `meeting_id` to joined sessions
2. Filter by capabilities (e.g., transcript events require `listen` or `transcribe`)
3. `transcript.segment.final` events are unpacked into structured `TranscriptMessage` fields (speaker_id, text, timestamps, confidence)

## Domain Models (Phase P-A)

### New Models
- `Room` (models/room.py) — meeting room with status lifecycle
- `AgentSession` (models/agent_session.py) — agent connection tracking
- `ConnectionType` enum — webrtc, agent_gateway, phone

### New Events (6 total)
- `room.created`, `agent.joined`, `agent.left`
- `participant.joined`, `participant.left`, `agent.data`

### Modified Models
- `Meeting` — dial_in_number/meeting_code now optional; added room_id, room_name, meeting_type
- `Participant` — added connection_type, agent_config_id, OBSERVER role
- `AgentConfig` — added agent_type, protocol_version, default_capabilities, max_concurrent_sessions

## LiveKit Audio Integration

### Overview

Phase 2 adds LiveKit as the audio/video transport layer for the agent-gateway. Every meeting gets a LiveKit room. Human audio flows in via LiveKit WebRTC (browser/mobile); agent TTS flows back out through LiveKit. The agent-gateway joins each room as a bot participant via `LiveKitAgentWorker`.

### Data Flow

```
Human (browser/mobile)
   ↕ LiveKit WebRTC
LiveKit SFU
   ↕ livekit rtc SDK
agent-gateway bot (LiveKitAgentWorker)
   ├─ LiveKitAudioAdapter → AudioBridge → STT → Redis → EventRelay → agents
   └─ TTSBridge.synthesize_text() → LiveKitAudioPublisher → LiveKit → humans
```

### Key Classes

| Class | Location | Responsibility |
|-------|----------|----------------|
| `LiveKitAgentWorker` | `agent_gateway/livekit_worker.py` | Owns `rtc.Room` connection, one per meeting. Creates on first participant join, destroys on last leave. |
| `LiveKitAudioAdapter` | `kutana_providers/audio/livekit_adapter.py` | Subscribes to room audio tracks. Spawns a per-participant async consumer task that reads `rtc.AudioFrame` objects, resamples/downmixes to PCM16 16 kHz mono, and pipes to `AudioPipeline`/STT. |
| `LiveKitAudioPublisher` | `kutana_providers/audio/livekit_publisher.py` | Publishes TTS output into the room as a `LocalAudioTrack`. Accepts PCM16 24 kHz bytes from `TTSBridge`, splits into 20 ms frames, and forwards to `rtc.AudioSource`. |

### Worker Lifecycle

Mirrors the `AudioRouter` pattern — `ensure_livekit_worker()` is called on participant join to create the `rtc.Room` connection if one does not already exist, and `cleanup_livekit_worker()` is called when the last participant leaves to disconnect and release the room. LiveKit server `empty_timeout` acts as a safety net in case cleanup is not called (e.g. after a crash).

### SDK Choice

Kutana uses the `livekit` rtc SDK only — **not** the `livekit-agents` framework. The rtc SDK provides raw transport primitives (`rtc.Room`, `rtc.AudioStream`, `rtc.AudioSource`, `rtc.LocalAudioTrack`) that plug into the existing `AudioBridge`/`TTSBridge` orchestration stack without competing with it.

The `livekit-agents` framework owns room lifecycle and has its own opinionated STT → LLM → TTS pipeline; adding it would create two competing orchestration layers and doesn't fit Kutana's multi-agent meeting model (multiple AI agents per room, mixed-minus audio, per-speaker VAD, turn queues). See `livekit-sdk-choice.md` for the full rationale.

### TTS Routing

`agent_session._handle_spoken_text()` checks whether an active `LiveKitAgentWorker` exists for the meeting. If one is found, it calls `TTSBridge.synthesize_text()` and pipes the resulting PCM16 bytes to `publisher.push_audio()` for delivery via LiveKit. If no worker is present the call falls through to the legacy WebSocket broadcast path, maintaining backward compatibility.

### No Meeting Type Branching

Every meeting uses the same LiveKit audio path. Agent-only meetings (no human participants) have idle rooms with no audio tracks flowing. There is no conditional branching on meeting type, and no overhead for agent-only rooms beyond holding an open room connection.
