# LiveKit SDK Choice: `livekit` rtc vs `livekit-agents`

## Overview

Kutana uses the `livekit` Python rtc SDK for LiveKit integration, not the `livekit-agents` framework. The rtc SDK provides raw WebRTC transport primitives (`rtc.Room`, `rtc.AudioStream`, `rtc.AudioSource`, `rtc.LocalAudioTrack`) that plug into Kutana's existing audio orchestration stack without competing with it.

## The Two Packages

**`livekit` (rtc SDK)**
Transport primitives only. Connect to a room, subscribe to remote tracks, publish local tracks. No opinions about agent lifecycle, STT/TTS pipelines, or job dispatch. You get `rtc.Room` events and PCM frames — what you do with them is up to you.

**`livekit-agents`**
A full agent framework built on top of the rtc SDK. Provides `AgentServer`, `JobContext`, `WorkerOptions`, a voice pipeline, and STT/TTS plugin system. It assumes ownership of the agent lifecycle: it dispatches jobs when participants join, manages room connections end-to-end, and handles shutdown. The framework's pipeline wires STT → silence detection → LLM → TTS as a single opinionated unit.

## Why Kutana Uses rtc Only

Kutana already has a complete audio orchestration stack:

| Component | Responsibility |
|-----------|----------------|
| `ConnectionManager` | Session registry, AudioRouter lifecycle per meeting |
| `AudioBridge` | Per-meeting `AudioPipeline` creation and teardown |
| `AudioPipeline` | STT streaming with retry, buffering, Redis event publishing |
| `AudioRouter` | Mixed-minus audio distribution + VAD silence detection |
| `AudioSessionHandler` | Per-agent audio session management |
| `TTSBridge` | TTS synthesis, voice pool, caching, meeting broadcast |

Adding `livekit-agents` would create two competing orchestration layers:

- The agents framework wants to own the room connection lifecycle. `ConnectionManager` and `AudioBridge` already own that.
- The framework's voice pipeline has its own STT/TTS plugin system. Kutana already has `ProviderRegistry` with swappable providers (Deepgram, Whisper, Cartesia, ElevenLabs, etc.).
- The framework's job dispatch model (one agent per `JobContext`) doesn't fit Kutana's multi-agent meeting model where several AI agents can be active in the same room simultaneously.
- Kutana has domain-specific audio semantics the framework doesn't know about: turn queues, mixed-minus mixing, per-speaker VAD timeouts, and multi-stream transcript routing.

What Kutana actually needs from LiveKit is just the transport layer:
- **`LiveKitAudioAdapter`** — subscribes to `rtc.AudioStream` events from the room and pipes PCM frames into `AudioPipeline`.
- **`LiveKitAudioPublisher`** — takes TTS output bytes from `TTSBridge` and publishes them to the room via `rtc.AudioSource` + `rtc.LocalAudioTrack`.

Both are thin wrappers around rtc primitives, plugged into the existing architecture via the `AudioAdapter` ABC and `ProviderRegistry`. No framework ownership of lifecycle, no duplicate pipeline.

## When `livekit-agents` Might Make Sense

- Greenfield projects with no existing audio orchestration — the framework is a fast path to a working voice agent.
- Projects that want LiveKit's opinionated STT → LLM → TTS pipeline with minimal custom code.
- If Kutana ever migrates fully to LiveKit's agent model. This is unlikely given the custom meeting semantics (turn queue, mixed-minus, VAD per speaker, multi-agent rooms) that would need to be rebuilt inside the framework's extension points.

## Integration Pattern

```
Browser ──WebRTC──→ LiveKit Room ←──rtc.Room──── Agent Gateway
                         │                           │
                    rtc.AudioStream              LiveKitAudioAdapter
                         │                           │
                         └──── PCM16 16kHz ──────→ AudioPipeline → STT
                                                     │
                    rtc.AudioSource              LiveKitAudioPublisher
                         │                           │
                         └──── PCM16 24kHz ←──── TTSBridge → Cartesia
```

The `LiveKitAudioAdapter` and `LiveKitAudioPublisher` are the only components that touch the `livekit` rtc SDK. Everything above `AudioPipeline` and `TTSBridge` is transport-agnostic.

## api-server: `livekit-api` only (no rtc)

The api-server uses only the `livekit-api` package — **not** the `livekit` rtc SDK. api-server never joins rooms; its LiveKit responsibilities are limited to:

- Room provisioning via `LiveKitAPI.room.create_room()` (REST, idempotent).
- Participant JWT generation via `api.AccessToken(...).with_grants(VideoGrants(...)).to_jwt()`.

Skipping the rtc dependency keeps the api-server image small and avoids pulling in native WebRTC binaries on a service that doesn't need them. Only agent-gateway (which actually connects to rooms) depends on the `livekit` rtc SDK.

## References

- `packages/kutana-providers/src/kutana_providers/audio/livekit_adapter.py` — LiveKitAudioAdapter
- `packages/kutana-providers/src/kutana_providers/audio/livekit_publisher.py` — LiveKitAudioPublisher
- `services/audio-service/src/audio_service/audio_adapter.py` — AudioAdapter ABC
- `services/agent-gateway/src/agent_gateway/audio_bridge.py` — AudioBridge (STT orchestration)
- `services/agent-gateway/src/agent_gateway/tts_bridge.py` — TTSBridge (TTS orchestration)
- `services/agent-gateway/src/agent_gateway/connection_manager.py` — ConnectionManager (session registry)
- `packages/kutana-providers/src/kutana_providers/registry.py` — ProviderRegistry
