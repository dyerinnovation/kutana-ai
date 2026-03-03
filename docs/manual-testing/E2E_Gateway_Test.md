# E2E Agent Gateway Test — Walkthrough

This guide walks you through verifying the full agent-gateway pipeline:
**Agent connects via WebSocket → sends audio → audio is transcribed → transcript segments are returned to the agent.**

## Prerequisites

- Docker (for Redis)
- `uv` installed
- DGX Spark reachable at `spark-b0f2.local` (for Whisper Remote STT)
- Project dependencies synced

## 1. Sync Dependencies

```bash
cd /path/to/convene-ai

# Sync all workspace packages
UV_LINK_MODE=copy uv sync --all-packages

# Fix macOS .venv hidden flag (required for imports to work)
chflags -R nohidden .venv
```

## 2. Start Redis

```bash
docker compose up redis -d
```

Verify Redis is running:

```bash
docker compose exec redis redis-cli ping
# Expected: PONG
```

## 3. Verify DGX Spark Whisper is Running

```bash
curl -s http://spark-b0f2.local/convene-stt/v1/models | python3 -m json.tool
```

You should see a response listing `openai/whisper-large-v3`. If this fails:
- Check that DGX Spark is powered on and reachable: `ping spark-b0f2.local`
- SSH in and check the pod: `ssh jondyer3@spark-b0f2.local` then check K8s

## 4. Start the Agent Gateway

Open a new terminal:

```bash
cd /path/to/convene-ai

# Fix venv hidden flags (do this each time after uv sync)
chflags -R nohidden .venv

# Set STT to whisper-remote pointing at DGX Spark
export AGENT_GATEWAY_STT_PROVIDER=whisper-remote
export AGENT_GATEWAY_WHISPER_API_URL=http://spark-b0f2.local/convene-stt/v1

# Start the gateway
uv run uvicorn agent_gateway.main:app --port 8003
```

You should see:
```
INFO:     agent-gateway starting up (max_connections=100)
INFO:     Event relay started (group=agent-gateway)
INFO:     Uvicorn running on http://0.0.0.0:8003
```

Verify the health endpoint:
```bash
curl http://localhost:8003/health
# Expected: {"status":"healthy","service":"agent-gateway","active_connections":0}
```

## 5. Run the E2E Test

### Option A: Smoke Test (Generated Sine Wave)

This sends a 3-second 440Hz sine wave. The STT will likely return garbled text or silence — but it proves the full pipeline works end-to-end.

```bash
cd /path/to/convene-ai
uv run python scripts/test_e2e_gateway.py --generate-audio --wait-timeout 20
```

### Option B: Real Audio File

Provide a 16kHz mono 16-bit PCM WAV file. You can convert any audio file with ffmpeg:

```bash
# Convert any audio to the required format
ffmpeg -i input.mp3 -ar 16000 -ac 1 -f wav -acodec pcm_s16le test-audio.wav

# Run the test
uv run python scripts/test_e2e_gateway.py --audio-file test-audio.wav --wait-timeout 30
```

### Custom Options

```bash
uv run python scripts/test_e2e_gateway.py \
    --audio-file test-audio.wav \
    --gateway-url ws://localhost:8003 \
    --jwt-secret change-me-in-production \
    --meeting-id 550e8400-e29b-41d4-a716-446655440000 \
    --wait-timeout 30
```

## 6. What to Expect

### Successful Output

```
2026-03-01 12:00:00 [INFO] Generating 3s sine-wave audio (440Hz)
2026-03-01 12:00:00 [INFO] Meeting ID: a1b2c3d4-...
2026-03-01 12:00:00 [INFO] Connecting to ws://localhost:8003
2026-03-01 12:00:00 [INFO] Connected! Sending join_meeting...
2026-03-01 12:00:00 [INFO] Joined meeting a1b2c3d4-... with capabilities: ['listen', 'transcribe', 'speak']
2026-03-01 12:00:00 [INFO] Sent 30 chunks (3.0s of audio, 96000 bytes)
2026-03-01 12:00:00 [INFO] Waiting up to 20s for transcript segments...
2026-03-01 12:00:01 [INFO] EVENT: meeting.started
2026-03-01 12:00:08 [INFO] TRANSCRIPT [0.0-3.0s] (confidence=0.85): [transcribed text here]
2026-03-01 12:00:08 [INFO] Left meeting.
2026-03-01 12:00:08 [INFO] SUCCESS: Received 1 transcript segment(s)
```

### Key Timing

- Audio is sent immediately after joining
- The gateway's AudioBridge triggers transcription every **5 seconds** (configurable)
- First transcript will arrive after ~5-10 seconds (5s interval + Whisper processing time)
- With `--wait-timeout 20`, the script will wait up to 20 seconds for results

### Events You'll See

1. `joined` — Confirmation of meeting join
2. `event: meeting.started` — AudioPipeline started the STT stream
3. `transcript` — One or more transcript segments with text, timestamps, confidence
4. (On leave) `event: meeting.ended` — AudioPipeline closed

## 7. Troubleshooting

### "ModuleNotFoundError: No module named 'agent_gateway'"

The macOS `UF_HIDDEN` flag is preventing `.pth` files from being processed.

```bash
chflags -R nohidden .venv
```

### "Connection refused" on ws://localhost:8003

The gateway isn't running. Start it per step 4.

### "4001: token_expired" or auth errors

The JWT secret in the test script doesn't match the gateway's `AGENT_GATEWAY_JWT_SECRET`. Default is `change-me-in-production`. Pass `--jwt-secret <your-secret>` to the script.

### No transcripts received (timeout)

1. **Check Redis**: `docker compose exec redis redis-cli XLEN convene:events` — should show entries after sending audio
2. **Check STT**: The Whisper API at `spark-b0f2.local` may be down. Verify with the curl command in step 3.
3. **Check timing**: Transcription happens every 5 seconds. Increase `--wait-timeout` to 30+.
4. **Check gateway logs**: Look for `Segment from meeting` or error messages in the gateway terminal.

### "Expected 16kHz mono, got ..."

Your WAV file needs to be 16kHz mono PCM16. Convert with:
```bash
ffmpeg -i input.wav -ar 16000 -ac 1 -f wav -acodec pcm_s16le output.wav
```

### Redis stream not being consumed

Check if the consumer group exists:
```bash
docker compose exec redis redis-cli XINFO GROUPS convene:events
```
Should show group `agent-gateway` with consumer `gateway-0`.
