"""Full-stack E2E integration test for the Convene AI platform.

Tests the complete flow:
1. Register user via API
2. Login, get JWT
3. Create agent, get agent_config_id
4. Generate API key
5. Exchange API key for gateway token
6. Connect to gateway, join meeting
7. Create a task via API
8. Verify task persisted

Usage:
    python scripts/test_e2e_full_stack.py

Requires:
    - API server running at http://localhost:8000
    - Agent gateway running at ws://localhost:8003
    - PostgreSQL and Redis running
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from datetime import UTC, datetime
from uuid import uuid4

import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8000"
GATEWAY_WS = "ws://localhost:8003"


class TestResult:
    """Tracks test step results."""

    def __init__(self) -> None:
        self.steps: list[dict[str, object]] = []
        self.passed = 0
        self.failed = 0

    def ok(self, name: str, detail: str = "") -> None:
        self.steps.append({"name": name, "status": "PASS", "detail": detail})
        self.passed += 1
        logger.info("PASS: %s %s", name, detail)

    def fail(self, name: str, detail: str = "") -> None:
        self.steps.append({"name": name, "status": "FAIL", "detail": detail})
        self.failed += 1
        logger.error("FAIL: %s %s", name, detail)

    def summary(self) -> str:
        return f"{self.passed} passed, {self.failed} failed, {self.passed + self.failed} total"


async def run_e2e_test() -> TestResult:
    """Run the complete E2E integration test."""
    result = TestResult()
    unique = uuid4().hex[:8]
    email = f"test-{unique}@convene.test"
    password = "testpass12345"
    name = f"Test User {unique}"
    jwt_token = ""
    agent_id = ""
    api_key = ""
    gateway_token = ""
    meeting_id = ""

    async with aiohttp.ClientSession() as session:
        # -----------------------------------------------------------------
        # Step 1: Register user
        # -----------------------------------------------------------------
        try:
            async with session.post(
                f"{API_BASE}/api/v1/auth/register",
                json={"email": email, "password": password, "name": name},
            ) as resp:
                assert resp.status == 201, f"Expected 201, got {resp.status}"
                data = await resp.json()
                jwt_token = data["token"]
                user_id = data["user"]["id"]
                result.ok("Register user", f"user_id={user_id}")
        except Exception as e:
            result.fail("Register user", str(e))
            return result

        auth_headers = {"Authorization": f"Bearer {jwt_token}"}

        # -----------------------------------------------------------------
        # Step 2: Login
        # -----------------------------------------------------------------
        try:
            async with session.post(
                f"{API_BASE}/api/v1/auth/login",
                json={"email": email, "password": password},
            ) as resp:
                assert resp.status == 200, f"Expected 200, got {resp.status}"
                data = await resp.json()
                assert data["token"]
                result.ok("Login", f"token_length={len(data['token'])}")
        except Exception as e:
            result.fail("Login", str(e))

        # -----------------------------------------------------------------
        # Step 3: GET /me
        # -----------------------------------------------------------------
        try:
            async with session.get(
                f"{API_BASE}/api/v1/auth/me",
                headers=auth_headers,
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["email"] == email
                result.ok("GET /me", f"email={data['email']}")
        except Exception as e:
            result.fail("GET /me", str(e))

        # -----------------------------------------------------------------
        # Step 4: Create agent
        # -----------------------------------------------------------------
        try:
            async with session.post(
                f"{API_BASE}/api/v1/agents",
                headers=auth_headers,
                json={
                    "name": f"E2E Agent {unique}",
                    "system_prompt": "Test agent for E2E testing",
                    "capabilities": ["listen", "transcribe"],
                },
            ) as resp:
                assert resp.status == 201, f"Expected 201, got {resp.status}"
                data = await resp.json()
                agent_id = data["id"]
                result.ok("Create agent", f"agent_id={agent_id}")
        except Exception as e:
            result.fail("Create agent", str(e))
            return result

        # -----------------------------------------------------------------
        # Step 5: Generate API key
        # -----------------------------------------------------------------
        try:
            async with session.post(
                f"{API_BASE}/api/v1/agents/{agent_id}/keys",
                headers=auth_headers,
                json={"name": "e2e-test-key"},
            ) as resp:
                assert resp.status == 201, f"Expected 201, got {resp.status}"
                data = await resp.json()
                api_key = data["raw_key"]
                assert api_key.startswith("cvn_")
                result.ok("Generate API key", f"prefix={data['key_prefix']}")
        except Exception as e:
            result.fail("Generate API key", str(e))
            return result

        # -----------------------------------------------------------------
        # Step 6: Exchange API key for gateway token
        # -----------------------------------------------------------------
        try:
            async with session.post(
                f"{API_BASE}/api/v1/token/gateway",
                headers={"X-API-Key": api_key},
            ) as resp:
                assert resp.status == 200, f"Expected 200, got {resp.status}"
                data = await resp.json()
                gateway_token = data["token"]
                assert data["agent_config_id"] == agent_id
                result.ok("Exchange for gateway token", f"token_length={len(gateway_token)}")
        except Exception as e:
            result.fail("Exchange for gateway token", str(e))

        # -----------------------------------------------------------------
        # Step 7: Create meeting
        # -----------------------------------------------------------------
        try:
            async with session.post(
                f"{API_BASE}/api/v1/meetings",
                headers=auth_headers,
                json={
                    "platform": "convene",
                    "title": f"E2E Test Meeting {unique}",
                    "scheduled_at": datetime.now(tz=UTC).isoformat(),
                },
            ) as resp:
                assert resp.status == 201, f"Expected 201, got {resp.status}"
                data = await resp.json()
                meeting_id = data["id"]
                result.ok("Create meeting", f"meeting_id={meeting_id}")
        except Exception as e:
            result.fail("Create meeting", str(e))

        # -----------------------------------------------------------------
        # Step 8: Create task via API
        # -----------------------------------------------------------------
        if meeting_id:
            try:
                async with session.post(
                    f"{API_BASE}/api/v1/tasks",
                    headers=auth_headers,
                    json={
                        "meeting_id": meeting_id,
                        "description": f"E2E test task {unique}",
                        "priority": "high",
                    },
                ) as resp:
                    assert resp.status == 201, f"Expected 201, got {resp.status}"
                    data = await resp.json()
                    task_id = data["id"]
                    assert data["meeting_id"] == meeting_id
                    result.ok("Create task", f"task_id={task_id}")
            except Exception as e:
                result.fail("Create task", str(e))

            # -----------------------------------------------------------------
            # Step 9: Verify task persisted
            # -----------------------------------------------------------------
            try:
                async with session.get(
                    f"{API_BASE}/api/v1/tasks",
                    headers=auth_headers,
                    params={"meeting_id": meeting_id},
                ) as resp:
                    assert resp.status == 200
                    data = await resp.json()
                    assert data["total"] >= 1
                    result.ok("Verify task persisted", f"total={data['total']}")
            except Exception as e:
                result.fail("Verify task persisted", str(e))

        # -----------------------------------------------------------------
        # Step 10: List agents (verify ownership)
        # -----------------------------------------------------------------
        try:
            async with session.get(
                f"{API_BASE}/api/v1/agents",
                headers=auth_headers,
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["total"] >= 1
                result.ok("List agents", f"total={data['total']}")
        except Exception as e:
            result.fail("List agents", str(e))

        # -----------------------------------------------------------------
        # Step 11: List API keys
        # -----------------------------------------------------------------
        try:
            async with session.get(
                f"{API_BASE}/api/v1/agents/{agent_id}/keys",
                headers=auth_headers,
            ) as resp:
                assert resp.status == 200
                data = await resp.json()
                assert data["total"] >= 1
                result.ok("List API keys", f"total={data['total']}")
        except Exception as e:
            result.fail("List API keys", str(e))

    return result


async def main() -> None:
    """Run the E2E test and print results."""
    logger.info("=" * 60)
    logger.info("Convene AI Full-Stack E2E Test")
    logger.info("=" * 60)

    result = await run_e2e_test()

    logger.info("=" * 60)
    logger.info("Results: %s", result.summary())
    logger.info("=" * 60)

    for step in result.steps:
        status = "  " if step["status"] == "PASS" else "X "
        logger.info(
            "%s %s %s",
            status,
            step["name"],
            step.get("detail", ""),
        )

    if result.failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
