---
name: update-convene-external-docs
description: >
  Create and update user-facing external documentation for Convene AI. External
  docs are for humans and AI agents who USE Convene — not internal implementation
  docs. TRIGGER on: update external docs, write docs, create docs, feature docs,
  user docs, agent docs, API docs, public docs, documentation for users, external
  documentation, docs site.
---

# Update Convene External Docs

External docs live at `docs/external/` and are the canonical reference for anyone
using Convene AI — human users, agent developers, and AI agents searching for how
to use the platform. They must meet Anthropic/OpenAI doc quality: no placeholders,
real working examples, complete API signatures, agent-readable structure.

## Internal vs External

| Location | Audience | Purpose |
|---|---|---|
| `claude_docs/` | Claude Code sessions only | Implementation patterns, coding conventions |
| `docs/technical/` | Convene developers | Architecture, internals, database schema |
| `docs/external/` | **Users and agents of Convene** | How to use Convene — features, API, examples |

**Rule:** External docs never reference `claude_docs/` or internal flat files.
Cross-link only to other pages within `docs/external/`.

## External Docs Directory Structure

```
docs/external/
├── overview.md                    ← Platform overview — always update this
├── getting-started/
│   ├── quickstart-human.md        ← Join a meeting in the browser
│   └── quickstart-agent.md        ← Connect an AI agent via MCP
├── concepts/
│   ├── meetings.md                ← Lifecycle, rooms, participants, states
│   ├── agents.md                  ← Agent tiers, capabilities, identity
│   ├── tasks.md                   ← Extraction, assignment, tracking
│   └── memory.md                  ← Four-layer persistent memory
├── features/
│   ├── transcription.md           ← Real-time STT, speaker diarization
│   ├── task-extraction.md         ← LLM-powered commitment detection
│   ├── turn-management.md         ← Hand-raise queue, floor control
│   └── voice-agents.md            ← TTS output, audio capabilities
├── agents/
│   ├── mcp-connection.md          ← MCP server URL, auth, tool list
│   ├── capabilities.md            ← listen, transcribe, voice, text_only
│   └── templates.md               ← Prebuilt agent templates with code
├── api-reference/
│   ├── overview.md                ← Auth, base URL, errors, pagination
│   ├── meetings.md                ← Meeting CRUD endpoints
│   ├── participants.md            ← Participant management
│   ├── tasks.md                   ← Task CRUD endpoints
│   └── websocket.md               ← WebSocket protocol + event types
├── integrations/
│   ├── claude-agent-sdk.md        ← Full quickstart: register → join → act
│   ├── openclaw.md                ← Plugin setup, tool matrix, examples
│   └── cli.md                     ← CLI install, auth, command reference
└── examples/
    ├── meeting-assistant.md        ← Complete working agent (annotated)
    ├── action-tracker.md           ← Extracts and logs commitments
    └── decision-logger.md          ← Captures decisions with context
```

## Workflow: After Building a Feature

1. **Identify which pages need changes:**
   - New feature → create `docs/external/features/<name>.md`
   - New API endpoint → update `docs/external/api-reference/<resource>.md`
   - Changed agent capability → update `docs/external/agents/capabilities.md`
   - New integration → create `docs/external/integrations/<name>.md`
   - New concept introduced → add to `docs/external/concepts/`
   - Always update `docs/external/overview.md` if platform surface area changed

2. **Write using the page templates** — see `references/doc-structure.md`

3. **Apply quality standards** — see `references/writing-standards.md`

4. **Cross-link bidirectionally** — new pages should link to related pages;
   related pages should link back

5. **Update `docs/external/overview.md`** — add the new page to the right section

## Per-Page Quality Checklist

Every external doc page must pass before committing:

- [ ] No placeholder text (`TODO`, `TBD`, `[your text here]`, `coming soon`)
- [ ] At least one complete, working code example with real values
- [ ] All parameters documented: name, type, required/optional, default, description
- [ ] A real expected response or output shown (not `{ ... }`)
- [ ] Links go to other `docs/external/` pages — not `claude_docs/` or `docs/technical/`
- [ ] Headings are noun phrases or verb phrases, not questions
- [ ] Agent search test: does the page answer "how do I X?" without ambiguity?

See `references/doc-structure.md` for page templates for each doc type.
See `references/writing-standards.md` for writing quality rules and examples.
