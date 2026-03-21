"""Authentication utilities: password hashing, JWT tokens, API key management."""

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any
from uuid import UUID

import bcrypt
import jwt

# ---------------------------------------------------------------------------
# Password hashing (bcrypt)
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.

    Args:
        password: The plaintext password.

    Returns:
        The bcrypt hash string.
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a plaintext password against a bcrypt hash.

    Args:
        plain: The plaintext password to check.
        hashed: The bcrypt hash to check against.

    Returns:
        True if the password matches.
    """
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ---------------------------------------------------------------------------
# User JWT tokens
# ---------------------------------------------------------------------------

_ALGORITHM = "HS256"


def create_user_token(
    user_id: UUID,
    email: str,
    secret: str,
    expire_seconds: int = 86400,
) -> str:
    """Create a JWT token for a user.

    Args:
        user_id: The user's UUID.
        email: The user's email.
        secret: JWT signing secret.
        expire_seconds: Token lifetime in seconds (default 24h).

    Returns:
        Signed JWT string.
    """
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "type": "user",
        "iat": now,
        "exp": now + expire_seconds,
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def decode_user_token(token: str, secret: str) -> dict[str, Any]:
    """Decode and validate a user JWT token.

    Args:
        token: The JWT string.
        secret: JWT signing secret.

    Returns:
        The decoded payload dict.

    Raises:
        jwt.ExpiredSignatureError: If the token has expired.
        jwt.InvalidTokenError: If the token is invalid.
    """
    return jwt.decode(token, secret, algorithms=[_ALGORITHM])


# ---------------------------------------------------------------------------
# API Key generation / hashing
# ---------------------------------------------------------------------------

_API_KEY_PREFIX = "cvn_"


def generate_api_key() -> tuple[str, str]:
    """Generate a new API key and its SHA-256 hash.

    Returns:
        Tuple of (raw_key, key_hash).
        The raw key has format ``cvn_<32 hex chars>``.
    """
    raw = _API_KEY_PREFIX + secrets.token_hex(16)
    return raw, hash_api_key(raw)


def hash_api_key(raw_key: str) -> str:
    """Hash a raw API key with SHA-256.

    Args:
        raw_key: The full raw API key string.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    return hashlib.sha256(raw_key.encode()).hexdigest()
