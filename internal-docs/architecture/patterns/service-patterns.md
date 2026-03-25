# Service Layer Patterns

## Service Structure

Each service under `services/` follows this layout:

```
services/<service-name>/
  pyproject.toml              # Dependencies, hatchling build backend
  src/<service_name>/
    __init__.py               # Docstring + from __future__ import annotations
    main.py                   # FastAPI app with lifespan and /health endpoint
    ...                       # Service-specific modules
  tests/
    __init__.py
```

## Common Patterns

### Health Endpoint
Every service exposes `GET /health` returning `{"status": "healthy", "service": "<name>"}` with a `HealthResponse` Pydantic model.

### Lifespan Context Manager
All services use FastAPI's `lifespan` async context manager for startup/shutdown:

```python
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("service starting up")
    yield
    logger.info("service shutting down")
```

### Settings via pydantic-settings
Services that need configuration use `pydantic_settings.BaseSettings` with `SettingsConfigDict(env_file=".env", extra="ignore")`. The `get_settings()` function uses `@lru_cache(maxsize=1)` for singleton behavior.

### Dependency Injection
The api-server uses FastAPI `Depends()` with `Annotated` type hints:
- `get_settings()` -> `Settings`
- `get_db_session()` -> `AsyncSession` (async generator with commit/rollback)
- `get_redis()` -> `Redis` (async generator with cleanup)

### Route Organization
The api-server groups routes into separate router modules under `routes/`:
- Each router uses `APIRouter(prefix="/resource", tags=["resource"])`
- Routers are included in main.py with an API version prefix: `app.include_router(router, prefix="/api/v1")`
- Request/response schemas are Pydantic models defined alongside the route file

## Service-Specific Notes

### audio-service
- Mulaw 8kHz to PCM16 16kHz transcoding uses a pure-Python lookup table (no `audioop` dependency)
- TwilioHandler processes Twilio Media Stream protocol events (connected/start/media/stop)
- MeetingDialer builds TwiML with DTMF digits and Media Stream URL

### task-engine
- Runs a background extraction consumer as an `asyncio.Task` during lifespan
- TaskExtractor delegates to `LLMProvider.extract_tasks()` from convene-core
- TaskDeduplicator uses `SequenceMatcher` with 0.85 similarity threshold

### worker
- SlackBot posts to Slack incoming webhooks using `httpx`
- NotificationService wraps Redis async pub/sub for event distribution
- CalendarSync is a placeholder for calendar API integration
