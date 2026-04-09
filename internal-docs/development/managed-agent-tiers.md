# Managed Agent Tier Assignments

## Current State (10 templates)

All 10 templates are seeded in migration `j2b3c4d5e6f7`. Tier enforcement uses the `tier` column on `agent_templates` and the `require_tier()` helper in the activation endpoint.

## Template Roster

| # | Template | Category | Tier | `is_premium` | ID |
|---|----------|----------|------|-------------|-----|
| 1 | Meeting Notetaker | productivity | **Basic** | false | `a0..001` |
| 2 | Meeting Summarizer | general | **Basic** | false | `a0..004` |
| 3 | Action Item Tracker | productivity | **Pro** | true | `a0..005` |
| 4 | Decision Logger | productivity | **Pro** | true | `a0..006` |
| 5 | Standup Facilitator | productivity | **Pro** | true | `a0..003` |
| 6 | Code Discussion Tracker | engineering | **Pro** | true | `a0..002` |
| 7 | Sprint Retro Coach | engineering | **Business** | true | `a0..007` |
| 8 | Sprint Planner | engineering | **Business** | true | `a0..008` |
| 9 | User Interviewer | research | **Business** | true | `a0..009` |
| 10 | Initial Interviewer | hr | **Business** | true | `a0..00a` |

## Tier Breakdown

### Basic (2 agents)
Core value prop — every user gets meeting notes and summaries. These are passive, silent agents that produce text output via chat.

- **Meeting Notetaker** — detailed, chronological, timestamped notes
- **Meeting Summarizer** — rolling 5-minute summaries + final recap

### Pro (4 agents)
Power-user productivity features. Mix of passive trackers and one active facilitator.

- **Action Item Tracker** — extracts commitments and creates tasks in real time
- **Decision Logger** — captures decisions with rationale and alternatives
- **Standup Facilitator** — *active facilitator* that guides standup format and prompts each participant
- **Code Discussion Tracker** — extracts code references, architecture decisions, tech debt

### Business (4 agents)
Advanced facilitation and research agents. Support organizational SOP customization — SOPs are prepended to the system prompt at activation time.

- **Sprint Retro Coach** — *active facilitator* for retrospectives (Start/Stop/Continue, 4Ls, etc.)
- **Sprint Planner** — *active facilitator* for sprint planning (backlog review, estimation, commitment)
- **User Interviewer** — *active interviewer* for user research sessions
- **Initial Interviewer** — *active interviewer* for candidate screening

## Enforcement

### Backend
- `services/api-server/src/api_server/routes/agent_templates.py` — `activate_template()` calls `require_tier(user, template.tier)`
- The `tier` column is the source of truth. `is_premium` is a legacy boolean kept for backward compatibility (true for Pro+ templates).

### Frontend
- Template cards show tier badges (Basic, Pro, Business)
- Activate button is disabled when user's plan is below the template's tier
- Upgrade prompt links to `/pricing`

## SOP Customization (Business Tier)

Business-tier agents support organizational SOPs stored in the `organization_sops` table. When a Business agent is activated:

1. The platform queries `organization_sops` for the user's org + matching category
2. SOP content is prepended to the agent's system prompt at the `[ORGANIZATION SOP BLOCK]` marker
3. The combined prompt is sent to the Anthropic API

This allows organizations to customize agent behavior (e.g., specific retro formats, interview question banks, reporting templates) without modifying the base system prompt.
