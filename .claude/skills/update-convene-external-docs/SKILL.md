---
name: update-convene-external-docs
model: claude-sonnet-4-6
description: >
  Create and update user-facing external documentation for Convene AI. External
  docs are for humans and AI agents who USE Convene — not internal implementation
  docs. TRIGGER on: update external docs, write docs, create docs, feature docs,
  user docs, agent docs, API docs, public docs, documentation for users, external
  documentation, docs site.
---

# Update Convene External Docs

External docs live at `external-docs/` and are the canonical reference for anyone
using Convene AI — human users, agent developers, and AI agents searching for how
to use the platform. They must meet Anthropic/Stripe doc quality: no placeholders,
real working examples, complete API signatures, agent-readable structure.

**Core principle:** External docs are about the **product and its functionality**,
not the repository, codebase, or technology internals. Write for a user who
doesn't know or care how Convene is built — only what it does and how to use it.

## Internal vs External

| Location | Audience | Purpose |
|---|---|---|
| `internal-docs/` | Contributors and maintainers | Architecture, internals, database schema, development patterns |
| `external-docs/` | **Users and agents of Convene** | How to use Convene — features, API, examples |

**Rule:** External docs never reference `internal-docs/`, repo structure, or
implementation details. Cross-link only to other pages within `external-docs/`.
Internal links in markdown must use absolute `/docs/<slug>` paths (e.g.,
`/docs/agent-platform/connecting/mcp-quickstart`) so they work in the SPA.

## External Docs Directory Structure

```
external-docs/
├── README.md                          ← Product landing page — always update this
├── agent-platform/
│   ├── overview.md                    ← Three-tier agent architecture
│   └── connecting/
│       ├── mcp-auth.md                ← OAuth 2.1 Bearer token flow
│       ├── mcp-quickstart.md          ← Connect any MCP-compatible agent
│       ├── claude-code-channel.md     ← Claude Code as a meeting participant
│       └── cli.md                     ← Convene CLI reference
├── openclaw/
│   ├── plugin-guide.md                ← OpenClaw plugin setup
│   └── convene-skill.md               ← Convene OpenClaw skill
├── providers/
│   ├── README.md                      ← Provider selection guide
│   ├── llm/                           ← LLM provider docs
│   ├── stt/                           ← Speech-to-text provider docs
│   └── tts/                           ← Text-to-speech provider docs
└── self-hosting/
    └── deployment.md                  ← Self-hosting guide
```

The docs manifest at `web/src/docs/manifest.ts` imports all pages as raw strings
at build time. The navigation tree (`docsTree`) and page lookup (`docPages`) must
be updated whenever files are added, renamed, or removed.

## Workflow: After Building a Feature

1. **Identify which pages need changes:**
   - New feature → create or update the relevant page in `external-docs/`
   - New API endpoint or MCP tool → document in the relevant connecting/tool page
   - Changed agent capability → update `external-docs/agent-platform/overview.md`
   - Always update `external-docs/README.md` if the product surface area changed

2. **Write product-first content** — describe what the feature does for users,
   not how it's implemented. Architecture and internals belong in `internal-docs/`.

3. **Apply quality standards** — see quality checklist below

4. **Cross-link bidirectionally** — new pages should link to related pages;
   related pages should link back

5. **Update `web/src/docs/manifest.ts`** — add the new page to `docPages` and
   `docsTree` so it appears in the sidebar

## Per-Page Quality Checklist

Every external doc page must pass before committing:

- [ ] No placeholder text (`TODO`, `TBD`, `[your text here]`, `coming soon`)
- [ ] At least one complete, working code example with real values
- [ ] All parameters documented: name, type, required/optional, default, description
- [ ] A real expected response or output shown (not `{ ... }`)
- [ ] Internal links use `/docs/<slug>` format — not relative `.md` paths
- [ ] No references to repo internals, codebase structure, or implementation details
- [ ] Headings are noun phrases or verb phrases, not questions
- [ ] Agent search test: does the page answer "how do I X?" without ambiguity?
