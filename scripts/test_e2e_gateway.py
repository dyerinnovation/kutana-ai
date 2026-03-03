#!/usr/bin/env python3
"""Manual E2E test for the Agent Gateway.

Connects via WebSocket, sends audio, and waits for transcript segments.

Usage:
    # With a WAV file:
    uv run python scripts/test_e2e_gateway.py --audio-file path/to/audio.wav

    # With generated sine-wave audio (smoke test):
    uv run python scripts/test_e2e_gateway.py --generate-audio

    # Custom gateway URL and JWT secret:
    uv run python scripts/test_e2e_gateway.py --generate-audio \
        --gateway-url ws://localhost:8003 \
        --jwt-secret my-secret

    # Custom meeting ID:
    uv run python scripts/test_e2e_gateway.py --generate-audio \
        --meeting-id 550e8400-e29b-41d4-a716-446655440000
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import logging
import math
import struct
import sys
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import websockets
from agent_gateway.auth import create_agent_token

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("e2e-test")

# ---------------------------------------------------------------------------
# Audio generation
# ---------------------------------------------------------------------------

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit PCM


def generate_sine_wav(duration_s: float = 3.0, frequency: float = 440.0) -> bytes:
    """Generate a sine-wave WAV at 16kHz mono PCM16.

    Args:
        duration_s: Duration in seconds.
        frequency: Sine wave frequency in Hz.

    Returns:
        Raw PCM16 bytes (no WAV header).
    """
    num_samples = int(SAMPLE_RATE * duration_s)
    samples = []
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        value = int(16000 * math.sin(2 * math.pi * frequency * t))
        samples.append(struct.pack("<h", max(-32768, min(32767, value))))
    return b"".join(samples)


def read_wav_file(path: str) -> bytes:
    """Read a WAV file and return raw PCM16 16kHz mono bytes.

    Args:
        path: Path to the WAV file.

    Returns:
        Raw PCM16 bytes.

    Raises:
        ValueError: If the WAV file is not 16kHz mono PCM16.
    """
    with wave.open(path, "rb") as wf:
        if wf.getnchannels() != 1:
            msg = f"Expected mono audio, got {wf.getnchannels()} channels"
            raise ValueError(msg)
        if wf.getframerate() != SAMPLE_RATE:
            msg = f"Expected {SAMPLE_RATE}Hz, got {wf.getframerate()}Hz"
            raise ValueError(msg)
        if wf.getsampwidth() != SAMPLE_WIDTH:
            msg = f"Expected 16-bit audio, got {wf.getsampwidth() * 8}-bit"
            raise ValueError(msg)
        return wf.readframes(wf.getnframes())


# ---------------------------------------------------------------------------
# WebSocket client
# ---------------------------------------------------------------------------

CHUNK_SIZE = 3200  # 100ms of 16kHz 16-bit mono audio


async def run_e2e_test(
    gateway_url: str,
    jwt_secret: str,
    meeting_id: UUID,
    audio_bytes: bytes,
    wait_timeout_s: float = 30.0,
    audio_file_path: str | None = None,
) -> dict[str, Any]:
    """Run the full E2E test.

    Args:
        gateway_url: WebSocket URL of the gateway.
        jwt_secret: JWT secret for token creation.
        meeting_id: Meeting ID to join.
        audio_bytes: Raw PCM16 audio to send.
        wait_timeout_s: Seconds to wait for transcript responses.
        audio_file_path: Path to the audio file (for result metadata).

    Returns:
        Structured results dict with all messages and summary.
    """
    duration_s = len(audio_bytes) / (SAMPLE_RATE * SAMPLE_WIDTH)
    messages: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "meeting_id": str(meeting_id),
        "gateway_url": gateway_url,
        "audio_file": audio_file_path,
        "audio_duration_s": round(duration_s, 2),
        "audio_bytes": len(audio_bytes),
        "messages": messages,
        "summary": {
            "connected": False,
            "joined": False,
            "audio_sent": False,
            "chunks_sent": 0,
            "transcripts_received": 0,
            "combined_text": "",
            "errors": [],
        },
    }

    # Create JWT token
    token = create_agent_token(
        agent_config_id=uuid4(),
        name="e2e-test-agent",
        capabilities=["listen", "transcribe", "speak"],
        secret=jwt_secret,
    )
    ws_url = f"{gateway_url}/agent/connect?token={token}"

    logger.info("Connecting to %s", gateway_url)

    try:
        async with websockets.connect(ws_url) as ws:
            result["summary"]["connected"] = True
            logger.info("Connected! Sending join_meeting...")

            # --- Join meeting ---
            join_msg = {
                "type": "join_meeting",
                "meeting_id": str(meeting_id),
                "capabilities": ["listen", "transcribe", "speak"],
            }
            await ws.send(json.dumps(join_msg))

            # Wait for joined response
            raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            joined = json.loads(raw)
            messages.append(joined)
            if joined.get("type") == "joined":
                result["summary"]["joined"] = True
                logger.info(
                    "Joined meeting %s with capabilities: %s",
                    joined.get("meeting_id"),
                    joined.get("granted_capabilities"),
                )
            else:
                logger.error("Unexpected response: %s", joined)
                result["summary"]["errors"].append(f"Unexpected join response: {joined.get('type')}")
                return result

            # --- Send audio in chunks ---
            total_bytes = len(audio_bytes)
            chunks_sent = 0
            for offset in range(0, total_bytes, CHUNK_SIZE):
                chunk = audio_bytes[offset : offset + CHUNK_SIZE]
                audio_msg = {
                    "type": "audio_data",
                    "data": base64.b64encode(chunk).decode("ascii"),
                    "sequence": chunks_sent,
                }
                await ws.send(json.dumps(audio_msg))
                chunks_sent += 1

            result["summary"]["audio_sent"] = True
            result["summary"]["chunks_sent"] = chunks_sent
            logger.info(
                "Sent %d chunks (%.1fs of audio, %d bytes)",
                chunks_sent,
                duration_s,
                total_bytes,
            )

            # --- Wait for transcript responses ---
            logger.info(
                "Waiting up to %.0fs for transcript segments...",
                wait_timeout_s,
            )
            transcript_texts: list[str] = []
            try:
                deadline = asyncio.get_event_loop().time() + wait_timeout_s
                while asyncio.get_event_loop().time() < deadline:
                    remaining = deadline - asyncio.get_event_loop().time()
                    if remaining <= 0:
                        break
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=remaining)
                    except TimeoutError:
                        break
                    msg = json.loads(raw)
                    messages.append(msg)
                    msg_type = msg.get("type")

                    if msg_type == "transcript":
                        result["summary"]["transcripts_received"] += 1
                        text = msg.get("text", "")
                        transcript_texts.append(text)
                        logger.info(
                            "TRANSCRIPT [%.1f-%.1fs] (confidence=%.2f): %s",
                            msg.get("start_time", 0),
                            msg.get("end_time", 0),
                            msg.get("confidence", 0),
                            text,
                        )
                    elif msg_type == "event":
                        logger.info(
                            "EVENT: %s",
                            msg.get("event_type", "unknown"),
                        )
                    elif msg_type == "error":
                        error_msg = f"[{msg.get('code')}] {msg.get('message')}"
                        result["summary"]["errors"].append(error_msg)
                        logger.error("ERROR: %s", error_msg)
                    else:
                        logger.info("Message: %s", msg_type)

            except Exception as exc:
                result["summary"]["errors"].append(str(exc))
                logger.exception("Error while waiting for transcripts")

            result["summary"]["combined_text"] = " ".join(transcript_texts)

            # --- Leave meeting ---
            leave_msg = {"type": "leave_meeting", "reason": "test_complete"}
            await ws.send(json.dumps(leave_msg))
            logger.info("Left meeting.")

    except Exception as exc:
        result["summary"]["errors"].append(str(exc))
        logger.exception("Failed to connect or run test")

    # --- Summary ---
    if result["summary"]["transcripts_received"] > 0:
        logger.info(
            "SUCCESS: Received %d transcript segment(s)",
            result["summary"]["transcripts_received"],
        )
    else:
        logger.warning(
            "No transcripts received. Check that the STT provider is running "
            "and that the transcription interval has elapsed."
        )

    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """Parse arguments and run the E2E test."""
    parser = argparse.ArgumentParser(
        description="Manual E2E test for the Agent Gateway",
    )
    parser.add_argument(
        "--gateway-url",
        default="ws://localhost:8003",
        help="WebSocket URL of the agent gateway (default: ws://localhost:8003)",
    )
    parser.add_argument(
        "--jwt-secret",
        default="change-me-in-production",
        help="JWT secret (must match AGENT_GATEWAY_JWT_SECRET)",
    )
    parser.add_argument(
        "--meeting-id",
        type=str,
        default=None,
        help="Meeting UUID (default: random)",
    )
    parser.add_argument(
        "--audio-file",
        type=str,
        default=None,
        help="Path to a 16kHz mono PCM16 WAV file",
    )
    parser.add_argument(
        "--generate-audio",
        action="store_true",
        help="Generate a 3-second sine-wave audio (smoke test)",
    )
    parser.add_argument(
        "--wait-timeout",
        type=float,
        default=30.0,
        help="Seconds to wait for transcript responses (default: 30)",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=None,
        help="Path to write JSON results (default: none)",
    )
    args = parser.parse_args()

    # Resolve audio source
    audio_file_path: str | None = None
    if args.audio_file:
        audio_file_path = args.audio_file
        logger.info("Reading audio from %s", audio_file_path)
        audio_bytes = read_wav_file(audio_file_path)
    elif args.generate_audio:
        logger.info("Generating 3s sine-wave audio (440Hz)")
        audio_bytes = generate_sine_wav(duration_s=3.0, frequency=440.0)
    else:
        logger.error("Provide --audio-file or --generate-audio")
        sys.exit(1)

    meeting_id = UUID(args.meeting_id) if args.meeting_id else uuid4()
    logger.info("Meeting ID: %s", meeting_id)

    result = asyncio.run(
        run_e2e_test(
            gateway_url=args.gateway_url,
            jwt_secret=args.jwt_secret,
            meeting_id=meeting_id,
            audio_bytes=audio_bytes,
            wait_timeout_s=args.wait_timeout,
            audio_file_path=audio_file_path,
        )
    )

    # Write results to output file
    if args.output_file:
        output_path = Path(args.output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2))
        logger.info("Results written to %s", output_path)


if __name__ == "__main__":
    main()
