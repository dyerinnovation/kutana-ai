# Plan: Wire STT Provider into Audio Service

## Date: 2026-02-28

## Goal
Wire STT provider creation into the audio service so Twilio audio actually gets transcribed. The `_stt_provider = None` on line 51 of `main.py` means the `/audio-stream` endpoint rejects all connections. Fix this with a per-connection factory pattern.

## Steps

1. **Create `WhisperRemoteSTT` provider** — `packages/kutana-providers/src/kutana_providers/stt/whisper_remote_stt.py`
   - Remote Whisper STT that calls DGX Spark vLLM OpenAI-compatible API
   - Buffers PCM16 audio, writes temp WAV, POSTs to `/v1/audio/transcriptions`
   - Register `whisper-remote` in `registry.py`, export from `stt/__init__.py`

2. **Add STT config to `AudioServiceSettings`** in `main.py`
   - `stt_provider`, `stt_api_key`, `whisper_model_size`, `whisper_api_url`

3. **Add `_create_stt_provider()` factory function** in `main.py`
   - Builds provider-specific kwargs, calls `default_registry.create()`

4. **Replace `_stt_provider` global with `_settings`**

5. **Update `lifespan()` to validate STT config on startup**
   - Create test provider instance, close immediately to validate config

6. **Update `/audio-stream` endpoint for per-connection STT**
   - Create fresh STT provider per WebSocket connection

7. **Create unit tests** — `test_stt_wiring.py`

8. **Create Redis integration tests** — `test_redis_integration.py`

9. **Update TASKLIST.md** — check off completed item

## Key Files
- `services/audio-service/src/audio_service/main.py`
- `packages/kutana-providers/src/kutana_providers/stt/whisper_remote_stt.py` (new)
- `packages/kutana-providers/src/kutana_providers/registry.py`
- `packages/kutana-providers/src/kutana_providers/stt/__init__.py`
- `services/audio-service/tests/test_stt_wiring.py` (new)
- `services/audio-service/tests/test_redis_integration.py` (new)
