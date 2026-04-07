"""OAuth integration endpoints for connecting external platforms."""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Annotated
from urllib.parse import urlencode
from uuid import uuid4

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy import select

from api_server.auth_deps import CurrentUser  # noqa: TC001 — runtime dep for FastAPI DI
from api_server.deps import Settings, get_db_session, get_settings
from api_server.encryption import decrypt_value, encrypt_value
from kutana_core.database.models import IntegrationORM

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/integrations", tags=["integrations"])

logger = logging.getLogger(__name__)

_JWT_ALGORITHM = "HS256"

# Slack OAuth scopes needed for feeds
_SLACK_SCOPES = ",".join(
    [
        "channels:history",
        "channels:read",
        "chat:write",
        "reactions:write",
        "users:read",
        "users.profile:read",
    ]
)


# ---------------------------------------------------------------------------
# Response / request models
# ---------------------------------------------------------------------------


class IntegrationResponse(BaseModel):
    """Public integration representation."""

    id: str
    platform: str
    external_team_id: str | None
    external_team_name: str | None
    status: str
    created_at: str

    class Config:
        from_attributes = True


class ConnectResponse(BaseModel):
    """Response from the connect endpoint with the OAuth authorize URL."""

    authorize_url: str


class SlackChannel(BaseModel):
    """A Slack channel from conversations.list."""

    id: str
    name: str
    is_member: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[IntegrationResponse])
async def list_integrations(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[IntegrationResponse]:
    """List the authenticated user's integrations.

    Args:
        user: Authenticated user.
        db: Database session.

    Returns:
        List of integrations.
    """
    result = await db.execute(
        select(IntegrationORM)
        .where(IntegrationORM.user_id == user.id)
        .order_by(IntegrationORM.created_at.desc())
    )
    integrations = result.scalars().all()
    return [
        IntegrationResponse(
            id=str(i.id),
            platform=i.platform,
            external_team_id=i.external_team_id,
            external_team_name=i.external_team_name,
            status=i.status,
            created_at=i.created_at.isoformat(),
        )
        for i in integrations
    ]


@router.post("/slack/connect", response_model=ConnectResponse)
async def connect_slack(
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ConnectResponse:
    """Generate a Slack OAuth authorize URL.

    Creates a signed JWT state parameter containing the user ID for CSRF
    protection. The state is validated in the callback endpoint.

    Args:
        user: Authenticated user.
        settings: Application settings with Slack client ID.

    Returns:
        The Slack OAuth authorize URL.

    Raises:
        HTTPException: 400 if Slack OAuth is not configured.
    """
    if not settings.slack_client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Slack OAuth is not configured",
        )

    state_payload = {
        "sub": str(user.id),
        "type": "slack_oauth",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,  # 10 minute expiry
    }
    state_token = jwt.encode(state_payload, settings.jwt_secret, algorithm=_JWT_ALGORITHM)

    params = urlencode(
        {
            "client_id": settings.slack_client_id,
            "scope": _SLACK_SCOPES,
            "redirect_uri": settings.slack_redirect_uri,
            "state": state_token,
        }
    )
    authorize_url = f"https://slack.com/oauth/v2/authorize?{params}"

    return ConnectResponse(authorize_url=authorize_url)


@router.get("/slack/callback")
async def slack_callback(
    code: Annotated[str, Query()],
    state: Annotated[str, Query()],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> RedirectResponse:
    """Handle the Slack OAuth callback.

    Exchanges the authorization code for a bot token, encrypts and stores
    it as an integration, then redirects to the frontend.

    Args:
        code: OAuth authorization code from Slack.
        state: Signed JWT state parameter.
        settings: Application settings.
        db: Database session.

    Returns:
        Redirect to the frontend feeds page.

    Raises:
        HTTPException: 400 if state is invalid or token exchange fails.
    """
    import aiohttp

    # Validate state JWT
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[_JWT_ALGORITHM])
        if payload.get("type") != "slack_oauth":
            raise HTTPException(status_code=400, detail="Invalid state type")
        user_id = payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="OAuth state expired")  # noqa: B904
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")  # noqa: B904

    # Exchange code for bot token
    async with (
        aiohttp.ClientSession() as session,
        session.post(
            "https://slack.com/api/oauth.v2.access",
            data={
                "client_id": settings.slack_client_id,
                "client_secret": settings.slack_client_secret,
                "code": code,
                "redirect_uri": settings.slack_redirect_uri,
            },
        ) as resp,
    ):
        data = await resp.json()

    if not data.get("ok"):
        error = data.get("error", "unknown_error")
        logger.error("Slack OAuth token exchange failed: %s", error)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Slack OAuth failed: {error}",
        )

    access_token = data["access_token"]
    team = data.get("team", {})
    bot_user_id = data.get("bot_user_id", "")
    scopes = data.get("scope", "")

    # Upsert integration (one per user per platform)
    result = await db.execute(
        select(IntegrationORM).where(
            IntegrationORM.user_id == user_id,
            IntegrationORM.platform == "slack",
        )
    )
    integration = result.scalar_one_or_none()

    encrypted_token = encrypt_value(access_token)
    token_hint = access_token[-4:] if len(access_token) >= 4 else access_token

    if integration:
        integration.access_token_encrypted = encrypted_token
        integration.token_hint = token_hint
        integration.external_team_id = team.get("id")
        integration.external_team_name = team.get("name")
        integration.bot_user_id = bot_user_id
        integration.scopes = scopes
        integration.status = "active"
    else:
        integration = IntegrationORM(
            id=uuid4(),
            user_id=user_id,
            platform="slack",
            external_team_id=team.get("id"),
            external_team_name=team.get("name"),
            bot_user_id=bot_user_id,
            access_token_encrypted=encrypted_token,
            token_hint=token_hint,
            scopes=scopes,
            status="active",
        )
        db.add(integration)

    await db.flush()

    frontend_url = settings.frontend_url.rstrip("/")
    return RedirectResponse(
        url=f"{frontend_url}/feeds?slack=connected",
        status_code=302,
    )


