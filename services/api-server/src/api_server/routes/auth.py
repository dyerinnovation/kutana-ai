"""Authentication endpoints: register, login, password reset, email verification."""

from __future__ import annotations

import contextlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID  # noqa: TC003 — used by Pydantic at runtime

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, EmailStr
from redis.asyncio import Redis  # noqa: TC002 — FastAPI DI resolves at startup
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: TC002 — FastAPI DI

from api_server.auth import create_user_token, hash_password, verify_password
from api_server.auth_deps import CurrentUser  # noqa: TC001 — FastAPI DI
from api_server.deps import Settings, get_db_session, get_redis, get_settings
from api_server.email import send_password_reset_email, send_verification_email
from api_server.storage import ObjectStorage, get_storage
from kutana_core.database.models import UserORM

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# ---------------------------------------------------------------------------
# Rate-limit helpers (Redis-backed)
# ---------------------------------------------------------------------------

_LOCKOUT_THRESHOLD = 5
_LOCKOUT_SECONDS = 900  # 15 minutes
_RESET_RATE_LIMIT = 3
_RESET_RATE_WINDOW = 3600  # 1 hour


async def _check_ip_rate_limit(
    redis: Redis,  # type: ignore[type-arg]
    ip: str,
    endpoint: str,
    max_requests: int = 20,
    window: int = 60,
) -> None:
    """Enforce per-IP rate limit. Raises 429 on breach."""
    key = f"rate:{endpoint}:ip:{ip}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window)
    if count > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )


async def _check_email_rate_limit(
    redis: Redis,  # type: ignore[type-arg]
    email: str,
    action: str,
    max_requests: int = _RESET_RATE_LIMIT,
    window: int = _RESET_RATE_WINDOW,
) -> None:
    """Enforce per-email rate limit for password reset / verification resend."""
    key = f"rate:{action}:email:{email}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, window)
    if count > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please try again later.",
        )


async def _record_failed_login(redis: Redis, ip: str, email: str) -> None:  # type: ignore[type-arg]
    """Increment failed login counter for an email and check lockout threshold."""
    key = f"login_failures:{email}"
    count = await redis.incr(key)
    if count == 1:
        await redis.expire(key, _LOCKOUT_SECONDS)
    logger.info("Failed login attempt %d for %s from %s", count, email, ip)


async def _check_lockout(redis: Redis, email: str) -> None:  # type: ignore[type-arg]
    """Check if the account is locked out due to too many failed attempts."""
    key = f"login_failures:{email}"
    count_str = await redis.get(key)
    if count_str and int(count_str) >= _LOCKOUT_THRESHOLD:
        ttl = await redis.ttl(key)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked. Try again in {max(ttl, 1)} seconds.",
        )


async def _clear_failed_logins(redis: Redis, email: str) -> None:  # type: ignore[type-arg]
    """Clear failed login counter on successful login."""
    await redis.delete(f"login_failures:{email}")


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


