# Plan: Milestone M1 — Live Meeting Dial-In Test

**Date:** 2026-02-28
**Objective:** Deliver tooling and documentation to prove the full audio pipeline end-to-end with a real meeting dial-in.

## Context

The audio pipeline (TwilioHandler → AudioPipeline → STT → EventPublisher → Redis) and MeetingDialer are fully implemented. This session creates the glue to run it against a real meeting.

## Deliverables

1. **`docs/milestone-testing/M1_Live_Test.md`** — formal test plan with prerequisites, steps, pass/fail criteria
2. **`scripts/dial_test.py`** — standalone script: dials meeting, streams audio, reads Redis events
3. **Updated `.env.example`** — STT provider config + public URL vars
4. **Updated `AudioServiceSettings`** — `audio_service_public_url` field
5. **Updated `TASKLIST.md`** — M1 checked off, future telephony items added

## Implementation Steps

### Step 1: Create `docs/milestone-testing/M1_Live_Test.md`
- Prerequisites checklist (Twilio, ngrok, Redis, DGX Spark, meeting)
- Step-by-step run instructions
- Redis verification steps
- Pass/fail criteria
- Troubleshooting guide

### Step 2: Update `.env.example`
Add:
- `STT_PROVIDER=whisper-remote`
- `WHISPER_API_URL=http://spark-b0f2.local/kutana-stt/v1`
- `WHISPER_MODEL_SIZE=small`
- `AUDIO_SERVICE_PUBLIC_URL=`

### Step 3: Add `audio_service_public_url` to `AudioServiceSettings`
In `services/audio-service/src/audio_service/main.py`.

### Step 4: Create `scripts/dial_test.py`
Standalone script that:
1. Loads settings from env
2. Creates MeetingDialer with Twilio credentials
3. Calls `dialer.dial(dial_in_number, meeting_code, stream_url)`
4. Waits for user to press Enter
5. Reads events from Redis Stream `kutana:events`
6. Prints transcript segments and pass/fail summary

### Step 5: Update `TASKLIST.md`
- Check off M1 milestone
- Add telephony evaluation items

## Key Files

| Component | File | Import |
|-----------|------|--------|
| MeetingDialer | `audio_service/meeting_dialer.py` | `audio_service.meeting_dialer.MeetingDialer` |
| AudioPipeline | `audio_service/audio_pipeline.py` | `audio_service.audio_pipeline.AudioPipeline` |
| EventPublisher | `audio_service/event_publisher.py` | `audio_service.event_publisher.EventPublisher` |
| Events | `kutana_core/events/definitions.py` | `MeetingStarted`, `MeetingEnded`, `TranscriptSegmentFinal` |
| Redis Stream | key: `kutana:events` | max 10,000 entries |
