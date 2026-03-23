"""JWT authentication for the MCP server."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import jwt

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MCPIdentity:
    """Validated identity from an MCP JWT.

    Attributes:
        user_id: UUID of the authenticated user.
        agent_config_id: UUID of the agent configuration.
        scopes: Granted scopes for this token.
    """

    user_id: UUID
    agent_config_id: UUID
    name: str = "Agent"
    scopes: list[str] = field(default_factory=list)


class MCPAuthError(Exception):
    """Raised when MCP authentication fails."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def validate_mcp_token(
    token: str,
    secret: str,
    algorithm: str = "HS256",
) -> MCPIdentity:
    """Validate an MCP JWT token and extract the identity.

    Expected JWT claims:
        sub: user_id (UUID string)
        agent_config_id: agent config UUID string
        type: must be "mcp"
        scopes: list of scope strings

    Args:
        token: The JWT token string.
        secret: The secret key for validation.
        algorithm: JWT algorithm (default HS256).

    Returns:
        MCPIdentity with validated claims.

    Raises:
        MCPAuthError: If the token is invalid or missing required claims.
    """
    try:
        payload: dict[str, Any] = jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
        )
    except jwt.ExpiredSignatureError as e:
        raise MCPAuthError("token_expired", "MCP token has expired") from e
    except jwt.InvalidTokenError as e:
        raise MCPAuthError("invalid_token", f"Invalid MCP token: {e}") from e

    # Verify token type
    token_type = payload.get("type")
    if token_type != "mcp":
        raise MCPAuthError(
            "invalid_token_type",
            f"Expected token type 'mcp', got '{token_type}'",
        )

    # Extract user_id from sub
    sub = payload.get("sub")
    if not sub:
        raise MCPAuthError("missing_claim", "Token missing 'sub' claim")

    try:
        user_id = UUID(sub)
    except ValueError as e:
        raise MCPAuthError("invalid_claim", "'sub' must be a valid UUID") from e

    # Extract agent_config_id
    agent_config_id_str = payload.get("agent_config_id")
    if not agent_config_id_str:
        raise MCPAuthError("missing_claim", "Token missing 'agent_config_id' claim")

    try:
        agent_config_id = UUID(agent_config_id_str)
    except ValueError as e:
        raise MCPAuthError(
            "invalid_claim", "'agent_config_id' must be a valid UUID"
        ) from e

    # Extract scopes
    scopes = payload.get("scopes", [])
    if not isinstance(scopes, list):
        raise MCPAuthError("invalid_claim", "'scopes' must be a list")

    # Extract optional agent name (falls back to "Agent" if not present)
    name: str = payload.get("name", "Agent")

    return MCPIdentity(
        user_id=user_id,
        agent_config_id=agent_config_id,
        name=name,
        scopes=scopes,
    )
