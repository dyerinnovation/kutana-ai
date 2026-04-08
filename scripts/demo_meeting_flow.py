#!/usr/bin/env python3
"""Demo: Full meeting lifecycle with audio transcription.

Demonstrates the complete Kutana AI meeting flow:
1. Register user + login
2. Create agent + generate API key
3. Create meeting + start it
4. Exchange API key for gateway token
5. Connect to gateway WebSocket
6. Join meeting + stream audio
7. Receive transcript segments
8. End meeting

Usage:
    python scripts/demo_meeting_flow.py
    python scripts/demo_meeting_flow.py --audio data/input/librispeech_sample.flac

Requires:
    - API server running at http://localhost:8000
    - Agent gateway running at ws://localhost:8003
    - PostgreSQL and Redis running
    - (Optional) Whisper STT endpoint for actual transcription
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import struct
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import aiohttp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8000"
GATEWAY_WS = "ws://localhost:8003"

# Default audio file for demo
DEFAULT_AUDIO = Path(__file__).parent.parent / "data" / "input" / "librispeech_sample.flac"

# PCM16 chunk size for streaming (16kHz * 2 bytes * 0.5s = 16000 bytes)
CHUNK_SIZE = 16000
SAMPLE_RATE = 16000


def generate_silence_pcm16(duration_seconds: float = 1.0) -> bytes:
    """Generate silence as PCM16 audio data."""
    num_samples = int(SAMPLE_RATE * duration_seconds)
    return struct.pack(f"<{num_samples}h", *([0] * num_samples))


def load_audio_file(path: Path) -> bytes | None:
    """Load and return raw audio bytes from a file.

    For the demo, we send raw file bytes. The gateway/STT service
    handles format conversion.
    """
    if not path.exists():
        logger.warning("Audio file not found: %s", path)
        return None
    return path.read_bytes()


async def demo_meeting_flow(audio_path: Path | None = None) -> bool:
    """Run the full meeting demo flow. Returns True on success."""
    unique = uuid4().hex[:8]
    email = f"demo-{unique}@example.com"
    password = "demopass12345"
    name = f"Demo User {unique}"

    async with aiohttp.ClientSession() as session:
        # =================================================================
        # Step 1: Register user
        # =================================================================
        logger.info("Step 1: Registering user %s", email)
        async with session.post(
            f"{API_BASE}/api/v1/auth/register",
            json={"email": email, "password": password, "name": name},
        ) as resp:
            if resp.status != 201:
                body = await resp.text()
                logger.error("Registration failed (%d): %s", resp.status, body)
                return False
            data = await resp.json()
            jwt_token = data["token"]
            user_id = data["user"]["id"]
            logger.info("  Registered: user_id=%s", user_id)

        auth_headers = {"Authorization": f"Bearer {jwt_token}"}

        # =================================================================
        # Step 2: Create agent
        # =================================================================
        logger.info("Step 2: Creating agent")
        async with session.post(
            f"{API_BASE}/api/v1/agents",
            headers=auth_headers,
            json={
                "name": f"Demo Agent {unique}",
                "system_prompt": "Demo meeting assistant",
                "capabilities": ["listen", "speak", "transcribe"],
            },
        ) as resp:
            if resp.status != 201:
                body = await resp.text()
                logger.error("Agent creation failed (%d): %s", resp.status, body)
                return False
            data = await resp.json()
            agent_id = data["id"]
            logger.info("  Created agent: %s", agent_id)

        # =================================================================
        # Step 3: Generate API key
        # =================================================================
        logger.info("Step 3: Generating API key")
        async with session.post(
            f"{API_BASE}/api/v1/agents/{agent_id}/keys",
            headers=auth_headers,
            json={"name": "demo-key"},
        ) as resp:
            if resp.status != 201:
                body = await resp.text()
                logger.error("Key generation failed (%d): %s", resp.status, body)
                return False
            data = await resp.json()
            api_key = data["raw_key"]
            logger.info("  API key: %s...", api_key[:12])

        # =================================================================
        # Step 4: Create meeting
        # =================================================================
        logger.info("Step 4: Creating meeting")
        async with session.post(
            f"{API_BASE}/api/v1/meetings",
            headers=auth_headers,
            json={
                "platform": "kutana",
                "title": f"Demo Meeting {unique}",
                "scheduled_at": datetime.now(tz=UTC).isoformat(),
            },
        ) as resp:
            if resp.status != 201:
                body = await resp.text()
                logger.error("Meeting creation failed (%d): %s", resp.status, body)
                return False
            data = await resp.json()
            meeting_id = data["id"]
            logger.info("  Meeting: %s (status=%s)", meeting_id, data["status"])

        # =================================================================
        # Step 5: Start meeting
        # =================================================================
        logger.info("Step 5: Starting meeting")
        async with session.post(
            f"{API_BASE}/api/v1/meetings/{meeting_id}/start",
            headers=auth_headers,
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error("Start meeting failed (%d): %s", resp.status, body)
                return False
            data = await resp.json()
            logger.info("  Meeting started: status=%s", data["status"])

        # =================================================================
        # Step 6: Exchange API key for gateway token
        # =================================================================
        logger.info("Step 6: Exchanging API key for gateway token")
        async with session.post(
            f"{API_BASE}/api/v1/token/gateway",
            headers={"X-API-Key": api_key},
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error("Token exchange failed (%d): %s", resp.status, body)
                return False
            data = await resp.json()
            gateway_token = data["token"]
            logger.info("  Gateway token obtained (length=%d)", len(gateway_token))

        # =================================================================
        # Step 7: Connect to gateway WebSocket
        # =================================================================
        logger.info("Step 7: Connecting to gateway WebSocket")
        transcripts: list[dict[str, object]] = []

        try:
            ws_url = f"{GATEWAY_WS}/agent/connect?token={gateway_token}"
            async with session.ws_connect(ws_url) as ws:
                logger.info("  WebSocket connected")

                # Send join_meeting
                logger.info("Step 8: Joining meeting")
                await ws.send_json({
                    "type": "join_meeting",
                    "meeting_id": meeting_id,
                    "capabilities": ["listen", "speak", "transcribe"],
                })

                # Wait for joined confirmation
                joined = False
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if data.get("type") == "joined":
                            logger.info(
                                "  Joined meeting: room=%s, capabilities=%s",
                                data.get("room_name", "N/A"),
                                data.get("granted_capabilities", []),
                            )
                            joined = True
                            break
                        elif data.get("type") == "error":
                            logger.error("  Join error: %s", data.get("message"))
                            return False
                    elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                        logger.error("  WebSocket closed unexpectedly")
                        return False

                if not joined:
                    logger.error("  Did not receive join confirmation")
                    return False

                # =============================================================
                # Step 9: Stream audio
                # =============================================================
                logger.info("Step 9: Streaming audio")

                # Load audio or use silence
                audio_data: bytes | None = None
                if audio_path and audio_path.exists():
                    audio_data = load_audio_file(audio_path)
                    logger.info("  Loaded audio: %s (%d bytes)", audio_path.name, len(audio_data) if audio_data else 0)

                if audio_data is None:
                    logger.info("  Using 2s silence (no audio file provided)")
                    audio_data = generate_silence_pcm16(2.0)

                # Send audio in chunks
                sequence = 0
                offset = 0
                while offset < len(audio_data):
                    chunk = audio_data[offset : offset + CHUNK_SIZE]
                    await ws.send_json({
                        "type": "audio_data",
                        "data": base64.b64encode(chunk).decode(),
                        "sequence": sequence,
                    })
                    offset += CHUNK_SIZE
                    sequence += 1
                    await asyncio.sleep(0.1)  # pace the sending

                logger.info("  Sent %d audio chunks (%d bytes total)", sequence, len(audio_data))

                # =============================================================
                # Step 10: Listen for transcripts (with timeout)
                # =============================================================
                logger.info("Step 10: Listening for transcripts (5s timeout)")
                try:
                    deadline = asyncio.get_event_loop().time() + 5.0
                    while asyncio.get_event_loop().time() < deadline:
                        try:
                            msg = await asyncio.wait_for(ws.receive(), timeout=1.0)
                        except TimeoutError:
                            continue
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            if data.get("type") == "transcript":
                                transcripts.append(data)
                                logger.info(
                                    "  Transcript: [%.1f-%.1f] %s (confidence=%.2f)",
                                    data.get("start_time", 0),
                                    data.get("end_time", 0),
                                    data.get("text", ""),
                                    data.get("confidence", 0),
                                )
                            elif data.get("type") == "event":
                                logger.info("  Event: %s", data.get("event_type"))
                        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                            break
                except Exception as e:
                    logger.warning("  Transcript listening error: %s", e)

                if transcripts:
                    logger.info("  Received %d transcript segments", len(transcripts))
                else:
                    logger.info("  No transcripts received (STT may not be running)")

                # =============================================================
                # Step 11: Leave meeting
                # =============================================================
                logger.info("Step 11: Leaving meeting")
                await ws.send_json({
                    "type": "leave_meeting",
                    "reason": "demo_complete",
                })
                await asyncio.sleep(0.5)

        except aiohttp.ClientError as e:
            logger.error("  WebSocket connection failed: %s", e)
            logger.info("  (Is the agent gateway running at %s?)", GATEWAY_WS)

        # =================================================================
        # Step 12: End meeting
        # =================================================================
        logger.info("Step 12: Ending meeting")
        async with session.post(
            f"{API_BASE}/api/v1/meetings/{meeting_id}/end",
            headers=auth_headers,
        ) as resp:
            if resp.status != 200:
                body = await resp.text()
                logger.error("End meeting failed (%d): %s", resp.status, body)
            else:
                data = await resp.json()
                logger.info("  Meeting ended: status=%s", data["status"])

        # =================================================================
        # Step 13: Create a task from the meeting
        # =================================================================
        logger.info("Step 13: Creating task from meeting")
        async with session.post(
            f"{API_BASE}/api/v1/tasks",
            headers=auth_headers,
            json={
                "meeting_id": meeting_id,
                "description": f"Review demo meeting transcript {unique}",
                "priority": "medium",
            },
        ) as resp:
            if resp.status == 201:
                data = await resp.json()
                logger.info("  Task created: %s", data["id"])
            else:
                body = await resp.text()
                logger.warning("  Task creation failed (%d): %s", resp.status, body)

        # =================================================================
        # Summary
        # =================================================================
        logger.info("=" * 60)
        logger.info("Demo Complete!")
        logger.info("=" * 60)
        logger.info("  User: %s", email)
        logger.info("  Agent: %s", agent_id)
        logger.info("  Meeting: %s", meeting_id)
        logger.info("  Transcripts received: %d", len(transcripts))
        logger.info("=" * 60)

        return True


async def main() -> None:
    """Run the demo."""
    parser = argparse.ArgumentParser(description="Kutana AI meeting demo")
    parser.add_argument(
        "--audio",
        type=str,
        default=str(DEFAULT_AUDIO),
        help="Path to audio file to stream (default: librispeech_sample.flac)",
    )
    args = parser.parse_args()

    audio_path = Path(args.audio)

    logger.info("=" * 60)
    logger.info("Kutana AI Meeting Demo")
    logger.info("=" * 60)
    logger.info("API: %s", API_BASE)
    logger.info("Gateway: %s", GATEWAY_WS)
    logger.info("Audio: %s", audio_path)
    logger.info("=" * 60)

    success = await demo_meeting_flow(audio_path)
    if not success:
        logger.error("Demo failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
