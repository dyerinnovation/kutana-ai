# Phase A: Portable Message Bus Abstraction

## Objective
Implement a portable MessageBus abstraction layer for Convene AI. Services currently use Redis Streams directly; this phase decouples them behind an ABC so the bus can be swapped (Redis → AWS SNS/SQS → GCP Pub/Sub → NATS) without touching service code.

## Files to Create

### convene-core (ABC layer)
- `packages/convene-core/src/convene_core/messaging/__init__.py`
- `packages/convene-core/src/convene_core/messaging/types.py`
- `packages/convene-core/src/convene_core/messaging/abc.py`

### convene-providers (Redis implementation)
- `packages/convene-providers/src/convene_providers/messaging/__init__.py`
- `packages/convene-providers/src/convene_providers/messaging/redis_streams.py`

### Tests
- `packages/convene-core/tests/test_messaging.py`
- `packages/convene-providers/tests/test_redis_message_bus.py`

## Files to Modify
- `packages/convene-providers/src/convene_providers/testing.py` — add MockMessageBus
- `packages/convene-providers/src/convene_providers/registry.py` — add ProviderType.MESSAGE_BUS, register "redis"
- `packages/convene-providers/pyproject.toml` — add `redis[asyncio]>=5.0` core dependency

## Design Decisions

### Message model (Pydantic BaseModel)
```python
class Message(BaseModel):
    id: str                      # UUID str, auto-generated
    topic: str                   # Redis stream key / topic name
    payload: dict[str, Any]      # JSON-serializable data
    metadata: dict[str, str]     # routing metadata (region, correlation-id, etc.)
    timestamp: datetime          # UTC creation time
    source: str                  # publishing service name
```

### Subscription (dataclass)
```python
@dataclass
class Subscription:
    topic: str
    handler: MessageHandler      # Callable[[Message], Awaitable[None]]
    group: str | None = None     # consumer group for load balancing
    subscription_id: str         # auto-generated UUID
```

### MessageBus ABC methods
- `publish(topic, payload, metadata, source) -> str` (message ID)
- `subscribe(topic, handler, group) -> Subscription`
- `unsubscribe(subscription) -> None`
- `ack(subscription, message_id) -> None`
- `close() -> None`

### RedisStreamsMessageBus
- `aioredis` (redis[asyncio]) for async operations
- `XADD` → publish
- `XREADGROUP` → group subscriptions (load-balanced)
- `XREAD` → fan-out subscriptions (no group)
- `XGROUP CREATE ... MKSTREAM` → auto-create group on subscribe
- `XACK` → acknowledgment
- Background `asyncio.Task` per subscription for polling
- `fnmatch` patterns (e.g., `"meeting.*.insights"`) via Redis SCAN

### Registry integration
- Add `ProviderType.MESSAGE_BUS = "message_bus"` to StrEnum
- Register `RedisStreamsMessageBus` as `"redis"` in `_build_default_registry()`

### CONVENE_MESSAGE_BUS env var
- Helper `create_message_bus_from_env()` reads `CONVENE_MESSAGE_BUS` (default: `"redis"`) and `REDIS_URL` to instantiate the correct provider from the registry.

## Recovery Notes
- Project root: `/Users/jonathandyer/Documents/Dyer_Innovation/dev/convene-ai`
- Python 3.12+, mypy strict, ruff formatting, pytest asyncio_mode=auto
- All providers follow the ABC-in-core / impl-in-providers pattern
- Tests use AsyncMock for Redis client; no actual Redis required for unit tests
- Commit message: `feat: add portable MessageBus abstraction with Redis Streams provider`
