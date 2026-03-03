"""Token exchange endpoint: API key → gateway JWT."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_gateway.auth import create_agent_token
from api_server.auth import hash_api_key
from api_server.deps import Settings, get_db_session, get_settings
from convene_core.database.models import AgentApiKeyORM, AgentConfigORM

router = APIRouter(prefix="/token", tags=["token"])


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
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    x_api_key: Annotated[str, Header()],
) -> GatewayTokenResponse:
    """Exchange an agent API key for a short-lived gateway JWT.

    This bridges user-side auth (API keys) with gateway auth (JWTs)
    without modifying the working agent-gateway.

    Args:
        settings: App settings.
        db: Database session.
        x_api_key: The raw API key from the X-API-Key header.

    Returns:
        A GatewayTokenResponse with the gateway JWT.

    Raises:
        HTTPException: 401 if the API key is invalid or revoked.
    """
    key_hash = hash_api_key(x_api_key)

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
