# Security Rules

- Validate all inputs at system boundaries (user-supplied data, external API responses). Trust internal service data.
- All API endpoints require JWT authentication. Use `get_current_user` dependency injection — never skip it.
- Check JWT scope/tier before granting access to premium features (`plan_tier` field on user).
- Apply rate limiting to all public-facing endpoints (use FastAPI middleware).
- Never hardcode secrets — all credentials live in environment variables.
- Never log secrets, tokens, or PII. Use structured logging with redaction for sensitive fields.
- Validate agent API keys on every WebSocket connection to the agent-gateway. See `internal-docs/architecture/patterns/auth-and-api-keys.md`.
