"""Agent template endpoints: browse and activate prebuilt templates."""

from __future__ import annotations

from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.auth_deps import CurrentUser
from api_server.deps import get_db_session
from kutana_core.database.models import (
    AgentTemplateORM,
    HostedAgentSessionORM,
    MeetingORM,
)

router = APIRouter(prefix="/agent-templates", tags=["agent-templates"])


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------


class AgentTemplateResponse(BaseModel):
    """Public agent template representation."""

    id: str
    name: str
    description: str
    system_prompt: str
    capabilities: list[str]
    category: str
    is_premium: bool

    class Config:
        from_attributes = True


class ActivateRequest(BaseModel):
    """Request to activate a template for a meeting."""

    meeting_id: str
    anthropic_api_key: str | None = None


class HostedSessionResponse(BaseModel):
    """Hosted agent session representation."""

    id: str
    template_id: str
    meeting_id: str
    status: str
    started_at: str

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[AgentTemplateResponse])
async def list_templates(
    db: Annotated[AsyncSession, Depends(get_db_session)],
    category: str | None = None,
) -> list[AgentTemplateResponse]:
    """List available agent templates, optionally filtered by category.

    Args:
        db: Database session.
        category: Optional category filter.

    Returns:
        List of agent templates.
    """
    query = select(AgentTemplateORM)
    if category:
        query = query.where(AgentTemplateORM.category == category)
    query = query.order_by(AgentTemplateORM.name)

    result = await db.execute(query)
    templates = result.scalars().all()

    return [
        AgentTemplateResponse(
            id=str(t.id),
            name=t.name,
            description=t.description,
            system_prompt=t.system_prompt,
            capabilities=t.capabilities or [],
            category=t.category,
            is_premium=t.is_premium,
        )
        for t in templates
    ]


@router.get("/{template_id}", response_model=AgentTemplateResponse)
async def get_template(
    template_id: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AgentTemplateResponse:
    """Get a single agent template by ID.

    Args:
        template_id: UUID of the template.
        db: Database session.

    Returns:
        The agent template.

    Raises:
        HTTPException: 404 if not found.
    """
    result = await db.execute(
        select(AgentTemplateORM).where(AgentTemplateORM.id == template_id)
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    return AgentTemplateResponse(
        id=str(template.id),
        name=template.name,
        description=template.description,
        system_prompt=template.system_prompt,
        capabilities=template.capabilities or [],
        category=template.category,
        is_premium=template.is_premium,
    )


@router.post("/{template_id}/activate", response_model=HostedSessionResponse)
async def activate_template(
    template_id: str,
    body: ActivateRequest,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> HostedSessionResponse:
    """Activate a template for a meeting, creating a hosted agent session.

    Args:
        template_id: UUID of the template.
        body: Activation request with meeting_id.
        user: Authenticated user.
        db: Database session.

    Returns:
        The created hosted session.

    Raises:
        HTTPException: 404 if template or meeting not found.
    """
    # Verify template exists
    t_result = await db.execute(
        select(AgentTemplateORM).where(AgentTemplateORM.id == template_id)
    )
    template = t_result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Verify meeting exists
    m_result = await db.execute(
        select(MeetingORM).where(MeetingORM.id == body.meeting_id)
    )
    meeting = m_result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    session = HostedAgentSessionORM(
        user_id=user.id,
        template_id=template.id,
        meeting_id=meeting.id,
        status="active",
        anthropic_api_key_encrypted=body.anthropic_api_key,
    )
    db.add(session)
    await db.flush()

    return HostedSessionResponse(
        id=str(session.id),
        template_id=str(session.template_id),
        meeting_id=str(session.meeting_id),
        status=session.status,
        started_at=session.started_at.isoformat(),
    )


@router.delete(
    "/hosted-sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_session(
    session_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Deactivate a hosted agent session.

    Args:
        session_id: UUID of the hosted session.
        user: Authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if session not found or not owned by user.
    """
    result = await db.execute(
        select(HostedAgentSessionORM).where(
            HostedAgentSessionORM.id == session_id,
            HostedAgentSessionORM.user_id == user.id,
        )
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    from datetime import datetime

    session.status = "stopped"
    session.ended_at = datetime.now(UTC)
    await db.flush()
