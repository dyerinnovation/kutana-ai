# Architecture Rules

- Every external service (STT, TTS, LLM, phone, message bus) must have an abstract base class. Implementations are swappable — business logic never imports a provider directly.
- Services communicate via the MessageBus (Redis Streams by default). Never make direct service-to-service calls.
- AI agents connect via the agent-gateway WebSocket. Never use platform SDKs (Zoom, Teams, etc.).
- Pydantic models own the API shape. SQLAlchemy models own persistence. Keep them separate.
- The provider registry resolves implementations at startup from config (`CONVENE_MESSAGE_BUS`, `STT_PROVIDER`, etc.). See `internal-docs/architecture/patterns/provider-patterns.md`.
- If STT/LLM fails, buffer and retry. Never drop meeting data.
- Every service must expose a `GET /health` endpoint returning `{"status": "healthy", "service": "<name>"}`. K8s readiness/liveness probes depend on this. No exceptions.
