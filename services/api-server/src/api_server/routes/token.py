"""Token exchange endpoints: API key → gateway/MCP JWT, user → meeting JWT."""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_gateway.auth import create_agent_token
from api_server.auth import hash_api_key
from api_server.auth_deps import CurrentUser
from api_server.deps import Settings, get_db_session, get_settings
from convene_core.database.models import (
    AgentApiKeyORM,
    AgentConfigORM,
    ApiKeyAuditLogORM,
    MeetingORM,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/token", tags=["token"])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def _validate_api_key(
    raw_key: str,
    db: AsyncSession,
    request: Request | None = None,
) -> AgentApiKeyORM:
    """Validate an API key: check hash, revocation, and expiry.

    Also logs an audit record on successful use.

    Args:
        raw_key: The raw API key string.
        db: Database session.
        request: Optional FastAPI request for IP/user-agent logging.

    Returns:
        The validated AgentApiKeyORM record.

    Raises:
        HTTPException: 401 if the key is invalid, revoked, or expired.
    """
    key_hash = hash_api_key(raw_key)

    result = await db.execute(
        select(AgentApiKeyORM).where(
            AgentApiKeyORM.key_hash == key_hash,
            AgentApiKeyORM.revoked_at.is_(None),
        )
    )
    api_key = result.scalar_one_or_none()
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key",
        )

    # Check expiry
    if api_key.expires_at is not None and api_key.expires_at < datetime.now(tz=UTC):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    # Log audit event
    ip_address = request.client.host if request and request.client else None
    user_agent = request.headers.get("user-agent") if request else None
    audit = ApiKeyAuditLogORM(
        key_id=api_key.id,
        action="used",
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else None,
    )
    db.add(audit)

    return api_key


class GatewayTokenResponse(BaseModel):
    """Response with a short-lived gateway JWT.

    Attributes:
        token: Gateway JWT for WebSocket connection.
        agent_config_id: The agent's config UUID.
        name: Agent display name.
    """

    token: str
    agent_config_id: str
    name: str


@router.post("/gateway", response_model=GatewayTokenResponse)
async def exchange_for_gateway_token(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_api_key: Annotated[str, Header()],
) -> GatewayTokenResponse:
    """Exchange an agent API key for a short-lived gateway JWT.

    This bridges user-side auth (API keys) with gateway auth (JWTs)
    without modifying the working agent-gateway.

    Args:
        request: The incoming request (for audit logging).
        settings: App settings.
        db: Database session.
        x_api_key: The raw API key from the X-API-Key header.

    Returns:
        A GatewayTokenResponse with the gateway JWT.

    Raises:
        HTTPException: 401 if the API key is invalid, revoked, or expired.
    """
    api_key = await _validate_api_key(x_api_key, db, request)

    # Look up the agent config
    agent_result = await db.execute(
        select(AgentConfigORM).where(AgentConfigORM.id == api_key.agent_config_id)
    )
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent configuration not found",
        )

    # Create a short-lived gateway JWT using the existing gateway auth module
    token = create_agent_token(
        agent_config_id=agent.id,
        name=agent.name,
        capabilities=agent.capabilities or ["listen", "transcribe"],
        secret=settings.agent_gateway_jwt_secret,
        expire_seconds=3600,
    )

    return GatewayTokenResponse(
        token=token,
        agent_config_id=str(agent.id),
        name=agent.name,
    )


class MCPTokenResponse(BaseModel):
    """Response with a short-lived MCP JWT.

    Attributes:
        token: MCP JWT for authenticating MCP tool calls.
        agent_config_id: The agent's config UUID.
        scopes: Granted scopes.
    """

    token: str
    agent_config_id: str
    scopes: list[str]


@router.post("/mcp", response_model=MCPTokenResponse)
async def exchange_for_mcp_token(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_api_key: Annotated[str, Header()],
) -> MCPTokenResponse:
    """Exchange an agent API key for a short-lived MCP JWT.

    The MCP JWT includes scopes for the MCP server to enforce
    fine-grained authorization on tool calls.

    Args:
        request: The incoming request (for audit logging).
        settings: App settings.
        db: Database session.
        x_api_key: The raw API key from the X-API-Key header.

    Returns:
        An MCPTokenResponse with the MCP JWT.

    Raises:
        HTTPException: 401 if the API key is invalid, revoked, or expired.
    """
    api_key = await _validate_api_key(x_api_key, db, request)

    # Look up the agent config
    agent_result = await db.execute(
        select(AgentConfigORM).where(AgentConfigORM.id == api_key.agent_config_id)
    )
    agent = agent_result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Agent configuration not found",
        )

    scopes = ["meetings:read", "meetings:join", "tasks:write"]

    now = int(time.time())
    payload = {
        "sub": str(api_key.user_id),
        "agent_config_id": str(agent.id),
        "name": agent.name,
        "type": "mcp",
        "scopes": scopes,
        "iat": now,
        "exp": now + 3600,
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm="HS256")

    return MCPTokenResponse(
        token=token,
        agent_config_id=str(agent.id),
        scopes=scopes,
    )


# ---------------------------------------------------------------------------
# Browser user → meeting gateway token
# ---------------------------------------------------------------------------


class MeetingTokenRequest(BaseModel):
    """Request body for meeting token exchange.

    Attributes:
        meeting_id: UUID of the meeting to join.
    """

    meeting_id: str


class MeetingTokenResponse(BaseModel):
    """Response with a gateway JWT scoped to a meeting.

    Attributes:
        token: Gateway JWT for WebSocket connection.
        meeting_id: The meeting UUID.
    """

    token: str
    meeting_id: str


@router.post("/meeting", response_model=MeetingTokenResponse)
async def get_meeting_token(
    body: MeetingTokenRequest,
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> MeetingTokenResponse:
    """Exchange a user Bearer JWT for a gateway token to join a meeting.

    The returned gateway JWT allows the browser to connect via WebSocket
    to the agent-gateway and stream audio / receive transcripts.

    Args:
        body: Request with meeting_id.
        user: The authenticated user (from Bearer JWT).
        settings: App settings.
        db: Database session.

    Returns:
        A MeetingTokenResponse with the gateway JWT.

    Raises:
        HTTPException: 404 if the meeting does not exist.
    """
    result = await db.execute(
        select(MeetingORM).where(MeetingORM.id == body.meeting_id)
    )
    meeting = result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    # Create a gateway JWT representing this browser user as a participant.
    # We use a synthetic agent_config_id (user's own id) since browser
    # participants are not registered agents.
    token = create_agent_token(
        agent_config_id=user.id,
        name=user.name,
        capabilities=["listen", "speak"],
        secret=settings.agent_gateway_jwt_secret,
        expire_seconds=3600,
    )

    return MeetingTokenResponse(
        token=token,
        meeting_id=str(meeting.id),
    )
