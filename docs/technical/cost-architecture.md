# Convene AI Cost Architecture & Subscription Model

## Subscription Tiers

| Tier | Price | Meeting Limits | Features | Target Margin |
|------|-------|---------------|----------|---------------|
| Free/Developer | $0 | 5 meetings/month, 30 min each | Basic extraction (task, decision), no diarization, Haiku-tier LLM | N/A (lead gen) |
| Pro | $29/user/month | Unlimited meetings | All 7 entity types, speaker diarization, meeting recaps, Sonnet-tier for recaps | 80%+ |
| Business | $79/user/month | Unlimited | Custom extractors, premium models, full API access, agent participation, priority processing | 80%+ |
| Enterprise | $150+/user/month | Unlimited | Dedicated infrastructure, on-prem option, custom model selection, SLA, SSO | 85%+ |

## Per-Meeting Cost Estimates
- 30-min meeting (extraction only): ~$0.20
- 30-min meeting (full stack: STT + diarization + extraction + recap): ~$0.35
- 60-min meeting (full stack + agent participation): ~$0.56

## Model Tiering
- Entity extraction: Small LLM (Haiku / GPT-4o-mini) — high volume, low cost
- Meeting recaps: Medium LLM (Sonnet / GPT-4o) — needs reasoning quality
- Agent dialogue: Medium LLM (Sonnet / GPT-4o) — contextual, multi-turn
- Complex analysis: Large LLM (Opus, optional) — premium tier only

## STT Recommendation
- Launch: Deepgram Nova-2 (diarization included, real-time, $0.0043/min)
- Self-hosted option: faster-whisper + pyannote.audio (enterprise on-prem)

## TTS Recommendation
- Real-time agent voice: Cartesia ($0.042/1K chars)
- Quality voice (async): ElevenLabs ($0.18/1K chars, Pro tier)

## Cost Optimization
- Progressive processing: cheap first pass, expensive only when uncertain (60-70% LLM cost reduction)
- Batch extraction windows (30s default) to amortize overhead
- Embedding-based deduplication before LLM calls
- Regional pricing optimization across cloud providers

## Stripe Integration Points
- Products: 4 subscription tiers
- Metered usage: meeting minutes, extraction calls, agent sessions
- Billing portal: self-service upgrade/downgrade/cancel
- Webhooks: subscription lifecycle management
