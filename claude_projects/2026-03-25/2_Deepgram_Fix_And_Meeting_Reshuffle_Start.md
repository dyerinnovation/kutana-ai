# Deepgram Fix + Meeting Reshuffle + K8s Migration

## Problem
1. Deepgram STT drops after initial transcription — WebSocket error 1011 (timeout) due to missing KeepAlive during audio silence gaps
2. Meeting page layout inverted — transcript is main panel, should be participants
3. No video stream support on roadmap
4. All services running in Docker Compose instead of K8s

## Plan (4 Parallel Workstreams)
1. **Deepgram fix**: KeepAlive task, reconnection logic, provider recreation in AudioBridge
2. **Frontend reshuffle**: Participant grid as main panel, transcript as compact sidebar, avatar cards with speaking indicators
3. **Roadmap update**: Video tiles, screen sharing, layout modes added to Phase 3
4. **K8s migration**: Local Docker registry, per-service Dockerfiles (uv base + Python 3.13), Kutana Helm chart, /build-and-push skill, rule updates

## Key Files
- `packages/kutana-providers/src/kutana_providers/stt/deepgram_stt.py`
- `services/agent-gateway/src/agent_gateway/audio_bridge.py`
- `services/audio-service/src/audio_service/audio_pipeline.py`
- `web/src/pages/MeetingRoomPage.tsx`
- `web/src/types/index.ts`
- `charts/kutana/` (new Helm chart)
- `charts/registry/` (new Helm chart)
- `scripts/build_and_push.sh` (new)
- `.claude/skills/build-and-push/` (new skill)
- `.claude/rules/dgx-connection.md` (update)
