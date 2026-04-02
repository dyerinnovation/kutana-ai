# Phase D: Cloud Message Bus Providers & Custom Extractor SDK

## Objective
Implement Phase D of Kutana AI:
- Cloud message bus providers: AWS SNS/SQS, GCP Pub/Sub, NATS JetStream
- Custom extractor SDK (loader + decorator/base class)
- Example compliance extractor
- Deployment config templates (AWS ECS, GCP Cloud Run, self-hosted)
- Tests for all new code

## Files to Create

### Cloud Message Bus Providers
- `packages/kutana-providers/src/kutana_providers/messaging/aws_sns_sqs.py` — SQSMessageBus (aioboto3)
- `packages/kutana-providers/src/kutana_providers/messaging/gcp_pubsub.py` — PubSubMessageBus (google-cloud-pubsub async)
- `packages/kutana-providers/src/kutana_providers/messaging/nats_jetstream.py` — NATSMessageBus (nats-py JetStream)

### Registry Updates
- `packages/kutana-providers/src/kutana_providers/registry.py` — register aws-sns-sqs, gcp-pubsub, nats
- `packages/kutana-providers/src/kutana_providers/messaging/redis_streams.py` — update create_message_bus_from_env() for all backends
- `packages/kutana-providers/pyproject.toml` — add optional deps: aws, gcp, nats

### Custom Extractor SDK (in kutana-core)
- `packages/kutana-core/src/kutana_core/extraction/loader.py` — ExtractorLoader class
- `packages/kutana-core/src/kutana_core/extraction/sdk.py` — @extractor decorator, SimpleExtractor

### Examples
- `examples/custom-extractors/compliance_extractor.py`

### Deployment Templates
- `deploy/aws/docker-compose.yml`
- `deploy/gcp/docker-compose.yml`
- `deploy/self-hosted/docker-compose.yml`
- `deploy/README.md`

### Tests
- `packages/kutana-providers/tests/test_aws_sns_sqs.py`
- `packages/kutana-providers/tests/test_gcp_pubsub.py`
- `packages/kutana-providers/tests/test_nats_jetstream.py`
- `packages/kutana-core/tests/test_extractor_sdk.py`

## Key Conventions
- Python 3.12+, strict mypy types, Pydantic v2, async/await, ruff
- ABC pattern: all providers implement MessageBus ABC
- Optional imports: cloud libs are optional deps — `try/except ImportError` with helpful error messages
- Mock-based tests (no real cloud credentials needed)
- Consumer groups: separate SQS queues / Pub/Sub subscriptions / JetStream durable consumers per group
- `create_message_bus_from_env()` remains the factory entry point (updated to support all 4 backends)
- Use `from __future__ import annotations` at top of every file
- Docstrings on all public methods (Google style)

## Implementation Order
1. Plan doc (this file)
2. aws_sns_sqs.py
3. gcp_pubsub.py
4. nats_jetstream.py
5. registry.py + pyproject.toml updates
6. loader.py + sdk.py
7. compliance_extractor.py example
8. deploy/ templates
9. tests
10. ruff check + fix
11. End doc, commit, push
