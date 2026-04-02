# Phase A: Portable Message Bus Abstraction — End

## Work Completed

- **kutana-core/messaging/types.py** — `Message` (Pydantic BaseModel), `MessageHandler` (type alias), `Subscription` (dataclass with auto-generated `subscription_id`)
- **kutana-core/messaging/abc.py** — `MessageBus` ABC with `publish`, `subscribe`, `unsubscribe`, `ack`, `close`
- **kutana-core/messaging/__init__.py** — exports `Message`, `MessageBus`, `MessageHandler`, `Subscription`
- **kutana-providers/messaging/redis_streams.py** — `RedisStreamsMessageBus` using `redis.asyncio`: XADD/XREADGROUP/XREAD/XACK/XGROUP CREATE, per-subscription background `asyncio.Task`, fnmatch pattern subscriptions via Redis SCAN, `create_message_bus_from_env()` helper
- **kutana-providers/messaging/__init__.py** — exports `RedisStreamsMessageBus`, `create_message_bus_from_env`
- **kutana-providers/testing.py** — Added `MockMessageBus`: in-process dispatch, fnmatch pattern matching, records all published messages in `.published`
- **kutana-providers/registry.py** — Added `ProviderType.MESSAGE_BUS = "message_bus"`, registered `"redis" → RedisStreamsMessageBus`
- **kutana-providers/pyproject.toml** — Added `redis[asyncio]>=5.0` as core dependency
- **kutana-core/tests/test_messaging.py** — 26 tests covering Message model, Subscription, MessageBus ABC, MockMessageBus
- **kutana-providers/tests/test_redis_message_bus.py** — 35 tests covering publish/subscribe/unsubscribe/ack/close, entry serialization roundtrip, registry integration, env var config
- All files pass `ruff check` and `mypy packages/kutana-core/` (the CI target)
- Committed as `feat: add portable MessageBus abstraction with Redis Streams provider`

## Work Remaining

- Push to remote (not done — user to push when ready)
- Phase B: Wire services to use `MessageBus` instead of direct Redis Streams calls (audio-service, task-engine, agent-gateway)
- Add `aws-sns-sqs`, `gcp-pubsub`, `nats` backend implementations as needed

## Lessons Learned

- `asyncio_mode = "auto"` in pytest config means NO `@pytest.mark.asyncio` decorators needed — test methods written as `async def` are picked up automatically
- Ruff UP040 enforces PEP 695 `type` keyword (`type Foo = ...`) over `TypeAlias` annotation for Python 3.12+ — use `type MessageHandler = Callable[...]` not `MessageHandler: TypeAlias = ...`
- `BLE001` is not enabled in this project's ruff config — `# noqa: BLE001` directives are flagged as unused (RUF100). Use bare `except Exception:` or `contextlib.suppress(Exception)` instead
- Ruff SIM105: prefer `with contextlib.suppress(Exception):` over `try/except: pass`
- Pre-existing mypy errors in kutana-providers (import-not-found for cross-package) are infrastructure-level — CI only runs `mypy packages/kutana-core/`, not the full project
- The `XGROUP CREATE` call should happen in `subscribe()` for exact topics (not inside the background `_consume()` task) so tests can synchronously assert it was called
- Pattern subscriptions (`meeting.*.events`) defer group creation to `_consume()` since streams aren't known at subscribe time
- `XREAD` with `$` as initial ID means "only messages published after this subscribe call" — correct semantics for a live messaging bus
