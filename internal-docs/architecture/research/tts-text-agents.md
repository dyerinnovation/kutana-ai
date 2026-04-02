# TTS Pipeline for Text-Only Agents

> Design reference for giving text-only agents a synthesized voice in meetings.
> Covers opt-in TTS, the TTSProvider ABC, provider comparison, cost model,
> voice assignment, and gateway-side synthesis flow.

---

## Overview

Not all agents need live microphone input, but many should be able to *speak* to the meeting room.
The `tts_enabled` capability lets a text-only agent send a text string and have the gateway
synthesize it into PCM16 audio, mix it into the meeting, and broadcast it to all participants.

This keeps agent logic simple: no audio capture, no VAD, no sidecar streaming. The agent calls
`kutana_start_speaking` with a `text` argument and the gateway handles everything else.

---

## Opt-In Design

TTS is opt-in — agents must declare `tts_enabled` in their capability at join time. Agents that
do not declare this capability cannot call `kutana_start_speaking` with a `text` argument.

This prevents accidental cost runup (TTS API calls are metered) and makes capabilities explicit
in participant logs.

```python
# Agent declares TTS capability when joining
result = await mcp.call_tool("kutana_join_meeting", {
    "meeting_id": "abc123",
    "audio_capability": "tts_enabled",
    "tts_voice_id": "a0e99841-438c-4a64-b679-ae501e7d6091"  # optional override
})
```

If `tts_voice_id` is omitted, the gateway uses the voice assigned to the agent in the Kutana
dashboard (Settings → Agents → Voice). If no voice is configured, the provider default is used.

---

## TTSProvider ABC

All TTS providers implement the same abstract interface. The gateway calls `synthesize()` and
streams the resulting chunks into the meeting audio mix.

```python
from abc import ABC, abstractmethod
from typing import AsyncIterator
from kutana_core.models.voice import Voice

class TTSProvider(ABC):
    """Abstract base class for text-to-speech providers."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_id: str | None = None,
    ) -> AsyncIterator[bytes]:
        """Synthesize text to PCM16 16kHz mono audio.

        Args:
            text: The text to synthesize.
            voice_id: Provider-specific voice identifier. Uses default if omitted.

        Yields:
            Raw PCM16 bytes (20ms frames, 640 bytes each).
        """
        ...

    @abstractmethod
    async def get_voices(self) -> list[Voice]:
        """Return available voices for this provider.

        Returns:
            List of Voice objects with id, name, language, and gender fields.
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """Release underlying HTTP client resources."""
        ...
```

### Output Contract

All providers **must** yield PCM16 16kHz mono bytes, regardless of their internal format.
Providers that generate MP3 (e.g., ElevenLabs) must transcode before yielding.

```python
# Internal transcoding example — ElevenLabs returns MP3
import av

async def _mp3_to_pcm16(mp3_bytes: bytes) -> bytes:
    container = av.open(io.BytesIO(mp3_bytes))
    stream = next(s for s in container.streams if s.type == "audio")
    resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
    pcm_bytes = b""
    for frame in container.decode(stream):
        for rf in resampler.resample(frame):
            pcm_bytes += bytes(rf.planes[0])
    return pcm_bytes
```

---

## Provider Comparison

| Provider | TTFA* | Quality | Cost | Format | Free Tier | Notes |
|----------|-------|---------|------|--------|-----------|-------|
| **Cartesia Sonic** | 40–90ms | Very good | ~$0.065/min | PCM16 native | None | Recommended for production |
| **ElevenLabs** | 200–400ms | Highest | ~$0.18/min | MP3 (transcode needed) | 10k chars/mo | Best voice quality + cloning |
| **OpenAI TTS** | 150–300ms | Good | $0.015/1k chars | MP3 | None | Cheapest at low volume |
| **AWS Polly** | 100–200ms | OK | $0.004/1k chars | MP3/PCM | None | Cheapest at high volume |
| **Piper** | <50ms | Acceptable | Free (self-hosted) | PCM16 native | N/A | Dev/offline use; no API key |

