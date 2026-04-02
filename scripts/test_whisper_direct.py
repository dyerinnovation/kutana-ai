#!/usr/bin/env python3
"""Direct Whisper API test script using aiohttp.

Sends a WAV file to a remote OpenAI-compatible Whisper endpoint and
prints the response. Uses aiohttp (not httpx) because httpx hangs on
IPv6 link-local addresses.

Usage:
    python -u scripts/test_whisper_direct.py --audio-file data/input/test-speech.wav
    python -u scripts/test_whisper_direct.py --api-url http://localhost:8000/v1
"""

from __future__ import annotations

import argparse
import asyncio
import time

import aiohttp


def log(msg: str) -> None:
    """Print with timestamp and flush."""
    print(f"[{time.monotonic():.3f}] {msg}", flush=True)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Direct Whisper API tester")
    parser.add_argument(
        "--api-url",
        default="http://spark-b0f2.local/kutana-stt/v1",
        help="Base URL of the OpenAI-compatible Whisper API",
    )
    parser.add_argument(
        "--audio-file",
        default="data/input/test-speech.wav",
        help="Path to a WAV file to transcribe",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Request timeout in seconds",
    )
    args = parser.parse_args()

    api_url = args.api_url.rstrip("/")
    post_url = f"{api_url}/audio/transcriptions"

    # Read audio file
    log(f"Reading audio file: {args.audio_file}")
    with open(args.audio_file, "rb") as f:
        wav_bytes = f.read()
    log(f"  File size: {len(wav_bytes)} bytes")

    # Create aiohttp session
    log(f"POST {post_url}")
    log(f"  Timeout: {args.timeout}s")
    timeout = aiohttp.ClientTimeout(total=args.timeout)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        form = aiohttp.FormData()
        form.add_field(
            "file",
            wav_bytes,
            filename="audio.wav",
            content_type="audio/wav",
        )
        form.add_field("model", "openai/whisper-large-v3")
        form.add_field("response_format", "verbose_json")
        form.add_field("language", "en")

        t0 = time.monotonic()
        try:
            async with session.post(post_url, data=form) as response:
                elapsed = time.monotonic() - t0
                body = await response.text()
                log(f"Response status: {response.status}")
                log(f"Response size:   {len(body)} bytes")
                log(f"Elapsed:         {elapsed:.2f}s")
                log("")
                log(f"Body (first 500 chars):")
                print(body[:500], flush=True)
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - t0
            log(f"TIMED OUT after {elapsed:.2f}s")
        except aiohttp.ClientError as e:
            elapsed = time.monotonic() - t0
            log(f"CLIENT ERROR after {elapsed:.2f}s: {e}")
        except Exception as e:
            elapsed = time.monotonic() - t0
            log(f"ERROR after {elapsed:.2f}s: {type(e).__name__}: {e}")

    log("Done.")


if __name__ == "__main__":
    asyncio.run(main())
