# TTS Tier Enforcement Plan

## Current State

TTS infrastructure is built but **not metered or tier-gated**:

- `TTSBridge` is initialized, wired into `AgentSessionHandler`, and handles synthesis + broadcast
- Three providers implemented: Cartesia ($0.015/1K chars), ElevenLabs ($0.030/1K chars), Piper (free/local)
- **Piper is NOT deployed** — it's an optional dependency not included in the Docker image
- A single global `tts_char_limit` of 100,000 chars/session applies to all agents regardless of tier
- No usage metering, no billing integration, no per-tier provider selection

## Design: Tier-Based TTS

### Provider × Tier Matrix

| Tier | Default Provider | Max chars/call | Session budget | Monthly budget | Voice selection |
|------|-----------------|---------------|----------------|----------------|-----------------|
| **Free** | Cartesia | 500 | 5,000 | 50,000 | 1 default voice |
| **Pro** | Cartesia | 2,000 | 50,000 | 500,000 | 5 voices |
| **Business** | Cartesia or ElevenLabs | 5,000 | 100,000 | 2,000,000 | All voices + custom |
| **Enterprise** | Any (customer choice) | Unlimited | Unlimited | Unlimited | Custom voice cloning |

**Rationale:**
- Cartesia is the default for all tiers — best balance of cost ($0.015/1K), latency (40-90ms), and quality
- ElevenLabs unlocked at Business tier — 2x cost but highest quality, justified by higher subscription price
- Piper removed from production path — requires binary + ONNX models in container, maintenance burden outweighs $0 cost benefit. Can revisit for enterprise on-prem deployments
- Free tier gets TTS (competitive differentiator) but with tight limits to control cost

### Cost Projections

| Tier | Avg chars/meeting | Meetings/month | Monthly TTS cost | Subscription | Margin impact |
|------|-------------------|----------------|-----------------|--------------|---------------|
| Free | 2,000 | 5 | $0.15 | $0 | -$0.15 (lead gen cost) |
| Pro | 10,000 | 20 | $3.00 | $29 | -10% margin (acceptable) |
| Business | 25,000 | 40 | $15.00 | $79 | -19% margin (watch) |
| Enterprise | 50,000 | 100 | $75.00 | $150+ | Negotiate per-deal |

### Implementation Components

#### 1. Budget Enforcement (modify existing `CharBudgetTracker`)

**File:** `services/agent-gateway/src/agent_gateway/tts_bridge.py`

Current `CharBudgetTracker` tracks per-session usage with a global limit. Extend to:

```python
class CharBudgetTracker:
    def __init__(self, per_call_limit: int, session_limit: int, monthly_limit: int):
        self.per_call_limit = per_call_limit
        self.session_limit = session_limit
        self.monthly_limit = monthly_limit
        self.session_used = 0
        # Monthly usage loaded from Redis on init

    def check_and_consume(self, char_count: int) -> BudgetResult:
        if char_count > self.per_call_limit:
            return BudgetResult(allowed=False, reason="per_call_limit_exceeded")
        if self.session_used + char_count > self.session_limit:
            return BudgetResult(allowed=False, reason="session_limit_exceeded")
        if self.monthly_used + char_count > self.monthly_limit:
            return BudgetResult(allowed=False, reason="monthly_limit_exceeded")
        self.session_used += char_count
        self.monthly_used += char_count
        return BudgetResult(allowed=True, remaining_session=self.session_limit - self.session_used)
```

#### 2. Monthly Usage Tracking (Redis)

**Key format:** `tts:usage:{user_id}:{yyyy-mm}` → integer (total chars used this month)

- Increment atomically on each synthesis: `INCRBY tts:usage:{user_id}:2026-04 {chars}`
- Set TTL to 90 days (for billing dispute lookups)
- Load current month's usage when agent joins meeting

#### 3. Tier Resolution

When an agent joins a meeting with `tts_enabled=True`:

