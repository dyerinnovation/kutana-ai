"""Agent configuration CRUD endpoints (wired to database)."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.auth_deps import CurrentUser
from api_server.deps import get_db_session
from kutana_core.database.models import AgentConfigORM

router = APIRouter(prefix="/agents", tags=["agents"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class AgentCreateRequest(BaseModel):
    """Request body for creating a new agent configuration.

    Attributes:
        name: Human-readable agent name.
        voice_id: Optional TTS voice identifier.
        system_prompt: Optional system prompt (not needed for self-managed agents).
        capabilities: List of capabilities the agent supports.
        meeting_type_filter: Meeting types this agent should join.
    """

    name: str
    voice_id: str | None = None
    system_prompt: str = ""
    capabilities: list[str] = Field(default_factory=list)
    meeting_type_filter: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    """Response model for a single agent configuration.

    Attributes:
        id: Unique agent configuration identifier.
        name: Human-readable agent name.
        voice_id: TTS voice identifier.
        system_prompt: System prompt text.
        capabilities: List of agent capabilities.
        meeting_type_filter: Meeting types this agent handles.
        created_at: Record creation timestamp.
        updated_at: Record last-update timestamp.
    """

    id: UUID
    name: str
    voice_id: str | None = None
    system_prompt: str
    capabilities: list[str] = Field(default_factory=list)
    meeting_type_filter: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AgentListResponse(BaseModel):
    """Paginated list of agents.

    Attributes:
        items: List of agent response objects.
        total: Total number of agents matching the query.
    """

    items: list[AgentResponse]
    total: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_response(agent: AgentConfigORM) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        name=agent.name,
        voice_id=agent.voice_id,
        system_prompt=agent.system_prompt,
        capabilities=agent.capabilities or [],
        meeting_type_filter=agent.meeting_type_filter or [],
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=AgentListResponse)
async def list_agents(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentListResponse:
    """List all agent configurations owned by the current user.

    Args:
        current_user: Authenticated user.
        db: Database session.

    Returns:
        AgentListResponse with agent data.
    """
    result = await db.execute(
        select(AgentConfigORM).where(AgentConfigORM.owner_id == current_user.id)
    )
    agents = result.scalars().all()

    count_result = await db.execute(
        select(func.count()).select_from(AgentConfigORM).where(
            AgentConfigORM.owner_id == current_user.id
        )
    )
    total = count_result.scalar_one()

    return AgentListResponse(
        items=[_to_response(a) for a in agents],
        total=total,
    )


@router.post("", response_model=AgentResponse, status_code=201)
async def create_agent(
    body: AgentCreateRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Create a new agent configuration.

    Args:
        body: The agent creation payload.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        AgentResponse with the newly created agent data.
    """
    agent = AgentConfigORM(
        name=body.name,
        voice_id=body.voice_id,
        system_prompt=body.system_prompt,
        capabilities=body.capabilities,
        meeting_type_filter=body.meeting_type_filter,
        owner_id=current_user.id,
    )
    db.add(agent)
    await db.flush()
    return _to_response(agent)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentResponse:
    """Get a single agent configuration by ID.

    Args:
        agent_id: The UUID of the agent to retrieve.
        current_user: Authenticated user.
        db: Database session.

    Returns:
        AgentResponse for the requested agent.

    Raises:
        HTTPException: 404 if agent not found or not owned by user.
    """
    result = await db.execute(
        select(AgentConfigORM).where(
            AgentConfigORM.id == agent_id,
            AgentConfigORM.owner_id == current_user.id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    return _to_response(agent)


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    agent_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Delete an agent configuration.

    Args:
        agent_id: The UUID of the agent to delete.
        current_user: Authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if agent not found or not owned by user.
    """
    result = await db.execute(
        select(AgentConfigORM).where(
            AgentConfigORM.id == agent_id,
            AgentConfigORM.owner_id == current_user.id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent not found",
        )
    await db.delete(agent)
