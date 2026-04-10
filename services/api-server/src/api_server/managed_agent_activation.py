"""Managed agent activation helpers.

Reusable activation logic extracted from ``routes/agent_templates.py`` so
both the deprecated ``/activate`` endpoint and the new ``start_meeting``
background warming path share a single code path.

Public surface:

- :func:`activate_template_for_meeting` — synchronous activation: vault →
  session → prep message → wait-for-idle. Raises ``HTTPException`` on
  failure (never silently swallows — callers catch and re-publish as
  ``AgentSessionFailed``).
- :func:`_warm_agent_in_background` — background-task entry point used by
  ``POST /v1/meetings/{id}/start``. Opens its own DB session, calls
  :func:`activate_template_for_meeting`, and publishes
  :class:`AgentSessionWarmed` or :class:`AgentSessionFailed` to the
  shared event stream.
- :data:`_warming_tasks` — module-level idempotency map keyed on
  ``(meeting_id, template_id)``.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID  # noqa: TC003 — runtime type in signatures

import jwt as pyjwt
from fastapi import HTTPException, status
from sqlalchemy import select

from api_server.agent_registry import AgentNotFoundError, get_agent_id_by_name
from api_server.managed_agents import (
    create_agent,
    create_vault,
    get_or_create_environment,
    send_message,
    start_session,
    stream_events,
)
from kutana_core.database.models import (
    AgentTemplateORM,
    HostedAgentSessionORM,
    MeetingORM,
    OrganizationSOPORM,
    UserORM,
)
from kutana_core.events.definitions import AgentSessionFailed, AgentSessionWarmed

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from api_server.deps import Settings
    from api_server.event_publisher import EventPublisher

logger = logging.getLogger(__name__)


# Idempotency map — keyed on (meeting_id, template_id).
# Populated by POST /v1/meetings/{id}/start and by the presence heartbeat
# when it re-warms missing agents. Cleared in the background task's
# ``finally`` block so a subsequent warm can proceed.
_warming_tasks: dict[tuple[UUID, UUID], asyncio.Task[None]] = {}


async def activate_template_for_meeting(
    *,
    db: AsyncSession,
    settings: Settings,
    api_key: str,
    user: UserORM,
    template: AgentTemplateORM,
    meeting: MeetingORM,
    system_prompt_override: str | None = None,
    sop_id: UUID | str | None = None,
    anthropic_api_key_override: str | None = None,
) -> HostedAgentSessionORM:
    """Activate a template for a meeting by creating a managed agent session.

    Performs: effective-prompt build (with optional SOP prefix), DB row
    insert, Anthropic agent resolve/create, MCP JWT mint, vault create,
    environment lookup, session create, prep-message + stream-first wait
    for idle. On any failure the session row is marked ``status="failed"``
    with an ``error_detail`` and an ``HTTPException`` is raised — no
    silent swallow. The caller is responsible for committing; callers
    that want to persist the failed row (e.g. the background warm task)
    must commit after catching.

    Args:
        db: Active SQLAlchemy async session (caller commits on success).
        settings: Application settings (for jwt_secret, kutana_agent_tier).
        api_key: Anthropic API key (typically ``settings.anthropic_api_key``).
        user: Authenticated or synthetic user the session is billed to.
        template: The agent template being activated.
        meeting: The meeting the agent will join.
        system_prompt_override: Optional override replacing the template's
            default system prompt before the SOP is (optionally) prefixed.
        sop_id: Optional organization SOP to prepend to the effective prompt.
        anthropic_api_key_override: Optional user-supplied API key captured
            on the session row (encrypted storage TBD).

    Returns:
        The persisted ``HostedAgentSessionORM`` row. The row has already
        been flushed; the caller is responsible for committing.

    Raises:
        HTTPException: 502 if the Anthropic session fails to reach idle,
            or if any SDK call fails. The session row is marked failed
            (with ``error_detail``) before re-raising — the caller must
            commit if it wants the failed row to persist.
    """
    # Build effective system prompt (SOP prepended for Business+ users)
    effective_prompt = system_prompt_override or template.system_prompt
    if sop_id is not None:
        sop_result = await db.execute(
            select(OrganizationSOPORM).where(OrganizationSOPORM.id == sop_id)
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
        anthropic_api_key_encrypted=anthropic_api_key_override,
        system_prompt_override=system_prompt_override,
    )
    db.add(session)
    await db.flush()

    if not api_key:
        logger.warning("ANTHROPIC_API_KEY not set — skipping managed agent session creation")
        return session

    try:
        if sop_id is not None:
            # Org-specific agent: create a new one with the SOP-enriched prompt
            anthropic_agent_id = await create_agent(api_key, template.name, effective_prompt)
        else:
            # Standard template: use pre-created registry agent
            try:
                anthropic_agent_id = get_agent_id_by_name(
                    template.name, tier=settings.kutana_agent_tier
                )
            except AgentNotFoundError:
                logger.warning(
                    "No registry agent for '%s' (tier=%s), falling back to create_agent",
                    template.name,
                    settings.kutana_agent_tier,
                )
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
        meeting_title = (meeting.title or "Untitled")[:40]
        title = f"Kutana · {template.name} · {meeting_title} ({str(meeting.id)[:8]})"
        title = title[:100]
        anthropic_session_id = await start_session(
            api_key,
            anthropic_agent_id,
            env_id,
            vault_id,
            title=title,
        )

        session.anthropic_session_id = anthropic_session_id
        await db.flush()

        # Send initial prep message so the agent knows its role and waits
        # for the Meeting Started notification instead of calling tools.
        #
        # ORDERING: open the SSE stream BEFORE sending the prep message to
        # avoid a race where the session reaches idle before we start listening
        # and we hang forever waiting for an event that already fired.
        prep_text = (
            f"You are the {template.name} for an upcoming Kutana meeting:\n"
            f'"{meeting.title}"\n\n'
            "The meeting has not started yet. You will receive:\n"
            "  1. A 'Meeting Started' notification with the full participant list when the meeting begins\n"
            "  2. Real-time transcript segments during the meeting (one user.message per segment)\n"
            "  3. A summary request when the meeting ends\n\n"
            "Until the Meeting Started notification arrives, do not call any tools. Wait.\n\n"
            "Once the meeting begins, you have full access to your Kutana MCP tools "
            "(kutana_send_chat_message, kutana_speak, kutana_raise_hand, "
            "kutana_get_participants, kutana_get_chat_messages, etc.) and your built-in "
            "toolset (web_search, web_fetch, bash, read, write, etc.).\n\n"
            "Use them actively during the meeting to:\n"
            "  - Fetch context when participants mention external references\n"
            "  - Look up past meetings/decisions via kutana_get_entity_history\n"
            "  - Post notes in real-time at natural breakpoints\n"
            "  - Answer participant questions when addressed directly (via kutana_speak)\n\n"
            "For now: acknowledge and wait."
        )

        # 1. Start consuming the SSE stream in a background task first
        event_gen = stream_events(api_key, anthropic_session_id)

        async def _wait_for_prep_idle() -> None:
            async for event in event_gen:
                etype = getattr(event, "type", None)
                if etype == "session.status_idle":
                    return
                if etype == "session.error":
                    error_obj = getattr(event, "error", None)
                    msg = getattr(error_obj, "message", str(error_obj)) if error_obj else str(event)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"Agent session errored during prep: {msg}",
                    )

        idle_task: asyncio.Task[None] = asyncio.create_task(_wait_for_prep_idle())
        # Let the event loop advance so the stream connection is established
        await asyncio.sleep(0.1)

        # 2. THEN send the prep message (stream is already open, no missed events)
        await send_message(api_key, anthropic_session_id, prep_text)
        logger.info(
            "Sent prep message to session %s (agent %s)", anthropic_session_id, template.name
        )

        # 3. Wait for the session to reach idle
        try:
            await asyncio.wait_for(idle_task, timeout=60.0)
            logger.info("Session %s reached idle after prep message", anthropic_session_id)
        except TimeoutError:
            idle_task.cancel()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    f"Managed agent session {anthropic_session_id} did not reach idle within 60s"
                ),
            ) from None
    except HTTPException as http_exc:
        session.status = "failed"
        session.error_detail = str(http_exc.detail)[:1000]
        session.ended_at = datetime.now(UTC)
        await db.flush()
        raise
    except Exception as exc:
        logger.exception("Failed to create Anthropic session for template %s", template.name)
        session.status = "failed"
        session.error_detail = str(exc)[:1000]
        session.ended_at = datetime.now(UTC)
        await db.flush()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to create managed agent session: {exc}",
        ) from exc

    return session


async def _warm_agent_in_background(
    db_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    user_id: UUID,
    template_id: UUID,
    meeting_id: UUID,
    system_prompt_override: str | None,
    sop_id: UUID | None,
    publisher: EventPublisher,
) -> None:
    """Warm a single managed agent for a meeting in the background.

    Designed to be scheduled via ``asyncio.create_task`` from the
    ``POST /v1/meetings/{id}/start`` handler and the presence heartbeat.
    Opens its own DB session via ``db_factory`` (decoupled from the
    request-scoped session that fired it), activates the template, and
    publishes the outcome to the shared event stream so the frontend's
    per-agent spinner can flip ``warming`` → ``ready`` (or ``failed``).

    Args:
        db_factory: Session factory for opening a fresh DB session.
        settings: Application settings.
        user_id: Owner of the HostedAgentSession row.
        template_id: Template to activate.
        meeting_id: Meeting the agent joins.
        system_prompt_override: Optional override captured from the
            selection row.
        sop_id: Optional SOP to prepend to the effective prompt.
        publisher: Event publisher for Redis Streams.
    """
    hosted_session_id: UUID | None = None
    error_message: str | None = None
    try:
        async with db_factory() as db:
            user = (await db.execute(select(UserORM).where(UserORM.id == user_id))).scalar_one()
            template = (
                await db.execute(select(AgentTemplateORM).where(AgentTemplateORM.id == template_id))
            ).scalar_one()
            meeting = (
                await db.execute(select(MeetingORM).where(MeetingORM.id == meeting_id))
            ).scalar_one()
            try:
                hosted = await activate_template_for_meeting(
                    db=db,
                    settings=settings,
                    api_key=settings.anthropic_api_key,
                    user=user,
                    template=template,
                    meeting=meeting,
                    system_prompt_override=system_prompt_override,
                    sop_id=sop_id,
                )
                hosted_session_id = hosted.id
                await db.commit()
            except Exception as exc:
                # Commit the failed-row state (activate_* already flushed
                # status="failed" + error_detail onto the row) so the GET
                # agent-sessions endpoint and the retry path can see it.
                await db.commit()
                error_message = str(exc)
                raise
        if error_message is None:
            await publisher.publish(
                AgentSessionWarmed(
                    meeting_id=meeting_id,
                    template_id=template_id,
                    hosted_session_id=hosted_session_id,
                )
            )
    except Exception as exc:
        logger.exception(
            "Background warm failed for template %s in meeting %s", template_id, meeting_id
        )
        try:
            await publisher.publish(
                AgentSessionFailed(
                    meeting_id=meeting_id,
                    template_id=template_id,
                    error=error_message or str(exc),
                )
            )
        except Exception:
            logger.exception(
                "Failed to publish AgentSessionFailed for template %s in meeting %s",
                template_id,
                meeting_id,
            )
    finally:
        _warming_tasks.pop((meeting_id, template_id), None)
