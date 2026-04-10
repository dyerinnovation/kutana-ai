"""FastAPI authentication dependencies."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — FastAPI DI

from api_server.auth import decode_user_token, hash_api_key
from api_server.deps import Settings, get_db_session, get_settings
from kutana_core.database.models import AgentApiKeyORM, ApiKeyAuditLogORM, UserORM

_bearer_scheme = HTTPBearer()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


async def validate_api_key(
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


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------


async def _lookup_user(db: AsyncSession, user_id: UUID) -> UserORM:
    """Look up an active user by ID or raise 401."""
    result = await db.execute(select(UserORM).where(UserORM.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserORM:
    """Extract and validate the current user from a Bearer JWT.

    Args:
        credentials: The HTTP Bearer token.
        settings: Application settings (for jwt_secret).
        db: Async database session.

    Returns:
        The authenticated UserORM instance.

    Raises:
        HTTPException: 401 if the token is invalid or user not found.
    """
    try:
        payload = decode_user_token(credentials.credentials, settings.jwt_secret)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from None

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    try:
        user_id = UUID(user_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        ) from None

    return await _lookup_user(db, user_id)


async def get_current_user_or_agent(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserORM:
    """Accept either a Bearer JWT (browser user) or X-API-Key (agent).

    Tries Bearer JWT first, then falls back to X-API-Key. This allows
    both browser users and agents (like the channel server) to access
    the same endpoints.

    Args:
        request: The incoming FastAPI request.
        settings: Application settings.
        db: Async database session.

    Returns:
        The authenticated UserORM instance.

    Raises:
        HTTPException: 401 if neither auth method succeeds.
    """
    # --- Try Bearer JWT ---
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:]
        try:
            payload = decode_user_token(token, settings.jwt_secret)
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
            ) from None

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        try:
            user_id = UUID(user_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            ) from None
        return await _lookup_user(db, user_id)

    # --- Try X-API-Key ---
    api_key_header = request.headers.get("x-api-key")
    if api_key_header:
        api_key_record = await validate_api_key(api_key_header, db, request)
        return await _lookup_user(db, api_key_record.user_id)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Missing credentials — provide Authorization Bearer token or X-API-Key header",
    )


# Convenient type aliases for route injection
CurrentUser = Annotated[UserORM, Depends(get_current_user)]
CurrentUserOrAgent = Annotated[UserORM, Depends(get_current_user_or_agent)]
