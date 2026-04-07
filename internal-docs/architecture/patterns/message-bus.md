# MessageBus Patterns

## Location

- **ABC + types**: `packages/kutana-core/src/kutana_core/messaging/` (NOT under `interfaces/`)
- **Redis implementation**: `packages/kutana-providers/src/kutana_providers/messaging/redis_streams.py`
- **Mock for testing**: `packages/kutana-providers/src/kutana_providers/testing.MockMessageBus`
- **Registry key**: `ProviderType.MESSAGE_BUS` → `"redis"`
- **Env helper**: `create_message_bus_from_env()` in `kutana_providers.messaging`

## Usage in Services

```python
from kutana_core.messaging import MessageBus, Message
from kutana_providers.messaging import create_message_bus_from_env

# At startup
bus = create_message_bus_from_env()  # reads KUTANA_MESSAGE_BUS + REDIS_URL

# Publish
msg_id = await bus.publish(
    topic="transcript.segment.final",
    payload=segment.model_dump(mode="json"),
    source="audio-service",
)

# Subscribe (fan-out)
async def on_segment(msg: Message) -> None:
    segment = TranscriptSegment.model_validate(msg.payload)
    ...

sub = await bus.subscribe("transcript.segment.final", on_segment)

# Subscribe (consumer group — load balanced, at-least-once)
sub = await bus.subscribe("transcript.segment.final", on_segment, group="task-workers")
await bus.ack(sub, msg.id)  # call after processing

# Cleanup
await bus.unsubscribe(sub)
await bus.close()
```

## Testing Pattern

```python
from kutana_providers.testing import MockMessageBus

bus = MockMessageBus()
sub = await bus.subscribe("events", handler)
await bus.publish("events", {"type": "started"})
assert len(bus.published) == 1  # records all published messages
```

## Redis Stream Entry Format

Each `Message` is stored in the Redis stream with these fields:
- `message_id` — the Message UUID
- `topic` — the topic name
- `payload` — JSON-encoded dict
- `metadata` — JSON-encoded dict of str:str
- `timestamp` — ISO 8601 UTC datetime
- `source` — publishing service name

## Implementation Notes

- `XGROUP CREATE` for exact (non-pattern) subscriptions happens synchronously in `subscribe()` — testable with mock assertions
- Pattern subscriptions (`meeting.*.events`) use Redis `SCAN` to discover streams; group creation is deferred to `_consume()` when streams are found
- `XREAD` initial ID is `$` — subscribers only receive messages published AFTER they subscribe
- Background `asyncio.Task` per subscription; tasks are cancelled on `unsubscribe()` / `close()`
- `poll_block_ms=500` default; lower for tests to improve cancellation speed

## Ruff Notes for This Package

- `BLE001` (blind exception) is NOT enabled — do not add `# noqa: BLE001`
- Use `contextlib.suppress(Exception)` for try/except/pass patterns (SIM105)
- Python 3.12+ type aliases: use `type Foo = ...` syntax, not `TypeAlias` annotation (UP040)
