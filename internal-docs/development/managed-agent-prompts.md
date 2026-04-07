# Managed Agent Prompt Templates

Optional system-prompt presets for the managed-agent activation flow.

## Current State

### Activation modal (both `AgentsPage.tsx` and `AgentTemplatePage.tsx`)

The "Activate" dialog currently asks for exactly one field:

| Field | Required | Source |
|-------|----------|--------|
| Meeting | Yes (dropdown) | `GET /meetings` filtered to `active`/`scheduled` |

There is **no system prompt field** in the activation modal. The system prompt is baked into each `AgentTemplateORM` row (column `system_prompt TEXT NOT NULL`) and is used as-is when a hosted session starts. Users cannot customize, override, or augment the prompt at activation time.

### Backend models

- **`AgentTemplateORM`** (`agent_templates` table) -- each template has a fixed `system_prompt`.
- **`HostedAgentSessionORM`** (`hosted_agent_sessions` table) -- stores `template_id`, `meeting_id`, `status`, optional encrypted API key. No prompt-override column exists.
- **`ActivateRequest`** (Pydantic) -- accepts `meeting_id` and optional `anthropic_api_key`. No prompt field.

### Frontend API client (`api/agentTemplates.ts`)

`activateTemplate(templateId, meetingId, anthropicApiKey?)` -- passes `meeting_id` and `anthropic_api_key` in the POST body. No prompt data.

## Proposed UX

### Goals

1. System prompt remains **optional** -- users can activate a template with zero extra configuration.
2. Add a collapsible "Customize Prompt" section below the meeting selector.
3. Inside the section, provide a **preset selector** (card-style or dropdown) plus a **free-text textarea** for full customization.
4. Selecting a preset populates the textarea; the user can edit further or clear it entirely.
5. If the textarea is empty at activation time, the template's default `system_prompt` is used.

### Wireframe (text)

```
+----------------------------------------------+
|  Activate: Meeting Notetaker                  |
|----------------------------------------------|
|  Meeting                                      |
|  [ Select a meeting            v ]            |
|                                               |
|  v  Customize Prompt (optional)               |
|  +-----------------------------------------+  |
|  |  Presets:                                |  |
|  |  [Meeting Notes] [Task Extraction]       |  |
|  |  [Summarization] [Technical Review]      |  |
|  |  [Action Items]                          |  |
|  |                                          |  |
|  |  +------------------------------------+ |  |
|  |  | <textarea: editable prompt text>   | |  |
|  |  |                                    | |  |
|  |  +------------------------------------+ |  |
|  |  Blank = use template default prompt   |  |
|  +-----------------------------------------+  |
|                                               |
|              [ Cancel ]  [ Activate Agent ]    |
+----------------------------------------------+
```

## Preset Templates

### 1. Meeting Notes Format

**Category:** productivity

```
You are a meeting notetaker. Structure your notes with:
- **Attendees** -- list everyone present.
- **Agenda Items** -- numbered list of topics discussed.
- **Key Discussion Points** -- concise summary per agenda item.
- **Decisions Made** -- explicit decisions with owners.
- **Open Questions** -- anything unresolved.
Use bullet points, keep language concise, and timestamp major topic transitions.
```

### 2. Task Extraction

**Category:** productivity

```
Focus exclusively on extracting actionable tasks from the conversation. For each task, capture:
- **Task description** -- one clear sentence.
- **Assignee** -- who is responsible (use "Unassigned" if unclear).
- **Due date** -- if mentioned, otherwise "No deadline stated."
- **Priority** -- High / Medium / Low based on conversational urgency cues.
- **Context** -- one sentence of relevant background.
Output tasks in a numbered list. Ignore small talk and tangential discussion.
```

### 3. Summarization Style

**Category:** general

```
After each major topic concludes, produce a 2-3 sentence summary of what was discussed and any conclusions reached. At the end of the meeting, provide a consolidated executive summary (max 200 words) covering the entire session. Prioritize clarity and brevity over completeness.
```

### 4. Technical Review

**Category:** engineering

