# DGX Whisper Fix — End Summary

## Work Completed
- Added diagnostic logging to WhisperRemoteSTT.get_transcript() (buffer size, duration, elapsed time, status codes)
- Added per-call timeout (60s) to Whisper HTTP POST with asyncio.wait_for()
- Added retry/restart logic to AudioBridge._consume_segments (5 retries, exponential backoff)
- Added startup validation logging (STT provider, API URL, Redis URL)
- Fixed .env configuration: added AGENT_GATEWAY_ prefixed vars for pydantic-settings
- Added env_file loading to AgentGatewaySettings
- Created standalone diagnostic script: scripts/test_whisper_direct.py
- Created PYTHONPATH_Workaround.md documentation
- Updated CLAUDE.md with PYTHONPATH references and test data section
- **ROOT CAUSE FOUND**: Replaced httpx with aiohttp — httpx hangs indefinitely on IPv6 link-local addresses (.local mDNS hostnames resolve to both IPv6 and IPv4; httpx tries IPv6 first and never falls back)
- aiohttp uses `aiohappyeyeballs` (RFC 8305 Happy Eyeballs) which correctly races IPv6/IPv4 connections
- test_whisper_direct.py confirmed: aiohttp completes in 5.3s, httpx hangs forever
- All 58 gateway tests pass

## Work Remaining
- E2E verification: run test_e2e_gateway.py with --wait-timeout 60
- Verify Redis XLEN > 0 after E2E test
- Verify e2e_results.json shows transcripts_received > 0
- Remove httpx dependency from convene-providers if no other code uses it

## Lessons Learned
- **httpx lacks Happy Eyeballs (RFC 8305)**: When DNS returns both IPv6 link-local and IPv4 addresses (common with `.local` mDNS), httpx tries IPv6 first and hangs indefinitely. aiohttp handles this correctly via `aiohappyeyeballs`. This is the #1 lesson from this session.
- Zero-logging critical paths are a major debugging blind spot — always log before/after external HTTP calls
- pydantic-settings env_prefix means `.env` vars need the prefix too (AGENT_GATEWAY_STT_PROVIDER, not STT_PROVIDER)
- Background asyncio tasks that silently die need retry loops with exponential backoff
- `flush=True` on print statements is essential for diagnostic scripts (stdout buffering masks output)
- macOS UF_HIDDEN flag on .pth files causes silent import failures with Python 3.13
- Use real test data (`data/input/`) not generated sine tones — real audio exercises the full codec path
