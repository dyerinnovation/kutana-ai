# Full End-to-End Demo

## Purpose
Run the automated `demo_meeting_flow.py` script and verify all 13 steps complete successfully, then validate results in the database and Redis.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed (infrastructure running)
- API server (8000), gateway (8003) running
- PostgreSQL and Redis running
- Audio file available at `data/input/librispeech_sample.flac`
- STT provider running (for transcript verification — optional but recommended)

> **Note:** This is the capstone test. It exercises the entire stack end-to-end in an automated script. Run this after verifying individual features in docs 01-09.

## Step 1: Verify Audio File Exists

```bash
ls -la data/input/librispeech_sample.flac
ls -la data/input/test-speech.wav
```

Expected: Both files exist. If missing, you'll need to provide audio files.

## Step 2: Run the Demo Script

```bash
uv run python scripts/demo_meeting_flow.py --audio data/input/librispeech_sample.flac
```

### Expected Output — All 13 Steps

The script should log each step as it executes:

| Step | Action | Expected Output |
|------|--------|----------------|
| 1 | Register user | `✓ Registered user <email>` (or login if exists) |
| 2 | Create agent | `✓ Created agent: <name> (id: <uuid>)` |
| 3 | Generate API key | `✓ Generated API key: cvn_...` |
| 4 | Create meeting | `✓ Created meeting: <title> (id: <uuid>, status: scheduled)` |
| 5 | Start meeting | `✓ Started meeting (status: active)` |
| 6 | Exchange for gateway token | `✓ Got gateway token` |
| 7 | Connect WebSocket | `✓ WebSocket connected to ws://localhost:8003/agent/connect` |
| 8 | Join meeting | `✓ Joined meeting (room: <name>, capabilities: [...])` |
| 9 | Stream audio | `✓ Streamed <N> audio chunks` |
| 10 | Listen for transcripts | `✓ Received <N> transcript segments` |
| 11 | Leave meeting | `✓ Left meeting` |
| 12 | End meeting | `✓ Ended meeting (status: completed)` |
| 13 | Create task | `✓ Created task: <description> (id: <uuid>)` |

The script returns a summary with the user ID, agent ID, meeting ID, and transcript count.

## Step 3: Verify Meeting Status in Database

```bash
docker exec -it $(docker compose ps -q postgres) psql -U kutana -d kutana -c \
  "SELECT id, title, status, started_at, ended_at
   FROM meetings
   ORDER BY created_at DESC
   LIMIT 3;"
```

Expected: Most recent meeting shows `status = 'completed'` with both `started_at` and `ended_at` set.

## Step 4: Verify Task in Database

```bash
docker exec -it $(docker compose ps -q postgres) psql -U kutana -d kutana -c \
  "SELECT id, meeting_id, description, priority, created_at
   FROM tasks
   ORDER BY created_at DESC
   LIMIT 3;"
```

Expected: Task created in Step 13 appears with the correct meeting ID and priority.

## Step 5: Verify Redis Events

```bash
docker exec -it $(docker compose ps -q redis) redis-cli XLEN kutana:events
```

Expected: Non-zero count. The exact number depends on transcript segments and events generated.

```bash
# View recent events
docker exec -it $(docker compose ps -q redis) redis-cli \
  XREVRANGE kutana:events + - COUNT 5
```

Expected: Events include `transcript.segment.final`, `meeting.started`, `meeting.ended`, etc.

## Step 6: Run Without Audio (Silence Test)

```bash
uv run python scripts/demo_meeting_flow.py
```

Expected:
- Steps 1-8 complete normally
- Step 9: Streams 2 seconds of silence
- Step 10: Zero transcript segments (expected without real audio)
- Steps 11-13 complete normally

This verifies the full flow works even without STT output.

## Step 7: Run with Alternative Audio

```bash
uv run python scripts/demo_meeting_flow.py --audio data/input/test-speech.wav
```

Expected: Same 13 steps complete. Transcript count may differ from the FLAC file.

## Step 8: Compare Transcript Counts

| Audio File | Expected Transcripts |
|------------|---------------------|
| `librispeech_sample.flac` | ~20-30 segments (depends on STT provider) |
| `test-speech.wav` | Varies by content length |
| No audio (silence) | 0 segments |

## Verification Checklist

- [ ] `demo_meeting_flow.py` with FLAC audio completes all 13 steps
- [ ] User registered (or logged in if existing)
- [ ] Agent created with correct capabilities
- [ ] API key generated (starts with `cvn_`)
- [ ] Meeting created with status "scheduled"
- [ ] Meeting started (status → "active")
- [ ] Gateway token obtained
- [ ] WebSocket connected
- [ ] Joined meeting with granted capabilities
- [ ] Audio streamed (correct chunk count)
- [ ] Transcripts received (non-zero with real audio)
- [ ] Meeting left cleanly
- [ ] Meeting ended (status → "completed")
- [ ] Task created in database
- [ ] Redis `kutana:events` stream has events
- [ ] Silence test completes without errors
- [ ] Alternative audio file test completes

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Step 1 fails (register) | User may already exist — script should handle login fallback |
| Step 6 fails (token exchange) | Verify API key was generated correctly. Check for rate limiting |
| Step 7 fails (WebSocket) | Verify gateway is running on port 8003. Check `AGENT_GATEWAY_JWT_SECRET` |
| Step 9 hangs | Audio file may be too large. Check file format (must be decodable by Python) |
| Step 10: 0 transcripts with real audio | STT provider not running. Check `WHISPER_API_URL` in `.env`. See [E2E Gateway Test](../manual-testing/E2E_Gateway_Test.md) for STT debugging |
| `FileNotFoundError` on audio | Verify path is relative to project root: `data/input/librispeech_sample.flac` |
| Redis XLEN returns 0 | Gateway may not be writing events. Check gateway logs for Redis connection errors |
| Script hangs at WebSocket | httpx may hang on `.local` hostnames. Ensure gateway uses `localhost` not mDNS |

## Cleanup

```bash
# The demo creates its own user/agent/meeting — no shared state to clean up
# To reset for a fresh run, you can clear the database:
# WARNING: This deletes ALL data
# docker exec -it $(docker compose ps -q postgres) psql -U kutana -d kutana -c "TRUNCATE users, agents, meetings, tasks CASCADE;"
```
