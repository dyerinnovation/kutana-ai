# Plan: Create All 4 Service Packages Under `services/`

## Objective
Create the complete service layer for the Convene AI monorepo. Four independent FastAPI services that consume the shared `convene-core`, `convene-providers`, and `convene-memory` packages.

## Services to Create

### 1. `services/api-server/`
- FastAPI REST + WebSocket API for dashboard and integrations
- Routes: health, meetings (CRUD), tasks (CRUD), agents (CRUD)
- Dependencies: Settings, DB session, Redis injection
- CORS middleware

### 2. `services/audio-service/`
- Twilio Media Streams handler and audio pipeline
- WebSocket endpoint for bidirectional audio
- Audio transcoding (mulaw 8kHz -> PCM16 16kHz)
- Meeting dialer with DTMF support

### 3. `services/task-engine/`
- LLM-powered task extraction from transcript segments
- Task deduplication against existing tasks
- Redis Streams consumer for transcript events

### 4. `services/worker/`
- Background worker service
- Slack webhook notifications
- Calendar sync placeholder
- Redis pub/sub notification service

## Files to Create (per service)

### api-server (11 files)
1. `services/api-server/pyproject.toml`
2. `services/api-server/src/api_server/__init__.py`
3. `services/api-server/src/api_server/main.py`
4. `services/api-server/src/api_server/routes/__init__.py`
5. `services/api-server/src/api_server/routes/health.py`
6. `services/api-server/src/api_server/routes/meetings.py`
7. `services/api-server/src/api_server/routes/tasks.py`
8. `services/api-server/src/api_server/routes/agents.py`
9. `services/api-server/src/api_server/deps.py`
10. `services/api-server/src/api_server/middleware.py`
11. `services/api-server/tests/__init__.py`

### audio-service (7 files)
1. `services/audio-service/pyproject.toml`
2. `services/audio-service/src/audio_service/__init__.py`
3. `services/audio-service/src/audio_service/main.py`
4. `services/audio-service/src/audio_service/twilio_handler.py`
5. `services/audio-service/src/audio_service/audio_pipeline.py`
6. `services/audio-service/src/audio_service/meeting_dialer.py`
7. `services/audio-service/tests/__init__.py`

### task-engine (6 files)
1. `services/task-engine/pyproject.toml`
2. `services/task-engine/src/task_engine/__init__.py`
3. `services/task-engine/src/task_engine/main.py`
4. `services/task-engine/src/task_engine/extractor.py`
5. `services/task-engine/src/task_engine/deduplicator.py`
6. `services/task-engine/tests/__init__.py`

### worker (8 files)
1. `services/worker/pyproject.toml`
2. `services/worker/src/worker/__init__.py`
3. `services/worker/src/worker/main.py`
4. `services/worker/src/worker/slack_bot.py`
5. `services/worker/src/worker/calendar_sync.py`
6. `services/worker/src/worker/notifications.py`
7. `services/worker/tests/__init__.py`

## Conventions
- Python 3.12+ with `from __future__ import annotations` in every .py file
- Strict type hints on all functions
- Google-style docstrings
- 100 char line length
- async def for all I/O operations
- Pydantic v2 for API models and settings
- FastAPI dependency injection pattern
- Each service has a working `/health` endpoint
