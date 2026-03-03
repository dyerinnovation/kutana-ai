"""Tests for agent gateway JWT authentication."""

from __future__ import annotations

import time
from uuid import uuid4

import jwt
import pytest
from agent_gateway.auth import (
    AgentIdentity,
    AuthError,
    create_agent_token,
    validate_token,
)

SECRET = "test-secret-key"
AGENT_ID = uuid4()


class TestCreateAgentToken:
    """Tests for create_agent_token."""

    def test_create_token(self) -> None:
        """Creates a valid JWT token."""
        token = create_agent_token(
            agent_config_id=AGENT_ID,
            name="Test Agent",
            capabilities=["listen"],
            secret=SECRET,
        )
        assert isinstance(token, str)
        # Verify it's valid JWT
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["sub"] == str(AGENT_ID)
        assert payload["name"] == "Test Agent"
        assert payload["capabilities"] == ["listen"]

    def test_create_token_with_expiry(self) -> None:
        """Token has correct expiry."""
        token = create_agent_token(
            agent_config_id=AGENT_ID,
            name="Test",
            capabilities=[],
            secret=SECRET,
            expire_seconds=7200,
        )
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        assert payload["exp"] - payload["iat"] == 7200


class TestValidateToken:
    """Tests for validate_token."""

    def test_valid_token(self) -> None:
        """Valid token returns AgentIdentity."""
        token = create_agent_token(
            agent_config_id=AGENT_ID,
            name="My Agent",
            capabilities=["listen", "transcribe"],
            secret=SECRET,
        )
        identity = validate_token(token, SECRET)
        assert isinstance(identity, AgentIdentity)
        assert identity.agent_config_id == AGENT_ID
        assert identity.name == "My Agent"
        assert identity.capabilities == ["listen", "transcribe"]

    def test_expired_token_raises(self) -> None:
        """Expired token raises AuthError."""
        token = create_agent_token(
            agent_config_id=AGENT_ID,
            name="Test",
            capabilities=[],
            secret=SECRET,
            expire_seconds=-1,  # Already expired
        )
        with pytest.raises(AuthError) as exc_info:
            validate_token(token, SECRET)
        assert exc_info.value.code == "token_expired"

    def test_wrong_secret_raises(self) -> None:
        """Token with wrong secret raises AuthError."""
        token = create_agent_token(
            agent_config_id=AGENT_ID,
            name="Test",
            capabilities=[],
            secret=SECRET,
        )
        with pytest.raises(AuthError) as exc_info:
            validate_token(token, "wrong-secret")
        assert exc_info.value.code == "invalid_token"

    def test_missing_sub_claim_raises(self) -> None:
        """Token without 'sub' claim raises AuthError."""
        payload = {
            "name": "Test",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, SECRET, algorithm="HS256")
        with pytest.raises(AuthError) as exc_info:
            validate_token(token, SECRET)
        assert exc_info.value.code == "missing_claim"

    def test_invalid_uuid_sub_raises(self) -> None:
        """Token with non-UUID 'sub' raises AuthError."""
        payload = {
            "sub": "not-a-uuid",
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, SECRET, algorithm="HS256")
        with pytest.raises(AuthError) as exc_info:
            validate_token(token, SECRET)
        assert exc_info.value.code == "invalid_claim"

    def test_default_capabilities(self) -> None:
        """Missing capabilities defaults to listen + transcribe."""
        payload = {
            "sub": str(AGENT_ID),
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, SECRET, algorithm="HS256")
        identity = validate_token(token, SECRET)
        assert identity.capabilities == ["listen", "transcribe"]

    def test_invalid_capabilities_type_raises(self) -> None:
        """Non-list capabilities raises AuthError."""
        payload = {
            "sub": str(AGENT_ID),
            "capabilities": "listen",  # Should be a list
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        token = jwt.encode(payload, SECRET, algorithm="HS256")
        with pytest.raises(AuthError) as exc_info:
            validate_token(token, SECRET)
        assert exc_info.value.code == "invalid_claim"