1. Look up `AgentApiKeyORM.user_id` → `UserORM`
2. Get user's `plan_tier` from user record (or Stripe subscription status)
3. Resolve tier → budget limits + allowed providers
4. Initialize `CharBudgetTracker` with tier-specific limits
5. If tier doesn't allow requested provider, downgrade to tier default

#### 4. Usage Metering to Audit Log

**File:** `services/agent-gateway/src/agent_gateway/tts_bridge.py`

After each successful synthesis:
```python
await redis.xadd("kutana:events", {
    "event_type": "tts.usage",
    "payload": json.dumps({
        "user_id": str(user_id),
        "agent_config_id": str(agent_config_id),
        "meeting_id": str(meeting_id),
        "chars": char_count,
        "provider": provider_name,
        "cost_estimate": char_count * provider.get_cost_per_char(),
        "timestamp": datetime.now(tz=UTC).isoformat(),
    })
})
```

Worker consumes these events and writes to `api_key_events` table for billing.

#### 5. Provider Gating

**File:** `services/agent-gateway/src/agent_gateway/tts_bridge.py`

```python
TIER_PROVIDERS = {
    "free": ["cartesia"],
    "pro": ["cartesia"],
    "business": ["cartesia", "elevenlabs"],
    "enterprise": ["cartesia", "elevenlabs", "piper"],  # piper for on-prem
}
```

If agent requests ElevenLabs but user is on Pro tier → reject with clear error message.

### Database Changes

Add `plan_tier` to `UserORM` if not already present:
```sql
ALTER TABLE users ADD COLUMN plan_tier VARCHAR(20) DEFAULT 'free';
```

Or resolve from Stripe subscription via `stripe_customer_id` → active subscription → tier.

### API Surface

No new endpoints needed. Budget info returned in existing TTS error responses:
```json
{
  "error": "tts_budget_exceeded",
  "detail": "Monthly TTS budget exceeded (500,000 / 500,000 chars)",
  "tier": "pro",
  "reset_date": "2026-05-01"
}
```

Optional: Add `GET /api/v1/usage/tts` endpoint for dashboard usage display.

### Redis Cache for Phrase Deduplication

Currently in-memory LRU (256 entries, lost on restart). Move to Redis:

- **Key:** `tts:cache:{provider}:{voice_id}:{sha256(text)}`
- **Value:** base64-encoded audio bytes
- **TTL:** 24 hours
- **Benefit:** Repeated phrases (greetings, sign-offs) don't re-synthesize, saving ~30-40% of API calls

### Implementation Priority

| Step | Description | Effort | Dependencies |
|------|-------------|--------|--------------|
| 1 | Add Cartesia API key to deployment secrets + configmap | 1hr | API key from Cartesia |
| 2 | Verify TTS works end-to-end with Cartesia | 1hr | Step 1 |
| 3 | Add `plan_tier` to UserORM (or Stripe resolution) | 2hr | Stripe integration |
| 4 | Extend CharBudgetTracker with per-call + monthly limits | 2hr | Step 3 |
| 5 | Redis monthly usage tracking | 2hr | Redis (already deployed) |
| 6 | Provider gating by tier | 1hr | Step 3 |
| 7 | Usage metering to audit log | 2hr | Worker consumer |
| 8 | Redis phrase cache | 3hr | Redis |
| 9 | Dashboard usage display | 3hr | Step 5 + frontend |

### Open Questions

1. **Free tier TTS:** Include or exclude? Current plan includes it as a differentiator, but even small usage adds up at scale. Alternative: free tier gets TTS in first 3 meetings only (trial).
2. **Voice cloning:** Enterprise feature? ElevenLabs supports custom voice cloning — pricing and legal implications TBD.
3. **Piper for on-prem:** Worth maintaining? Adds Docker image complexity (ONNX runtime + models). Could be an enterprise-only SKU.
4. **Overage billing:** Hard stop at limit, or allow overage with per-char billing? Stripe metered billing supports overage natively.
