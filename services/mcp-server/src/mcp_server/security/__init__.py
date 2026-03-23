"""Security infrastructure for Convene AI MCP server.

Modules:
    scopes: JWT scope definitions and per-tool enforcement.
    sanitization: Input validation and sanitization for all tool parameters.
    rate_limit: Per-agent, per-tool Redis sliding-window rate limiting.
    audit: Structured JSON audit logging for auth events and tool calls.
"""
