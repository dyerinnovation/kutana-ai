# Archive Twilio Files and Refactor Audio Service

## Objective
Remove Twilio-specific code from the Convene AI audio service, archive the files, and refactor the audio pipeline to accept PCM16 16kHz mono audio directly (no mulaw transcoding). This prepares the audio service for transport-agnostic adapters (e.g., LiveKit, WebSocket).

## Steps

### 1. Create archive directory and copy files
- Create `~/Documents/Dyer_Innovation/archive/convene-twilio/`
- Copy `twilio_handler.py`, `meeting_dialer.py`, `scripts/dial_test.py`, `docs/milestone-testing/M1_Live_Test.md`

### 2. Delete archived files from the repo
- Remove the four copied files from the working tree

### 3. Update audio-service/pyproject.toml
- Remove `"twilio>=9.0"` from dependencies
- Update description to "Audio pipeline and transport adapters for Convene AI"

### 4. Refactor AudioPipeline (audio_pipeline.py)
- Remove ALL mulaw transcoding code (decode table, _build_mulaw_table, _upsample_8k_to_16k, _transcode_mulaw_to_pcm16)
- Keep retry/buffer logic, event publishing, get_segments()
- Main method `process_audio(self, chunk: bytes)` accepts PCM16 16kHz mono directly
- Update docstrings to reference PCM16 instead of Twilio/mulaw

### 5. Create AudioAdapter ABC (audio_adapter.py)
- New file: abstract base class for audio transport adapters
- Defines `start()` and `stop()` abstract methods
- Takes an AudioPipeline in constructor

### 6. Update main.py
- Remove all Twilio references (TwilioHandler, twilio settings, /audio-stream websocket)
- Keep STT factory, lifespan, health check
- Update app description and version

### 7. Update .env.example
- Remove Twilio section (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER)
- Add Agent Gateway and LiveKit sections
