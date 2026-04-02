# Fix STT Pipeline + Switch to Deepgram + Deploy SigNoz

## Problem
- STT pipeline broken: no transcripts when users speak in meetings
- Root cause: `TypeError` in Whisper hallucination filter — `no_speech_prob` returned as `None` from Whisper API
- Wrong STT provider deployed (Whisper instead of Deepgram)
- No log aggregator for debugging

## Plan
1. Fix Whisper `None` comparison bug (defensive — keeps Whisper as fallback)
2. Switch STT provider to Deepgram Nova-2 (real-time streaming, better latency)
3. Free cluster memory by scaling down unused pods (Whisper STT, Langfuse ClickHouse/ZooKeeper)
4. Deploy SigNoz observability platform on K3s
5. Redeploy agent-gateway with Deepgram config

## Key Files
- `packages/kutana-providers/src/kutana_providers/stt/whisper_remote_stt.py` — hallucination filter fix
- `services/audio-service/tests/test_whisper_hallucination_filter.py` — new tests
- `.env` — STT provider config switch to Deepgram
- `docker-compose.yml` — service config
