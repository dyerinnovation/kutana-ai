# Managed Agent Tier Bucketing

Implementation plan for enforcing `is_premium` on managed agent templates so Basic users get core templates and Pro+ users unlock advanced ones.

## Current State

- 4 seed templates in migration `d5e6f7a8b9c0`, all with `is_premium = false`
- `billing_deps.py` has `MANAGED_AGENT_MIN_TIER = "basic"` — a single gate for all templates
- `activate_template` calls `require_tier(user, MANAGED_AGENT_MIN_TIER)` but ignores `template.is_premium`
- Frontend shows a yellow "Premium" label when `is_premium` is true but does not gate the Activate button

## Template Tier Assignments

| Template | Category | Capabilities | Recommended Tier | Rationale |
|---|---|---|---|---|
| Meeting Notetaker | productivity | transcription, task_extraction, action_items | **Basic** | Core value prop — every user should get a notetaker |
| Meeting Summarizer | general | transcription, summarization | **Basic** | Simple post-meeting output, low differentiation cost |
| Standup Facilitator | productivity | transcription, task_extraction, action_items | **Pro** | Active facilitation (guides participants, tracks blockers) is higher-value than passive note-taking |
| Technical Scribe | engineering | transcription, task_extraction, summarization | **Pro** | Engineering-specific context capture is a power-user feature |

**Future templates to consider** (not yet seeded):
| Template Idea | Category | Tier | Notes |
|---|---|---|---|
| Sprint Retro Coach | engineering | Pro | Guides retro formats, clusters feedback |
| Sales Call Analyst | sales | Pro | Objection tracking, deal signals |
| Compliance Monitor | compliance | Business | Regulated-industry feature |
| Executive Briefing Writer | leadership | Business | Cross-meeting synthesis |

## Implementation Steps

### 1. Backend: enforce `is_premium` in activate endpoint

**File:** `services/api-server/src/api_server/routes/agent_templates.py`

In `activate_template()`, after fetching the template and before creating the session, add:

```python
if template.is_premium:
    require_tier(user, "pro")
```

This reuses the existing `require_tier` helper. No new billing constant needed — `is_premium` maps directly to the `"pro"` tier.

### 2. Backend: update seed data

**File:** New Alembic migration (data-only, no schema change)

```sql
UPDATE agent_templates SET is_premium = true
WHERE name IN ('Standup Facilitator', 'Technical Scribe');
```

This flips the two Pro-tier templates. The `is_premium` column and index already exist.

### 3. Frontend: add tier badge to template cards

**File:** `web/src/pages/AgentsPage.tsx` (lines ~287-289)

Replace the current plain "Premium" text span with the existing `UpgradeBadge` component:

```tsx
{template.is_premium && !meetsTier(user, "pro") && (
  <UpgradeBadge requiredTier="pro" />
)}
{template.is_premium && meetsTier(user, "pro") && (
  <span className="text-xs text-yellow-400 font-medium">Pro</span>
)}
```

### 4. Frontend: gate activation in modal

**File:** `web/src/pages/AgentsPage.tsx` (activate modal section, ~line 306)

When `activateTarget.is_premium && !meetsTier(user, "pro")`:
- Disable the "Activate Agent" button
- Show an inline upgrade prompt: "Upgrade to Pro to activate this agent"
- Link to `/pricing`

### 5. Frontend: update `planLimits.ts`

**File:** `web/src/lib/planLimits.ts`

Add `"premium-agents"` to the `upgradeTargetFor` function so it returns `"pro"`.

### 6. API response: include `min_tier` field (optional enhancement)

Add a computed `min_tier` field to `AgentTemplateResponse` so the frontend does not need to duplicate the `is_premium -> "pro"` mapping:

```python
min_tier: str  # "basic" or "pro"
# Set from: "pro" if t.is_premium else "basic"
```

This is optional but cleaner than the frontend interpreting a boolean.

## Files Changed

| File | Change |
|---|---|
| `services/api-server/src/api_server/routes/agent_templates.py` | Add `is_premium` check in `activate_template` |
| `alembic/versions/<new>_set_premium_templates.py` | Data migration flipping 2 templates to premium |
| `web/src/pages/AgentsPage.tsx` | Tier badge, gated Activate button, upgrade prompt in modal |
| `web/src/lib/planLimits.ts` | Add `premium-agents` to `upgradeTargetFor` |

## Testing

- Unit test: activate a premium template as Basic user -> 403
- Unit test: activate a premium template as Pro user -> 201
- Unit test: activate a non-premium template as Basic user -> 201
- E2E: verify badge renders on premium cards, Activate disabled for Basic users
- Migration: verify idempotent (re-running UPDATE is safe)
