"""JWT authentication and API key management for the agent gateway."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentIdentity:
    """Validated identity of a connecting agent.

    Attributes:
        agent_config_id: UUID of the agent configuration.
        name: Human-readable agent name.
        capabilities: Capabilities the agent is allowed to request.
        source: Connection source identifier (e.g. "agent", "claude-code", "openclaw").
    """

    agent_config_id: UUID
    name: str
    capabilities: list[str]
    source: str = "agent"


class AuthError(Exception):
    """Raised when authentication fails."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def validate_token(
    token: str,
    secret: str,
    algorithm: str = "HS256",
) -> AgentIdentity:
    """Validate a JWT token and extract the agent identity.

    Expected JWT claims:
        sub: agent_config_id (UUID string)
        name: agent display name
        capabilities: list of capability strings

    Args:
        token: The JWT token string.
        secret: The secret key for validation.
        algorithm: JWT algorithm (default HS256).

    Returns:
        AgentIdentity with validated claims.

    Raises:
        AuthError: If the token is invalid or missing required claims.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
        )
    except jwt.ExpiredSignatureError as e:
        raise AuthError("token_expired", "Token has expired") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("invalid_token", f"Invalid token: {e}") from e

    # Extract required claims
    sub = payload.get("sub")
    if not sub:
        raise AuthError("missing_claim", "Token missing 'sub' claim")

    try:
        agent_config_id = UUID(sub)
    except ValueError as e:
        raise AuthError("invalid_claim", "'sub' must be a valid UUID") from e

    name = payload.get("name", "unnamed-agent")
    capabilities = payload.get("capabilities", ["listen", "transcribe"])
    source = payload.get("source", "agent")

    if not isinstance(capabilities, list):
        raise AuthError("invalid_claim", "'capabilities' must be a list")

    return AgentIdentity(
        agent_config_id=agent_config_id,
        name=name,
        capabilities=capabilities,
        source=source,
    )


def create_agent_token(
    agent_config_id: UUID,
    name: str,
    capabilities: list[str],
    secret: str,
    algorithm: str = "HS256",
    expire_seconds: int = 3600,
    source: str = "agent",
) -> str:
    """Create a JWT token for an agent.

    Args:
        agent_config_id: UUID of the agent configuration.
        name: Agent display name.
        capabilities: List of capability strings.
        secret: Secret key for signing.
        algorithm: JWT algorithm (default HS256).
        expire_seconds: Token expiry in seconds (default 1 hour).
        source: Connection source identifier (default "agent").

    Returns:
        Signed JWT token string.
    """
    import time

    now = int(time.time())
    payload = {
        "sub": str(agent_config_id),
        "name": name,
        "capabilities": capabilities,
        "source": source,
        "iat": now,
        "exp": now + expire_seconds,
    }
    return jwt.encode(payload, secret, algorithm=algorithm)


def create_audio_token(
    agent_config_id: UUID,
    meeting_id: UUID,
    secret: str,
    algorithm: str = "HS256",
    expire_seconds: int = 300,
    control_session_id: UUID | None = None,
) -> str:
    """Create a short-lived JWT for the /audio/connect sidecar endpoint.

    The audio token is intentionally narrow in scope: it identifies the agent,
    binds to a specific meeting, and expires quickly so it cannot be reused.

    Args:
        agent_config_id: UUID of the agent configuration (becomes ``sub``).
        meeting_id: UUID of the meeting the audio session is for.
        secret: Secret key for signing (same as the gateway JWT secret).
        algorithm: JWT algorithm (default HS256).
        expire_seconds: Token lifetime in seconds (default 5 minutes).
        control_session_id: Optional UUID of the linked control-plane session.

    Returns:
        Signed JWT token string for use with /audio/connect.
    """
    import time

    now = int(time.time())
    payload: dict[str, object] = {
        "sub": str(agent_config_id),
        "meeting_id": str(meeting_id),
        "token_type": "audio",
        "iat": now,
        "exp": now + expire_seconds,
    }
    if control_session_id is not None:
        payload["control_session_id"] = str(control_session_id)
    return jwt.encode(payload, secret, algorithm=algorithm)
