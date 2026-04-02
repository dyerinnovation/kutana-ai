# Plan: Complete Phase 1B + Phase 1C (Twilio Audio Pipeline)

## Objective
Complete the remaining Phase 1B item (provider registry integration tests) and implement Phase 1C features: Redis Streams event publishing, meeting end detection, graceful cleanup, audio buffering on STT failure, and end-to-end tests.

## Work Items

### 1. Provider Registry Integration Tests
- **Create:** `packages/kutana-providers/tests/test_registry_integration.py`
- 8 tests covering full lifecycle, isolation, kwargs pass-through, error cases, default registry smoke test

### 2. Redis Streams Event Publisher
- **Create:** `services/audio-service/src/audio_service/event_publisher.py`
- **Modify:** `audio_pipeline.py` — add optional `EventPublisher` + `meeting_id`
- **Modify:** `main.py` — add `AudioServiceSettings`, create publisher in lifespan

### 3. Meeting End Detection
- **Modify:** `twilio_handler.py` — add `meeting_id`, 60s silence timeout

### 4. Graceful Cleanup & Lifecycle Events
- **Modify:** `audio_pipeline.py` — publish MeetingStarted/MeetingEnded events

### 5. Audio Buffering on STT Failure
- **Modify:** `audio_pipeline.py` — retry logic, buffer with 5MB cap

### 6. End-to-End Tests
- **Create:** `services/audio-service/tests/__init__.py`
- **Create:** `services/audio-service/tests/test_audio_pipeline.py`

## Verification
- `uv run ruff check .`
- `uv run mypy --strict .`
- `uv run pytest -x -v`
- All 48 existing tests + new tests pass
- TASKLIST.md updated
