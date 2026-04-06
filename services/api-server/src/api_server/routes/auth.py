"""Authentication endpoints: register, login, current user."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api_server.auth import create_user_token, hash_password, verify_password
from api_server.auth_deps import CurrentUser
from api_server.deps import Settings, get_db_session, get_settings
from api_server.storage import ObjectStorage, get_storage
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


class UpdateProfileRequest(BaseModel):
    """Request body for profile updates.

    Attributes:
        name: New display name (optional).
    """

    name: str | None = None


class ChangePasswordRequest(BaseModel):
    """Request body for password change.

    Attributes:
        current_password: Current password for verification.
        new_password: New password (min 8 chars).
    """

    current_password: str
    new_password: str


class UserResponse(BaseModel):
    """Public user representation.

    Attributes:
        id: User UUID.
        email: Email address.
        name: Display name.
        is_active: Account active flag.
        avatar_url: Profile photo URL.
        plan_tier: Subscription tier.
        subscription_status: Current subscription state.
        trial_ends_at: Free trial expiration.
        created_at: Creation timestamp.
    """

    id: UUID
    email: str
    name: str
    is_active: bool
    avatar_url: str | None = None
    plan_tier: str = "basic"
    subscription_status: str = "trialing"
    trial_ends_at: datetime | None = None
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
# Helpers
# ---------------------------------------------------------------------------


def _user_response(user: UserORM) -> UserResponse:
    """Build a UserResponse from a UserORM instance."""
    return UserResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        avatar_url=user.avatar_url,
        plan_tier=user.plan_tier,
        subscription_status=user.subscription_status,
        trial_ends_at=user.trial_ends_at,
        created_at=user.created_at,
    )


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

    trial_end = datetime.now(timezone.utc) + timedelta(days=14)
    user = UserORM(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
        plan_tier="basic",
        subscription_status="trialing",
        trial_ends_at=trial_end,
    )
    db.add(user)
    await db.flush()

    token = create_user_token(user.id, user.email, settings.jwt_secret)
    return AuthResponse(token=token, user=_user_response(user))


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
    return AuthResponse(token=token, user=_user_response(user))


@router.get("/me", response_model=UserResponse)
async def me(current_user: CurrentUser) -> UserResponse:
    """Get the currently authenticated user's profile.

    Args:
        current_user: Injected from JWT.

    Returns:
        The user's public profile.
    """
    return _user_response(current_user)


@router.patch("/users/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> UserResponse:
    """Update the current user's profile.

    Args:
        body: Fields to update.
        current_user: Injected from JWT.
        db: Database session.

    Returns:
        Updated user profile.
    """
    if body.name is not None:
        current_user.name = body.name
    await db.flush()
    return _user_response(current_user)


@router.post("/users/me/password", status_code=204)
async def change_password(
    body: ChangePasswordRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    """Change the current user's password.

    Args:
        body: Current and new passwords.
        current_user: Injected from JWT.
        db: Database session.

    Raises:
        HTTPException: 400 if current password is wrong, 422 if new password too short.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )
    current_user.hashed_password = hash_password(body.new_password)
    await db.flush()


@router.post("/users/me/avatar", response_model=UserResponse)
async def upload_avatar(
    file: UploadFile,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> UserResponse:
    """Upload or replace the current user's profile photo.

    Args:
        file: Uploaded image file.
        current_user: Injected from JWT.
        db: Database session.
        storage: Object storage client.

    Returns:
        Updated user profile with avatar_url.

    Raises:
        HTTPException: 400 if file is not an image or too large.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image",
        )

    data = await file.read()
    max_size = 5 * 1024 * 1024  # 5 MB
    if len(data) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image must be under 5 MB",
        )

    ext = file.filename.rsplit(".", 1)[-1] if file.filename and "." in file.filename else "jpg"
    key = f"avatars/{current_user.id}.{ext}"

    await storage.ensure_bucket()
    await storage.upload(key, data, content_type=file.content_type)
    url = await storage.get_presigned_url(key, expires=86400 * 7)

    current_user.avatar_url = url
    await db.flush()
    return _user_response(current_user)


@router.delete("/users/me/avatar", response_model=UserResponse)
async def delete_avatar(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db_session)],
    storage: Annotated[ObjectStorage, Depends(get_storage)],
) -> UserResponse:
    """Remove the current user's profile photo.

    Args:
        current_user: Injected from JWT.
        db: Database session.
        storage: Object storage client.

    Returns:
        Updated user profile with avatar_url cleared.
    """
    if current_user.avatar_url:
        key = f"avatars/{current_user.id}"
        try:
            await storage.delete(key)
        except Exception:
            pass  # Best-effort delete; URL might not match key format
    current_user.avatar_url = None
    await db.flush()
    return _user_response(current_user)
