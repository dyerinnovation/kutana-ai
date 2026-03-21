# Phase A: Portable Message Bus Abstraction — End

## Work Completed

- **convene-core/messaging/types.py** — `Message` (Pydantic BaseModel), `MessageHandler` (type alias), `Subscription` (dataclass with auto-generated `subscription_id`)
- **convene-core/messaging/abc.py** — `MessageBus` ABC with `publish`, `subscribe`, `unsubscribe`, `ack`, `close`
- **convene-core/messaging/__init__.py** — exports `Message`, `MessageBus`, `MessageHandler`, `Subscription`
- **convene-providers/messaging/redis_streams.py** — `RedisStreamsMessageBus` using `redis.asyncio`: XADD/XREADGROUP/XREAD/XACK/XGROUP CREATE, per-subscription background `asyncio.Task`, fnmatch pattern subscriptions via Redis SCAN, `create_message_bus_from_env()` helper
- **convene-providers/messaging/__init__.py** — exports `RedisStreamsMessageBus`, `create_message_bus_from_env`
- **convene-providers/testing.py** — Added `MockMessageBus`: in-process dispatch, fnmatch pattern matching, records all published messages in `.published`
- **convene-providers/registry.py** — Added `ProviderType.MESSAGE_BUS = "message_bus"`, registered `"redis" → RedisStreamsMessageBus`
- **convene-providers/pyproject.toml** — Added `redis[asyncio]>=5.0` as core dependency
- **convene-core/tests/test_messaging.py** — 26 tests covering Message model, Subscription, MessageBus ABC, MockMessageBus
- **convene-providers/tests/test_redis_message_bus.py** — 35 tests covering publish/subscribe/unsubscribe/ack/close, entry serialization roundtrip, registry integration, env var config
- All files pass `ruff check` and `mypy packages/convene-core/` (the CI target)
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
- Pre-existing mypy errors in convene-providers (import-not-found for cross-package) are infrastructure-level — CI only runs `mypy packages/convene-core/`, not the full project
- The `XGROUP CREATE` call should happen in `subscribe()` for exact topics (not inside the background `_consume()` task) so tests can synchronously assert it was called
- Pattern subscriptions (`meeting.*.events`) defer group creation to `_consume()` since streams aren't known at subscribe time
- `XREAD` with `$` as initial ID means "only messages published after this subscribe call" — correct semantics for a live messaging bus
