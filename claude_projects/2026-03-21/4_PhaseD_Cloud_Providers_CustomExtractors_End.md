# Phase D: Cloud Message Bus Providers & Custom Extractor SDK — End

## Work Completed

- **AWS SNS/SQS message bus provider** (`convene_providers/messaging/aws_sns_sqs.py`)
  - `SQSMessageBus` using aioboto3 with lazy import guard
  - publish/subscribe/ack/unsubscribe/close fully implemented
  - Consumer groups via separate SQS queues per (topic, group)
  - Fan-out subscriptions via unique per-subscriber SQS queues
  - SNS topic auto-creation with ARN caching
  - SNS→SQS subscription wiring with policy
  - Topic pattern matching via SNS topic list + fnmatch

- **GCP Pub/Sub message bus provider** (`convene_providers/messaging/gcp_pubsub.py`)
  - `PubSubMessageBus` using google-cloud-pubsub async client
  - Topic/subscription auto-creation with `AlreadyExists` handling
  - Consumer groups via separate subscriptions per (topic, group)
  - Streaming pull model with auto-ack
  - Resource path caching for topics and subscriptions
  - Requires `GCP_PROJECT_ID` env var — raises `ValueError` if absent

- **NATS JetStream message bus provider** (`convene_providers/messaging/nats_jetstream.py`)
  - `NATSMessageBus` using nats-py with JetStream
  - JetStream stream auto-creation (CONVENE stream)
  - Consumer groups via durable push consumers with `queue=` parameter
  - Fan-out via ephemeral push consumers
  - Auto-ack in callback; `ack()` is intentional no-op
  - Native subject wildcard support (`*`, `>`)
  - `contextlib.suppress` for clean shutdown

- **Provider registry updated** (`convene_providers/registry.py`)
  - Registered: `aws-sns-sqs`, `gcp-pubsub`, `nats` message bus providers

- **`create_message_bus_from_env()` updated** (`redis_streams.py`)
  - Supports all four backends: redis, aws-sns-sqs, gcp-pubsub, nats
  - Reads provider-specific env vars for each backend
  - Clear error message listing all supported backends

- **`pyproject.toml` updated** with optional deps:
  - `[aws]` → aioboto3>=13.0
  - `[gcp]` → google-cloud-pubsub>=2.0
  - `[nats]` → nats-py>=2.7

- **ExtractorLoader** (`convene_core/extraction/loader.py`)
  - Discovery from installed package entry points (`convene.extractors` group)
  - Loading from local Python files (module isolation via importlib)
  - Hot-loading via `register_or_replace()`
  - Full ABC validation before registration
  - `load_from_module()` for dotted path imports
  - `create()` factory with kwarg forwarding

- **Extractor SDK** (`convene_core/extraction/sdk.py`)
  - `SimpleExtractor` base class with ClassVar name/entity_types
  - `@extractor` decorator for function-based extractors
  - Factory functions: `make_task`, `make_decision`, `make_question`, `make_key_point`, `make_blocker`, `make_follow_up`, `make_entity_mention`
  - `timed_result()` helper for accurate processing time

- **Example compliance extractor** (`examples/custom-extractors/compliance_extractor.py`)
  - `ComplianceExtractor` (SimpleExtractor subclass) with regex keyword detection
  - `regex_compliance_extractor` (decorator-based variant)
  - `register_all()` convenience function
  - Well-documented with usage examples

- **Deployment templates** (`deploy/`)
  - `deploy/aws/docker-compose.yml` — ECS/Fargate with LocalStack for dev
  - `deploy/gcp/docker-compose.yml` — Cloud Run with Pub/Sub emulator for dev
  - `deploy/self-hosted/docker-compose.yml` — NATS + Postgres + Redis self-contained
  - `deploy/README.md` — describes all three options with env vars and quick start

- **Tests**
  - `test_aws_sns_sqs.py` — 22 tests: import guard, naming, publish, subscribe, ack, close, create_from_env
  - `test_gcp_pubsub.py` — 20 tests: import guard, naming, publish, subscribe, ack, close, create_from_env
  - `test_nats_jetstream.py` — 26 tests: import guard, naming, publish, subscribe, handler dispatch, ack, unsubscribe, close, registry
  - `test_extractor_sdk.py` — 40+ tests: validate_extractor, SimpleExtractor, decorator, all 7 factories, loader registration/creation/file loading/entry points/introspection, compliance extractor smoke test

- **Ruff** — all new files pass `ruff check` with zero errors

## Work Remaining

- None for this phase. All items in the plan are implemented.

## Lessons Learned

- **SIM105**: Use `contextlib.suppress(Exception)` instead of `try/except: pass` — ruff enforces this; add `import contextlib` to the top of files that need exception-swallowing in cleanup paths.
- **RUF012**: Mutable class attributes (like `list[str] = []`) on classes need `ClassVar` annotation to avoid ruff RUF012 complaints. Use `name: ClassVar[str] = ""` and `entity_types: ClassVar[list[str]] = []` in SimpleExtractor and its subclasses.
- **TC001**: If an import is only used for a type check (`_: Extractor = ...`), move it to `TYPE_CHECKING` block. If it's needed at runtime (isinstance checks, etc.), keep it as a regular import.
- **Optional cloud libraries**: Use `try/except ImportError` at module level with a `_AVAILABLE` flag, then `_require_xyz()` at init time with a helpful install message. This avoids errors at import time for users who don't have the optional dep.
- **Test unpacking**: When unpacking a fixture tuple, use `_` prefixes for truly unused variables (RUF059). Be surgical — only rename what's unused in each specific test method.
