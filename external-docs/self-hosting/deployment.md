# Convene AI — Deployment Options

Convene AI supports three production deployment configurations.  All share
the same application code; only the message bus backend changes.

## Option 1: AWS (SNS + SQS)

**File:** `deploy/aws/docker-compose.yml`

Uses AWS SNS for fanout and SQS for durable per-consumer delivery.

| Component | AWS service |
|-----------|-------------|
| Message bus | Amazon SNS + SQS |
| Database | Amazon RDS (PostgreSQL 16 + pgvector) |
| Cache | Amazon ElastiCache (Redis) |
| Containers | Amazon ECS / Fargate |
| Registry | Amazon ECR |

### Quick start (local with LocalStack)

```bash
cd deploy/aws
AWS_REGION=us-east-1 docker compose --profile localdev up -d
```

### Environment variables

```bash
CONVENE_MESSAGE_BUS=aws-sns-sqs
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=...       # or use IAM role on ECS task
AWS_SECRET_ACCESS_KEY=...
SNS_TOPIC_PREFIX=convene-prod-
DATABASE_URL=postgresql+asyncpg://...
ANTHROPIC_API_KEY=...
DEEPGRAM_API_KEY=...
AGENT_GATEWAY_JWT_SECRET=...
```

---

## Option 2: GCP (Pub/Sub)

**File:** `deploy/gcp/docker-compose.yml`

Uses Google Cloud Pub/Sub for fanout and per-consumer pull subscriptions.

| Component | GCP service |
|-----------|-------------|
| Message bus | Google Cloud Pub/Sub |
| Database | Cloud SQL (PostgreSQL 16 + pgvector) |
| Cache | Memorystore (Redis) |
| Containers | Cloud Run or GKE |
| Registry | Artifact Registry |

### Quick start (local with Pub/Sub emulator)

```bash
cd deploy/gcp
GCP_PROJECT_ID=my-project docker compose --profile localdev up -d
```

### Environment variables

```bash
CONVENE_MESSAGE_BUS=gcp-pubsub
GCP_PROJECT_ID=my-gcp-project
GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json   # or use Workload Identity
PUBSUB_TOPIC_PREFIX=convene-prod-
DATABASE_URL=postgresql+asyncpg://...
ANTHROPIC_API_KEY=...
DEEPGRAM_API_KEY=...
AGENT_GATEWAY_JWT_SECRET=...
```

---

## Option 3: Self-Hosted (NATS JetStream)

**File:** `deploy/self-hosted/docker-compose.yml`

Runs the full stack locally or on your own infrastructure using NATS
JetStream.  All infrastructure (NATS, PostgreSQL, Redis) is included.
Ideal for on-premises, air-gapped, or data-sovereignty deployments.

| Component | Technology |
|-----------|-----------|
| Message bus | NATS JetStream |
| Database | PostgreSQL 16 + pgvector |
| Cache | Redis 7 |
| Containers | Docker Compose / K8s |

### Quick start

```bash
cd deploy/self-hosted

# Copy and edit environment
cp ../../.env.example .env
# Edit .env: set ANTHROPIC_API_KEY, DEEPGRAM_API_KEY, AGENT_GATEWAY_JWT_SECRET

docker compose up -d
```

### Scale workers

```bash
docker compose up -d --scale task-engine=4
```

### Environment variables

```bash
CONVENE_MESSAGE_BUS=nats
NATS_URL=nats://localhost:4222
NATS_STREAM_NAME=CONVENE
DATABASE_URL=postgresql+asyncpg://convene:convene@localhost:5432/convene
REDIS_URL=redis://localhost:6379/0
ANTHROPIC_API_KEY=...
DEEPGRAM_API_KEY=...
AGENT_GATEWAY_JWT_SECRET=...
POSTGRES_PASSWORD=...
```

---

## Switching backends

The message bus backend is controlled by a single environment variable:

```bash
CONVENE_MESSAGE_BUS=redis         # default (development)
CONVENE_MESSAGE_BUS=aws-sns-sqs   # AWS
CONVENE_MESSAGE_BUS=gcp-pubsub    # GCP
CONVENE_MESSAGE_BUS=nats          # self-hosted
```

No application code changes are needed when switching backends.

---

## Custom Extractor Deployment

To deploy custom extractors, install your extractor package alongside
the `task-engine` service and set:

```bash
CONVENE_CUSTOM_EXTRACTOR_PACKAGE=my_package.extractors
```

Or mount the extractor file and set:

```bash
CONVENE_CUSTOM_EXTRACTOR_FILE=/app/extractors/compliance_extractor.py
```

See `examples/custom-extractors/` for a reference implementation.
