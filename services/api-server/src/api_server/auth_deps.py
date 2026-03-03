"""FastAPI authentication dependencies."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.auth import decode_user_token
from api_server.deps import Settings, get_db_session, get_settings
from convene_core.database.models import UserORM

_bearer_scheme = HTTPBearer()


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
        )

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
        )

    result = await db.execute(select(UserORM).where(UserORM.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return user


# Convenient type alias for route injection
CurrentUser = Annotated[UserORM, Depends(get_current_user)]
