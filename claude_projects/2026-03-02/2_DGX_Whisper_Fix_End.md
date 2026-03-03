# DGX Whisper Fix — End Summary

## Work Completed
- **ROOT CAUSE FOUND**: Replaced httpx with aiohttp in WhisperRemoteSTT — httpx hangs indefinitely on IPv6 link-local addresses (.local mDNS hostnames resolve to both IPv6 and IPv4; httpx tries IPv6 first and never falls back)
- aiohttp uses `aiohappyeyeballs` (RFC 8305 Happy Eyeballs) which correctly races IPv6/IPv4 connections
- Added diagnostic logging to WhisperRemoteSTT.get_transcript() (buffer size, duration, elapsed time, status codes)
- Added per-call timeout (60s) to Whisper HTTP POST with asyncio.wait_for()
- Added retry/restart logic to AudioBridge._consume_segments (5 retries, exponential backoff)
- Added startup validation logging (STT provider, API URL, Redis URL)
- Fixed .env configuration: added AGENT_GATEWAY_ prefixed vars for pydantic-settings
- Added env_file loading to AgentGatewaySettings with `extra = "ignore"` to avoid rejecting unrelated env vars
- Created standalone diagnostic script: scripts/test_whisper_direct.py
- Created PYTHONPATH_Workaround.md documentation
- Updated CLAUDE.md with PYTHONPATH references and test data section
- Fixed 2 pre-existing audio-service test failures (test_get_segments_yields_stt_segments, test_segments_published_as_events): both tests were missing `process_audio()` call before `get_segments()`
- All 58 gateway tests pass
- All 38 audio-service tests pass (previously 36/38)
- **E2E verification complete**: test_e2e_gateway.py with real audio (test-speech.wav) — 29 transcript segments received, Redis XLEN = 31

## E2E Test Results
- **transcripts_received**: 29
- **Redis XLEN (convene:events)**: 31 (29 transcripts + meeting.started + meeting.ended)
- **Audio**: data/input/test-speech.wav (5.9s, 187,360 bytes, 59 chunks)
- **Latency**: ~10s from audio send to first transcript segment
- **Results file**: data/output/e2e_results.json

## Work Remaining
- Remove httpx dependency from convene-providers if no other code uses it
- Improve transcript accuracy — Whisper is producing repetitive "I'm sorry" / "It's all right" instead of actual speech content (likely a Whisper model issue on DGX Spark, not an integration issue)
- Consider adding `--log-level info` to uvicorn startup to surface application-level logs

## Lessons Learned
- **httpx lacks Happy Eyeballs (RFC 8305)**: When DNS returns both IPv6 link-local and IPv4 addresses (common with `.local` mDNS), httpx tries IPv6 first and hangs indefinitely. aiohttp handles this correctly via `aiohappyeyeballs`. Never use httpx for `.local` hostnames.
- **pydantic-settings env_file loads ALL vars**: When using `env_file = ".env"`, all vars from the file are loaded. If the model has `extra = "forbid"` (default), unrelated env vars cause startup failures. Use `extra = "ignore"` when loading a shared .env file.
- Zero-logging critical paths are a major debugging blind spot — always log before/after external HTTP calls
- pydantic-settings env_prefix means `.env` vars need the prefix too (AGENT_GATEWAY_STT_PROVIDER, not STT_PROVIDER)
- Background asyncio tasks that silently die need retry loops with exponential backoff
- `flush=True` on print statements is essential for diagnostic scripts (stdout buffering masks output)
- macOS UF_HIDDEN flag on .pth files causes silent import failures with Python 3.13
- Use real test data (`data/input/`) not generated sine tones — real audio exercises the full codec path
- Tests that call `get_segments()` without first calling `process_audio()` silently return 0 segments due to `_started` guard
