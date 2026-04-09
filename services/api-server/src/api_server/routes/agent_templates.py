"""Agent template endpoints: browse and activate prebuilt templates."""

from __future__ import annotations

import logging
import time
from datetime import UTC
from typing import TYPE_CHECKING, Annotated

import jwt as pyjwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from api_server.auth_deps import CurrentUser  # noqa: TC001 — runtime dep for FastAPI DI
from api_server.billing_deps import MANAGED_AGENT_MIN_TIER, require_tier
from api_server.deps import Settings, get_db_session, get_settings
from api_server.managed_agents import (
    create_agent,
    create_vault,
    end_session,
    get_or_create_environment,
    start_session,
)
from kutana_core.database.models import (
    AgentTemplateORM,
    HostedAgentSessionORM,
    MeetingORM,
    OrganizationSOPORM,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

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
    db: Annotated[AsyncSession, Depends(get_db_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> HostedSessionResponse:
    """Activate a template for a meeting, creating a hosted agent session.

    Creates an Anthropic managed agent session backed by the template's
    system prompt. If Business+ and an SOP is selected, the SOP content
    is prepended to the system prompt.

    Args:
        template_id: UUID of the template.
        body: Activation request with meeting_id.
        user: Authenticated user.
        db: Database session.
        settings: Application settings.

    Returns:
        The created hosted session.

    Raises:
        HTTPException: 402/403 if user lacks the required plan tier,
            or 404 if template or meeting not found.
    """
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

    # Build effective system prompt (SOP prepended for Business+ users)
    effective_prompt = body.system_prompt_override or template.system_prompt
    if body.sop_id:
        require_tier(user, "business")
        sop_result = await db.execute(
            select(OrganizationSOPORM).where(OrganizationSOPORM.id == body.sop_id)
        )
        sop = sop_result.scalar_one_or_none()
        if sop is not None:
            effective_prompt = (
                f"## Organization SOP: {sop.name}\n\n{sop.content}\n\n---\n\n{effective_prompt}"
            )

    # Create the DB record
    session = HostedAgentSessionORM(
        user_id=user.id,
        template_id=template.id,
        meeting_id=meeting.id,
        status="active",
        anthropic_api_key_encrypted=body.anthropic_api_key,
        system_prompt_override=body.system_prompt_override,
    )
    db.add(session)
    await db.flush()

    # Create Anthropic managed agent + session
    api_key = settings.anthropic_api_key
    if api_key:
        try:
            # Create the Anthropic agent from the effective system prompt
            anthropic_agent_id = await create_agent(api_key, template.name, effective_prompt)
            session.anthropic_agent_id = anthropic_agent_id

            # Generate an MCP JWT for the managed agent
            now = int(time.time())
            mcp_payload = {
                "sub": str(user.id),
                "type": "mcp",
                "session_id": str(session.id),
                "scopes": [
                    "meetings:read",
                    "meetings:join",
                    "meetings:chat",
                    "turns:manage",
                    "tasks:write",
                ],
                "iat": now,
                "exp": now + 7200,  # 2 hours
            }
            mcp_jwt = pyjwt.encode(mcp_payload, settings.jwt_secret, algorithm="HS256")

            # Set up Anthropic session with the real agent ID
            vault_id = await create_vault(api_key, mcp_jwt)
            env_id = await get_or_create_environment(api_key)
            anthropic_session_id = await start_session(
                api_key,
                anthropic_agent_id,
                env_id,
                vault_id,
            )

            session.anthropic_session_id = anthropic_session_id
            await db.flush()
        except Exception:
            logger.exception("Failed to create Anthropic session for template %s", template.name)
            # Session is still created — Anthropic integration is best-effort
    else:
        logger.warning("ANTHROPIC_API_KEY not set — skipping managed agent session creation")

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