@router.delete("/{integration_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_integration(
    integration_id: str,
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Revoke and delete an integration.

    Args:
        integration_id: UUID of the integration.
        user: Authenticated user.
        db: Database session.

    Raises:
        HTTPException: 404 if not found or not owned by user.
    """
    result = await db.execute(
        select(IntegrationORM).where(
            IntegrationORM.id == integration_id,
            IntegrationORM.user_id == user.id,
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Integration not found",
        )
    await db.delete(integration)
    await db.flush()


@router.get("/slack/channels", response_model=list[SlackChannel])
async def list_slack_channels(
    user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[SlackChannel]:
    """List Slack channels available via the user's integration.

    Proxies to Slack's conversations.list API using the stored bot token.

    Args:
        user: Authenticated user.
        db: Database session.

    Returns:
        List of Slack channels.

    Raises:
        HTTPException: 404 if no Slack integration found.
        HTTPException: 502 if Slack API call fails.
    """
    import aiohttp

    result = await db.execute(
        select(IntegrationORM).where(
            IntegrationORM.user_id == user.id,
            IntegrationORM.platform == "slack",
            IntegrationORM.status == "active",
        )
    )
    integration = result.scalar_one_or_none()
    if integration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active Slack integration found",
        )

    bot_token = decrypt_value(integration.access_token_encrypted)

    async with (
        aiohttp.ClientSession() as session,
        session.get(
            "https://slack.com/api/conversations.list",
            headers={"Authorization": f"Bearer {bot_token}"},
            params={"types": "public_channel,private_channel", "limit": "200"},
        ) as resp,
    ):
        data = await resp.json()

    if not data.get("ok"):
        error = data.get("error", "unknown_error")
        logger.error("Slack conversations.list failed: %s", error)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Slack API error: {error}",
        )

    return [
        SlackChannel(
            id=ch["id"],
            name=ch["name"],
            is_member=ch.get("is_member", False),
        )
        for ch in data.get("channels", [])
    ]