\*TTFA = Time to First Audio chunk (lower is better for real-time speech)

### Recommendation by Tier

| Tier | Provider | Rationale |
|------|----------|-----------|
| Free | Piper (local dev) / OpenAI TTS (cloud) | No upfront cost |
| Pro | Cartesia | Best latency, good quality |
| Business | Cartesia (default) + ElevenLabs (custom voices) | Cloning for branded agents |
| Enterprise | Cartesia or self-hosted Piper | Data sovereignty option |

---

## Cartesia (Recommended)

**Why Cartesia first:** Native PCM16 output (no transcoding), lowest latency, streaming API.

```python
class CartesiaTTS(TTSProvider):
    """Cartesia Sonic TTS provider."""

    BASE_URL = "https://api.cartesia.ai"

    def __init__(self, api_key: str, voice_id: str = "default", model_id: str = "sonic-english") -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._model_id = model_id
        self._client: httpx.AsyncClient | None = None

    async def synthesize(self, text: str, voice_id: str | None = None) -> AsyncIterator[bytes]:
        client = await self._get_client()
        async with client.stream(
            "POST",
            f"{self.BASE_URL}/tts/bytes",
            json={
                "model_id": self._model_id,
                "transcript": text,
                "voice": {"mode": "id", "id": voice_id or self._voice_id},
                "output_format": {
                    "container": "raw",
                    "encoding": "pcm_s16le",
                    "sample_rate": 16000,
                },
            },
            headers={"X-API-Key": self._api_key},
        ) as response:
            async for chunk in response.aiter_bytes(chunk_size=640):
                yield chunk
```

---

## ElevenLabs

Higher quality, more expensive, requires MP3→PCM16 transcoding.

```python
class ElevenLabsTTS(TTSProvider):
    """ElevenLabs streaming TTS provider."""

    BASE_URL = "https://api.elevenlabs.io/v1"

    async def synthesize(self, text: str, voice_id: str | None = None) -> AsyncIterator[bytes]:
        vid = voice_id or self._voice_id
        client = await self._get_client()
        async with client.stream(
            "POST",
            f"{self.BASE_URL}/text-to-speech/{vid}/stream",
            json={"text": text, "model_id": self._model_id},
            headers={"xi-api-key": self._api_key},
        ) as response:
            mp3_buffer = b""
            async for chunk in response.aiter_bytes():
                mp3_buffer += chunk
            # Transcode accumulated MP3 → PCM16
            pcm = await _mp3_to_pcm16(mp3_buffer)
            for i in range(0, len(pcm), 640):
                yield pcm[i:i + 640]
```

**Note:** ElevenLabs streaming delivers MP3 frame-by-frame but transcoding requires a full MP3
frame boundary. Buffer until a complete frame, then transcode and yield PCM. Alternatively, use
the `/stream` endpoint with `output_format=pcm_16000` if available on your plan.

---

## Piper (Local / Offline)

Zero API cost, runs on CPU, useful for development.

```python
# Piper is invoked as a subprocess — no Python bindings
import asyncio
import shutil

class PiperTTS(TTSProvider):
    """Self-hosted Piper neural TTS."""

    def __init__(self, voice: str = "en_US-lessac-medium") -> None:
        self._voice = voice
        piper_path = shutil.which("piper")
        if not piper_path:
            raise RuntimeError("piper binary not found — run: pip install piper-tts")
        self._piper_path = piper_path

    async def synthesize(self, text: str, voice_id: str | None = None) -> AsyncIterator[bytes]:
        voice = voice_id or self._voice
        proc = await asyncio.create_subprocess_exec(
            self._piper_path,
            "--model", voice,
            "--output-raw",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate(text.encode())
        # Piper outputs PCM16 16kHz mono directly
        for i in range(0, len(stdout), 640):
            yield stdout[i:i + 640]
```

---

## Voice Assignment

Agents get a default voice from three resolution layers (highest priority first):

