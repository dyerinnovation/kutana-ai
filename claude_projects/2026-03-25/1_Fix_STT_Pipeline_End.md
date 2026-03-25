# Fix STT Pipeline — Completion Summary

## Work Completed
- Fixed `TypeError` in `whisper_remote_stt.py` lines 326 and 337 — `no_speech_prob` and `compression_ratio` now handle `None` values from Whisper API
- Added 8 unit tests in `test_whisper_hallucination_filter.py` covering None fields, missing fields, and filter behavior
- Switched STT provider from `whisper-remote` to `deepgram` in `.env` (fixed duplicate `DEEPGRAM_API_KEY` line, added `AGENT_GATEWAY_STT_API_KEY`)
- Scaled down K3s pods: Whisper STT (freed ~16Gi + 1 GPU), Langfuse ClickHouse + ZooKeeper (freed ~2GB)
- Deployed SigNoz v0.117.0 observability platform on K3s via Helm chart
- Created SigNoz ingress at `http://signoz.spark-b0f2.local`
- Rebuilt and redeployed agent-gateway on DGX — confirmed startup with `stt_provider=deepgram`

## Work Remaining
- Configure Docker Compose services to ship logs to SigNoz OTel collector (add OpenTelemetry SDK or Docker logging driver)
- E2E test: join meeting, speak, verify Deepgram transcripts appear in web UI
- Migrate gateway and other services from Docker Compose to K3s (user flagged this)
- Clean up pre-existing test failures in `test_multi_agent.py` (stale `route_human_audio`/`get_audio_router` references)

## Lessons Learned
- `dict.get(key, default)` returns `None` (not the default) when the key exists with value `None` — always use explicit `is None` checks for API response fields
- DGX memory was maxed at 119Gi/119Gi — the Whisper vLLM pod alone reserved 16Gi. Scaling it down freed massive resources.
- Deepgram requires zero code changes to switch — the AudioBridge/AudioPipeline architecture supports streaming providers natively
- SigNoz Helm chart deploys cleanly on K3s with default settings
