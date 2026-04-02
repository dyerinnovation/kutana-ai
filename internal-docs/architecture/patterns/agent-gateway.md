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
