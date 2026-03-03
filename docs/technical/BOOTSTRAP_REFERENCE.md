# Convene AI — Bootstrap Reference

> This file preserves the original bootstrap prompt used to scaffold the project.
> It is kept for historical reference only. See CLAUDE.md at the repo root for
> current project conventions.

---

## Original Bootstrap Instructions

When pasting this into Claude Code, ask it to:

### Step 1: Create the monorepo structure

Create the Convene AI monorepo with the following structure. Use uv workspaces.
Initialize all packages with pyproject.toml files and proper dependency declarations.
Set up docker-compose.yml with PostgreSQL 16 (pgvector) and Redis 7.
Create the CLAUDE.md file at the root from the spec above.

### Step 2: Implement core domain models

Implement all Pydantic v2 models in packages/convene-core/src/convene_core/models/.
Then implement the corresponding SQLAlchemy 2.0 ORM models.
Create the initial Alembic migration.

### Step 3: Implement provider interfaces and first providers

Implement the abstract base classes in packages/convene-core/src/convene_core/interfaces/.
Then implement AssemblyAI STT, Anthropic LLM, and the provider registry.

### Step 4: Implement Twilio phone integration

Implement MeetingDialer, TwilioHandler, and AudioPipeline in the audio service.

### Step 5: Implement task extraction and memory

Implement the task engine (Redis Streams consumer, LLM extraction, deduplication)
and the four-layer memory system.

### Step 6: Build API and minimal dashboard

Implement FastAPI routes and a minimal React dashboard.

---

## Provider Configuration Reference

### AssemblyAI Streaming STT
- WebSocket URL: wss://api.assemblyai.com/v2/realtime/ws
- Auth: token parameter in URL
- Audio format: PCM16, 16kHz, mono
- Features: speaker_labels=true, word_boost (optional)
- Events: SessionBegins, PartialTranscript, FinalTranscript, SessionTerminated

### Twilio Media Streams
- Outbound call: client.calls.create(to=dial_in, from_=twilio_number, twiml=stream_twiml)
- TwiML: `<Response><Connect><Stream url="wss://your-server/audio-stream" /></Connect></Response>`
- Audio format: mulaw, 8kHz, mono, base64-encoded in JSON messages
- Events: connected, start, media, stop
- For DTMF: use `<Play digits="w{meeting_code}#" />` in TwiML (w = 0.5s wait)

### Anthropic Claude (Task Extraction)
- Model: claude-sonnet-4-20250514 (or claude-haiku for classification)
- Use tool_use with Pydantic schema for structured extraction
- System prompt should include: meeting context, participant names, open tasks
- Temperature: 0.0 for extraction (deterministic)
- Max tokens: 4096 for extraction responses
