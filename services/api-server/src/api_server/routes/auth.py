"""Authentication endpoints: register, login, current user."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.auth import create_user_token, hash_password, verify_password
from api_server.auth_deps import CurrentUser
from api_server.deps import Settings, get_db_session, get_settings
from kutana_core.database.models import UserORM

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    """Request body for user registration.

    Attributes:
        email: User email address.
        password: Plaintext password (min 8 chars).
        name: Display name.
    """

    email: EmailStr
    password: str
    name: str


class LoginRequest(BaseModel):
    """Request body for user login.

    Attributes:
        email: User email address.
        password: Plaintext password.
    """

    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Public user representation.

    Attributes:
        id: User UUID.
        email: Email address.
        name: Display name.
        is_active: Account active flag.
        created_at: Creation timestamp.
    """

    id: UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime


class AuthResponse(BaseModel):
    """Response containing JWT token and user info.

    Attributes:
        token: JWT access token.
        user: The authenticated user.
    """

    token: str
    user: UserResponse


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthResponse:
    """Register a new user account.

    Args:
        body: Registration payload.
        settings: App settings.
        db: Database session.

    Returns:
        JWT token and user info.

    Raises:
        HTTPException: 409 if email already in use.
    """
    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )

    existing = await db.execute(
        select(UserORM).where(UserORM.email == body.email)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    user = UserORM(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
    )
    db.add(user)
    await db.flush()

    token = create_user_token(user.id, user.email, settings.jwt_secret)
    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AuthResponse:
    """Authenticate a user with email and password.

    Args:
        body: Login payload.
        settings: App settings.
        db: Database session.

    Returns:
        JWT token and user info.

    Raises:
        HTTPException: 401 if credentials are invalid.
    """
    result = await db.execute(
        select(UserORM).where(UserORM.email == body.email)
    )
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    token = create_user_token(user.id, user.email, settings.jwt_secret)
    return AuthResponse(
        token=token,
        user=UserResponse(
            id=user.id,
            email=user.email,
            name=user.name,
            is_active=user.is_active,
            created_at=user.created_at,
        ),
    )


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    """Get the currently authenticated user's profile.

    Args:
        current_user: Injected from JWT.

    Returns:
        The user's public profile.
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_active=current_user.is_active,
        created_at=current_user.created_at,
    )