```
You are a technical review assistant. Pay close attention to:
- Architecture decisions and trade-offs discussed.
- Code or system design references.
- Risks, blockers, and technical debt mentioned.
- Action items related to code changes, deployments, or infrastructure.
Organize output under headings: Architecture, Risks, Action Items, Follow-ups.
```

### 5. Action Items & Follow-ups

**Category:** productivity

```
Track every commitment, follow-up, and next-step mentioned during the meeting. For each item:
- **What** -- the commitment in one sentence.
- **Who** -- the person responsible.
- **When** -- deadline or "next meeting" if unspecified.
- **Status** -- New (default for everything captured in this meeting).
At the end, output a single consolidated checklist sorted by assignee.
```

## Backend Changes

### Option A: Frontend-only presets (recommended for v1)

Store the preset templates as a static array in the frontend. No new database tables or API changes needed for the presets themselves.

Backend change required: add an optional `system_prompt_override` field so users can send a custom prompt at activation time.

| Layer | Change |
|-------|--------|
| `ActivateRequest` (Pydantic) | Add `system_prompt_override: str \| None = None` |
| `HostedAgentSessionORM` | Add column `system_prompt_override TEXT NULL` |
| `activate_template` endpoint | Store `body.system_prompt_override` on the session row |
| Agent runtime | When starting the hosted agent, prefer `session.system_prompt_override` over `template.system_prompt` if non-null |
| Migration | One Alembic migration adding the nullable column |

### Option B: Backend-managed presets (future)

If we later want admins or users to create/share their own prompt presets, add a `prompt_presets` table:

```
prompt_presets
  id           UUID PK
  name         VARCHAR(100) NOT NULL
  description  TEXT
  prompt_text  TEXT NOT NULL
  category     VARCHAR(50)
  is_global    BOOLEAN DEFAULT TRUE
  user_id      UUID NULL FK(users.id)   -- NULL = global preset
  created_at   TIMESTAMPTZ
```

New endpoints: `GET /prompt-presets`, `POST /prompt-presets`, `DELETE /prompt-presets/{id}`.

This can be deferred -- Option A covers the immediate need.

## Frontend Changes

All changes are in the activation modal (`AgentsPage.tsx` lines 306-342 and `AgentTemplatePage.tsx` lines 213-263).

### 1. New state variables

```ts
const [showPromptCustomize, setShowPromptCustomize] = useState(false);
const [promptOverride, setPromptOverride] = useState("");
```

### 2. Preset data (static constant)

```ts
const PROMPT_PRESETS = [
  { label: "Meeting Notes", value: "..." },
  { label: "Task Extraction", value: "..." },
  { label: "Summarization", value: "..." },
  { label: "Technical Review", value: "..." },
  { label: "Action Items", value: "..." },
];
```

Extract to a shared file (e.g., `src/lib/promptPresets.ts`) since both pages use the same modal.

### 3. Modal additions (inside `<div className="space-y-4">`)

Below the meeting selector, add:

- A collapsible toggle: "Customize Prompt (optional)"
- When expanded: preset selector buttons + textarea
- Preset click sets `promptOverride` to the preset text
- Textarea is bound to `promptOverride`
- Helper text: "Leave blank to use the template's default prompt."

### 4. Update `activateTemplate` call

Pass `promptOverride || undefined` as a new argument:

```ts
await activateTemplate(activateTarget.id, selectedMeetingId, undefined, promptOverride || undefined);
```

Update `api/agentTemplates.ts` to include `system_prompt_override` in the POST body.

### 5. Shared modal extraction (recommended)

Both `AgentsPage.tsx` and `AgentTemplatePage.tsx` duplicate the activation modal. Extract to a shared component:

```
src/components/ActivateTemplateDialog.tsx
```

This eliminates the duplication and ensures both pages get the prompt preset feature.

## Implementation Order

1. **Alembic migration** -- add `system_prompt_override` column to `hosted_agent_sessions`
2. **Backend** -- update `ActivateRequest`, endpoint, and agent runtime to use override
3. **Frontend** -- extract shared modal, add preset selector + textarea, wire up API call
4. **Seed data** -- optionally seed the 5 presets into a constants file
5. **Test** -- activate with no override (default behavior), with a preset, with a custom prompt
