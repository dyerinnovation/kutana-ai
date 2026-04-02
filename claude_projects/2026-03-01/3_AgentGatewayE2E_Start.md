# Milestone M3: Agent Gateway E2E — Plan

**Date**: 2026-03-01
**Objective**: Bridge the gaps in agent-gateway so an agent can connect via WebSocket, send PCM16 audio, and receive real-time transcript segments back.

## Problem

Audio sent by agents is decoded but discarded (TODO on line 169 of agent_session.py), and transcript events come back as generic JSON instead of structured `TranscriptMessage` objects.

## Architecture

```
Agent (WebSocket) → AgentSession._handle_audio() → AudioBridge.process_audio()
→ AudioPipeline → STT Provider → TranscriptSegment
→ EventPublisher → Redis Streams → EventRelay._handle_event()
→ session.send_transcript() → Agent (WebSocket)
```

## Implementation Steps

1. **Add workspace deps** — `kutana-providers` + `audio-service` to agent-gateway/pyproject.toml
2. **Extend settings** — STT config fields (stt_provider, stt_api_key, whisper_model_size, whisper_api_url)
3. **Create AudioBridge** — New `audio_bridge.py` managing per-meeting AudioPipeline instances
4. **Wire into agent_session.py** — Replace TODO with AudioBridge calls
5. **Enhance EventRelay** — transcript.segment.final → send_transcript() instead of send_event()
6. **Wire into main.py** — Create AudioBridge in lifespan, pass to sessions
7. **Write tests** — test_audio_bridge.py, test_event_relay_transcript.py, test_e2e_flow.py
8. **Update TASKLIST.md** — Check off completed Phase 2 items

## Key Decision

Embed `AudioPipeline` directly in agent-gateway (it's just a class). No inter-service HTTP/gRPC needed.

## Files

| File | Action |
|------|--------|
| services/agent-gateway/pyproject.toml | MODIFY |
| services/agent-gateway/src/agent_gateway/settings.py | MODIFY |
| services/agent-gateway/src/agent_gateway/audio_bridge.py | CREATE |
| services/agent-gateway/src/agent_gateway/agent_session.py | MODIFY |
| services/agent-gateway/src/agent_gateway/event_relay.py | MODIFY |
| services/agent-gateway/src/agent_gateway/main.py | MODIFY |
| services/agent-gateway/tests/test_audio_bridge.py | CREATE |
| services/agent-gateway/tests/test_event_relay_transcript.py | CREATE |
| services/agent-gateway/tests/test_e2e_flow.py | CREATE |
| docs/TASKLIST.md | MODIFY |