1. **Per-call override** — `tts_voice_id` in the `kutana_join_meeting` call
2. **Agent config** — voice assigned in the Kutana dashboard (persisted in `agents.tts_voice_id`)
3. **Provider default** — the TTS provider's built-in default voice

```python
# Voice resolution in the gateway
async def resolve_voice(agent_id: str, requested_voice: str | None) -> str:
    if requested_voice:
        return requested_voice
    agent = await db.get_agent(agent_id)
    if agent.tts_voice_id:
        return agent.tts_voice_id
    return "default"
```

### Voice Assignment UI

The Kutana dashboard (Settings → Agents → Voice) lets workspace admins assign voices to agents.
Voices are fetched from the configured TTS provider at page load. Custom voice IDs (e.g., cloned
ElevenLabs voices) can be pasted directly.

---

## Cost Optimization

### Caching

Short, repeated phrases (e.g., "I've raised my hand", "Thank you") should be pre-synthesized
and cached in Redis. Cache key: `tts:{provider}:{voice_id}:{sha256(text)}`.

```python
CACHE_TTL = 86400  # 24 hours

async def synthesize_cached(
    redis: Redis,
    provider: TTSProvider,
    text: str,
    voice_id: str,
) -> bytes:
    key = f"tts:{provider.__class__.__name__}:{voice_id}:{hashlib.sha256(text.encode()).hexdigest()[:16]}"
    cached = await redis.get(key)
    if cached:
        return cached
    audio = b"".join([chunk async for chunk in provider.synthesize(text, voice_id)])
    await redis.setex(key, CACHE_TTL, audio)
    return audio
```

### Length Limits

| Tier | Max chars per `kutana_start_speaking` call | Estimated cost |
|------|----------------------------------------------|----------------|
| Free | 500 chars | ~$0.001 (Cartesia) |
| Pro | 2,000 chars | ~$0.004 |
| Business | 5,000 chars | ~$0.010 |
| Enterprise | Unlimited | Custom |

### Metering

TTS usage is metered per character synthesized and billed alongside meeting minutes. The
`api_key_events` audit log records each synthesis call with `character_count` in `metadata`.

---

## Gateway Synthesis Flow

```
Agent (text) ─── kutana_start_speaking({text}) ──► MCP Server
                                                         │
                                                         │── enqueue TurnManager
                                                         │
                                                         │◄── speaker.granted
                                                         │
                                                         ▼
                                                   Gateway TTS Engine
                                                         │
                                                         │── resolve_voice(agent_id)
                                                         │── TTSProvider.synthesize(text)
                                                         │
                                                         ▼
                                                   AudioRouter
                                                         │
                                                         │── mixed-minus broadcast
                                                         │   to all participants
                                                         │
                                                         ▼
                                                  mark_finished_speaking (auto)
```

---

## Implementation Checklist

- [x] `CartesiaTTS` provider implemented
- [x] `ElevenLabsTTS` provider implemented
- [ ] `PiperTTS` provider (planned — not in default registry yet)
- [ ] OpenAI TTS provider
- [ ] AWS Polly provider
- [ ] `TTSProvider.synthesize()` contract enforces PCM16 16kHz mono output
- [ ] Gateway `TTS Engine` service component
- [ ] Voice resolution logic (per-call → agent config → default)
- [ ] TTS result cache (Redis, 24h TTL)
- [ ] Character metering in `api_key_events`
- [ ] Length limits by plan tier
- [ ] Voice assignment UI in dashboard

---

## Related Files

- `packages/kutana-providers/src/kutana_providers/tts/` — Provider implementations
- `docs/providers/cartesia-tts.md` — Cartesia setup and usage
- `docs/providers/elevenlabs-tts.md` — ElevenLabs setup and usage
- `docs/providers/piper-tts.md` — Piper local TTS setup
- `docs/research/voice-agent-integration.md` — Voice sidecar and bidirectional audio
- `docs/technical/cost-architecture.md` — Full cost model and billing tiers
