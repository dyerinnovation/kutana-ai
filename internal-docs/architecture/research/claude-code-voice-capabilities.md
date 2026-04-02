# Claude Code Voice Capabilities & Kutana Integration

## Claude Code Voice Mode — What It Actually Is

Per official Anthropic documentation (code.claude.com/docs/en/voice-dictation):

- **Voice INPUT only** — push-to-talk dictation via `/voice` command (spacebar hold)
- **No voice OUTPUT** — Claude Code responses are text-only in the terminal
- Audio is captured locally via native modules (macOS/Linux/Windows)
- Audio is sent to **Anthropic's servers** for transcription (requires Claude.ai account auth)
- Transcribed text is inserted into the prompt input
- **Not available** via API keys, Bedrock, Vertex AI, or Foundry
- **Not accessible** to MCP servers — audio stream is internal to Claude Code

## Implications for Kutana

Claude Code is a **text agent** in Kutana's capability taxonomy:

| Capability | Claude Code | True Voice Agent |
|-----------|-------------|-----------------|
| Sends text to meeting | ✅ via `reply` tool | ✅ via control channel |
| Receives transcript | ✅ via channel events | ✅ via channel events |
| Sends audio to meeting | ❌ no audio output | ✅ via `/audio/connect` sidecar |
| Receives room audio | ❌ no audio input | ✅ via `/audio/connect` sidecar |
| Voice output method | Gateway TTS synthesis | Own audio stream |

### How Claude Code Gets a Voice

Claude Code uses the **TTS path** (not the audio sidecar path):

```
Claude Code
    │ text response
    ▼
Channel Server (MCP stdio)
    │ SpokenText message
    ▼
Agent Gateway (control WebSocket)
    │ routes to TTSBridge
    ▼
TTSBridge → TTSProvider.synthesize()
    │ PCM16 audio bytes
    ▼
Broadcast tts.audio event → all meeting participants
    │
    ▼
Browser: decode + play audio, show "Speaking..." on agent tile
```

No audio sidecar (`/audio/connect`) is needed. Claude Code only uses the **control plane** WebSocket.

### Capability Declaration

When Claude Code joins a meeting, the channel server should declare:

```json
{
  "capabilities": ["listen", "transcribe", "data_channel"],
  "tts_enabled": true,
  "tts_voice": null
}
```

- `tts_enabled: true` — tells the gateway to assign a voice and enable TTS synthesis
- `tts_voice: null` — use voice pool assignment (round-robin from default pool)
- No `voice_in` or `voice_out` — these are for agents with their own audio I/O

## Dual-Path Architecture (for reference)

The agent gateway supports two connection types:

**Path 1: Control Plane** (all agents, including Claude Code)
- Endpoint: `/agent/connect`
- Protocol: JSON over WebSocket
- Messages: join, leave, chat, start_speaking, spoken_text, events
- Used by: ALL agents

**Path 2: Audio Sidecar** (voice agents only, NOT Claude Code)
- Endpoint: `/audio/connect`
- Protocol: Binary PCM16 frames (20ms chunks, 16kHz mono)
- Auth: Separate short-lived JWT (5-min expiry)
- Used by: Custom agents with bidirectional audio (e.g., phone bots, hardware devices)

Claude Code uses Path 1 only. The gateway's TTS pipeline handles voice output.

## Future Considerations

- If Anthropic adds voice output to Claude Code in the future, the channel server could be updated to use the audio sidecar path instead of TTS
- Third-party MCP voice servers (VoiceMode, Claude-to-Speech) exist but are not integrated with Kutana's meeting audio pipeline
- The channel server's stdio transport cannot carry binary audio — any future audio integration would need a parallel connection

## References

- Voice dictation docs: https://code.claude.com/docs/en/voice-dictation
- Kutana voice agent architecture: `internal-docs/architecture/research/voice-agent-integration.md`
- Kutana TTS pipeline: `internal-docs/architecture/research/tts-text-agents.md`
- TTS tier enforcement: `internal-docs/architecture/research/tts-tier-enforcement-plan.md`
