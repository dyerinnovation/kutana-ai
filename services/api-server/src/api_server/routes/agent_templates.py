"""Agent template endpoints: browse and activate prebuilt templates."""

from __future__ import annotations

import logging
from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — FastAPI DI

from api_server.auth_deps import CurrentUser  # noqa: TC001 — runtime dep for FastAPI DI
from api_server.billing_deps import MANAGED_AGENT_MIN_TIER, require_tier
from api_server.deps import Settings, get_db_session, get_settings
from api_server.managed_agent_activation import activate_template_for_meeting
from api_server.managed_agents import end_session
from kutana_core.database.models import (
    AgentTemplateORM,
    HostedAgentSessionORM,
    MeetingORM,
)

logger = logging.getLogger(__name__)

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
    tier: str

    class Config:
        from_attributes = True


class ActivateRequest(BaseModel):
    """Request to activate a template for a meeting."""

    meeting_id: str
    anthropic_api_key: str | None = None
    system_prompt_override: str | None = None
    sop_id: str | None = None


class HostedSessionResponse(BaseModel):
    """Hosted agent session representation."""

    id: str
    template_id: str
    meeting_id: str
    status: str
    started_at: str
    system_prompt_override: str | None = None
    anthropic_session_id: str | None = None

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
            tier=t.tier,
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
    result = await db.execute(select(AgentTemplateORM).where(AgentTemplateORM.id == template_id))
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
        tier=template.tier,
    )


@router.post("/{template_id}/activate", response_model=HostedSessionResponse)
async def activate_template(
    template_id: str,
    body: ActivateRequest,
    user: CurrentUser,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HostedSessionResponse:
    """Activate a template for a meeting, creating a hosted agent session.

    **Deprecated.** New clients should use ``PUT /v1/meetings/{id}/selected-agents``
    followed by ``POST /v1/meetings/{id}/start``, which warms all selected
    agents in the background behind the Start Meeting click. This endpoint is
    retained during the migration window for the eval harness and admin tooling.

    Args:
        template_id: UUID of the template.
        body: Activation request with meeting_id.
        user: Authenticated user.
        response: FastAPI response (used to attach the Deprecation header).
        db: Database session.
        settings: Application settings.

    Returns:
        The created hosted session.

    Raises:
        HTTPException: 402/403 if user lacks the required plan tier,
            404 if template or meeting not found, 502 if the Anthropic
            session fails to reach idle.
    """
    response.headers["Deprecation"] = "true"

    require_tier(user, MANAGED_AGENT_MIN_TIER)

    # Verify template exists
    t_result = await db.execute(select(AgentTemplateORM).where(AgentTemplateORM.id == template_id))
    template = t_result.scalar_one_or_none()
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Template not found",
        )

    # Enforce tier requirement from template
    require_tier(user, template.tier)

    # Verify meeting exists
    m_result = await db.execute(select(MeetingORM).where(MeetingORM.id == body.meeting_id))
    meeting = m_result.scalar_one_or_none()
    if meeting is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    # SOP overrides are Business+ only
    if body.sop_id:
        require_tier(user, "business")

    session = await activate_template_for_meeting(
        db=db,
        settings=settings,
        api_key=settings.anthropic_api_key,
        user=user,
        template=template,
        meeting=meeting,
        system_prompt_override=body.system_prompt_override,
        sop_id=body.sop_id,
        anthropic_api_key_override=body.anthropic_api_key,
    )

    return HostedSessionResponse(
        id=str(session.id),
        template_id=str(session.template_id),
        meeting_id=str(session.meeting_id),
        status=session.status,
        started_at=session.started_at.isoformat(),
        anthropic_session_id=session.anthropic_session_id,
    )


@router.delete(
    "/hosted-sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def deactivate_session(
    session_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Deactivate a hosted agent session.

    Sends a user.interrupt to the Anthropic session (if active) and
    marks the local session as stopped.

    Args:
        session_id: UUID of the hosted session.
        user: Authenticated user.
        db: Database session.
        settings: Application settings.

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

    # End the Anthropic session if one exists
    api_key = settings.anthropic_api_key
    if api_key and session.anthropic_session_id:
        try:
            await end_session(api_key, session.anthropic_session_id)
        except Exception:
            logger.warning("Failed to end Anthropic session %s", session.anthropic_session_id)

    from datetime import datetime

    session.status = "stopped"
    session.ended_at = datetime.now(UTC)
    await db.flush()