class ForgotPasswordRequest(BaseModel):
    """Request body for forgot password.

    Attributes:
        email: The account email address.
    """

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Request body for password reset via token.

    Attributes:
        token: The password reset token.
        new_password: New password (min 8 chars).
    """

    token: str
    new_password: str


class UserResponse(BaseModel):
    """Public user representation.

    Attributes:
        id: User UUID.
        email: Email address.
        name: Display name.
        is_active: Account active flag.
        avatar_url: Profile photo URL.
        email_verified: Whether email is verified.
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
    email_verified: bool = False
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
        email_verified=user.email_verified,
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
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
) -> AuthResponse:
    """Register a new user account.

    Args:
        body: Registration payload.
        request: The incoming request (for IP rate limiting).
        settings: App settings.
        db: Database session.
        redis: Redis client for rate limiting.

    Returns:
        JWT token and user info.

    Raises:
        HTTPException: 409 if email already in use, 429 if rate limited.
    """
    ip = request.client.host if request.client else "unknown"
    await _check_ip_rate_limit(redis, ip, "register")

    if len(body.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )

    existing = await db.execute(select(UserORM).where(UserORM.email == body.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    verification_token = secrets.token_urlsafe(32)
    trial_end = datetime.now(UTC) + timedelta(days=14)
    user = UserORM(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name,
        email_verification_token=verification_token,
        plan_tier="basic",
        subscription_status="trialing",
        trial_ends_at=trial_end,
    )
    db.add(user)
    await db.flush()

    # Fire-and-forget: send verification email (don't block registration)
    await send_verification_email(body.email, verification_token, settings)

    token = create_user_token(user.id, user.email, settings.jwt_secret)
    return AuthResponse(token=token, user=_user_response(user))


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
) -> AuthResponse:
    """Authenticate a user with email and password.

    Enforces per-IP rate limiting and account lockout after 5 failed attempts
    (15-minute cooldown, Redis-backed).

    Args:
        body: Login payload.
        request: The incoming request (for IP rate limiting).
        settings: App settings.
        db: Database session.
        redis: Redis client for rate limiting and lockout.

    Returns:
        JWT token and user info.

    Raises:
        HTTPException: 401 if credentials are invalid, 429 if locked out.
    """
    ip = request.client.host if request.client else "unknown"
    await _check_ip_rate_limit(redis, ip, "login")
    await _check_lockout(redis, body.email)

    result = await db.execute(select(UserORM).where(UserORM.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        await _record_failed_login(redis, ip, body.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    await _clear_failed_logins(redis, body.email)
    token = create_user_token(user.id, user.email, settings.jwt_secret)
    return AuthResponse(token=token, user=_user_response(user))


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@router.post("/forgot-password", status_code=200)
async def forgot_password(
    body: ForgotPasswordRequest,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
) -> dict[str, str]:
    """Request a password reset email.

    Always returns success to avoid leaking whether an email is registered.
    Rate-limited to 3 requests per hour per email.

    Args:
        body: Contains the email address.
        settings: App settings.
        db: Database session.
        redis: Redis client for rate limiting.

    Returns:
        Success message.
    """
    await _check_email_rate_limit(redis, body.email, "forgot_password")

    result = await db.execute(select(UserORM).where(UserORM.email == body.email))
    user = result.scalar_one_or_none()

    if user is not None:
        reset_token = secrets.token_urlsafe(32)
        user.password_reset_token = reset_token
        user.password_reset_expires = datetime.now(UTC) + timedelta(hours=1)
        await db.flush()
        await send_password_reset_email(body.email, reset_token, settings)

    return {"message": "If that email is registered, a reset link has been sent."}


@router.post("/reset-password", status_code=200)
async def reset_password(
    body: ResetPasswordRequest,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """Reset a user's password using a valid reset token.

    Args:
        body: Contains the reset token and new password.
        db: Database session.

    Returns:
        Success message.

    Raises:
        HTTPException: 400 if token is invalid/expired, 422 if password too short.
    """
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password must be at least 8 characters",
        )

    result = await db.execute(select(UserORM).where(UserORM.password_reset_token == body.token))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    if user.password_reset_expires is None or user.password_reset_expires < datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.hashed_password = hash_password(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.flush()

    return {"message": "Password has been reset successfully."}


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


@router.get("/verify-email", status_code=200)
async def verify_email(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    """Verify a user's email address using the token from their verification link.

    Args:
        token: The email verification token (query parameter).
        db: Database session.

    Returns:
        Success message.

    Raises:
        HTTPException: 400 if the token is invalid.
    """
    result = await db.execute(select(UserORM).where(UserORM.email_verification_token == token))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification token",
        )

    user.email_verified = True
    user.email_verification_token = None
    await db.flush()

    return {"message": "Email verified successfully."}


@router.post("/resend-verification", status_code=200)
async def resend_verification(
    current_user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    redis: Annotated[Redis, Depends(get_redis)],  # type: ignore[type-arg]
) -> dict[str, str]:
    """Resend the email verification link for the current user.

    Rate-limited to 3 per hour per email.

    Args:
        current_user: The authenticated user.
        settings: App settings.
        db: Database session.
        redis: Redis client for rate limiting.

    Returns:
        Success message.

    Raises:
        HTTPException: 400 if already verified, 429 if rate limited.
    """
    if current_user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already verified",
        )

    await _check_email_rate_limit(redis, current_user.email, "resend_verification")

    verification_token = secrets.token_urlsafe(32)
    current_user.email_verification_token = verification_token
    await db.flush()

    await send_verification_email(current_user.email, verification_token, settings)

    return {"message": "Verification email sent."}


# ---------------------------------------------------------------------------
# Profile / password management
# ---------------------------------------------------------------------------


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
        with contextlib.suppress(Exception):
            await storage.delete(key)
    current_user.avatar_url = None
    await db.flush()
    return _user_response(current_user)
