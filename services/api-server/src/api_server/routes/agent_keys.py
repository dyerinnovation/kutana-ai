"""Agent API key management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.auth import generate_api_key
from api_server.auth_deps import CurrentUser
from api_server.deps import get_db_session
from kutana_core.database.models import AgentApiKeyORM, AgentConfigORM, ApiKeyAuditLogORM

router = APIRouter(prefix="/agents/{agent_id}/keys", tags=["agent-keys"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class KeyCreateRequest(BaseModel):
    """Request body for generating a new API key.

    Attributes:
        name: Human-readable name for the key.
        expires_at: Optional expiry datetime (null = never expires).
    """

    name: str = "default"
    expires_at: datetime | None = None


class KeyCreateResponse(BaseModel):
    """Response after creating an API key (raw key shown ONCE).

    Attributes:
        id: Key UUID.
        raw_key: The full API key (only returned on creation).
        key_prefix: First 8 characters for display.
        name: Key name.
        expires_at: When the key expires (null = never).
        created_at: Creation timestamp.
    """

    id: UUID
    raw_key: str
    key_prefix: str
    name: str
    expires_at: datetime | None
    created_at: datetime


class KeyResponse(BaseModel):
    """Public API key metadata (no raw key).

    Attributes:
        id: Key UUID.
        key_prefix: First 8 characters for display.
        name: Key name.
        expires_at: When the key expires (null = never).
        revoked_at: When the key was revoked (null if active).
        created_at: Creation timestamp.
    """

    id: UUID
    key_prefix: str
    name: str
    expires_at: datetime | None
    revoked_at: datetime | None
    created_at: datetime


class KeyListResponse(BaseModel):
    """List of API key metadata.

    Attributes:
        items: List of key metadata.
        total: Total count.
    """

    items: list[KeyResponse]
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_owned_agent(
    agent_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> AgentConfigORM:
    """Fetch an agent that belongs to the given user.

    Raises:
        HTTPException: 404 if not found.
    """
    result = await db.execute(
        select(AgentConfigORM).where(
            AgentConfigORM.id == agent_id,
            AgentConfigORM.owner_id == user_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return agent


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=KeyCreateResponse, status_code=201)
async def create_key(
    agent_id: UUID,
    body: KeyCreateRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> KeyCreateResponse:
    """Generate a new API key for an agent.

    The raw key is returned ONCE in this response and cannot be retrieved again.

    Args:
        agent_id: Agent UUID.
        body: Key creation payload.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        KeyCreateResponse with the raw key.
    """
    await _get_owned_agent(agent_id, current_user.id, db)

    raw_key, key_hash = generate_api_key()
    key = AgentApiKeyORM(
        key_prefix=raw_key[:8],
        key_hash=key_hash,
        agent_config_id=agent_id,
        user_id=current_user.id,
        name=body.name,
        expires_at=body.expires_at,
    )
    db.add(key)
    await db.flush()

    # Audit log: key created
    audit = ApiKeyAuditLogORM(
        key_id=key.id,
        action="created",
    )
    db.add(audit)

    return KeyCreateResponse(
        id=key.id,
        raw_key=raw_key,
        key_prefix=key.key_prefix,
        name=key.name,
        expires_at=key.expires_at,
        created_at=key.created_at,
    )


@router.get("", response_model=KeyListResponse)
async def list_keys(
    agent_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> KeyListResponse:
    """List all API key metadata for an agent.

    Args:
        agent_id: Agent UUID.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        KeyListResponse with key metadata (no raw keys).
    """
    await _get_owned_agent(agent_id, current_user.id, db)

    result = await db.execute(
        select(AgentApiKeyORM).where(AgentApiKeyORM.agent_config_id == agent_id)
    )
    keys = result.scalars().all()

    return KeyListResponse(
        items=[
            KeyResponse(
                id=k.id,
                key_prefix=k.key_prefix,
                name=k.name,
                expires_at=k.expires_at,
                revoked_at=k.revoked_at,
                created_at=k.created_at,
            )
            for k in keys
        ],
        total=len(keys),
    )


@router.delete("/{key_id}", status_code=204)
async def revoke_key(
    agent_id: UUID,
    key_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Revoke an API key.

    Args:
        agent_id: Agent UUID.
        key_id: Key UUID to revoke.
        current_user: Authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if key not found.
    """
    await _get_owned_agent(agent_id, current_user.id, db)

    result = await db.execute(
        select(AgentApiKeyORM).where(
            AgentApiKeyORM.id == key_id,
            AgentApiKeyORM.agent_config_id == agent_id,
        )
    )
    key = result.scalar_one_or_none()
    if key is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Key not found",
        )

    key.revoked_at = datetime.now(tz=UTC)

    # Audit log: key revoked
    audit = ApiKeyAuditLogORM(
        key_id=key.id,
        action="revoked",
    )
    db.add(audit)
