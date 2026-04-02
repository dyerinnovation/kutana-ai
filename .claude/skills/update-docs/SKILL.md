---
name: update-docs
description: Update all documentation after a feature lands. TRIGGER on: update docs, documentation update, update tasklist, update readme, post-feature docs.
---

# Update Docs

Checklist of all documentation locations to review and update after a feature lands.

## Checklist

**Always:**
- [ ] `docs/TASKLIST.md` — mark completed items with `- [x]`, update phase if needed
- [ ] `README.md` — update feature list or architecture diagram if changed
- [ ] Service/package `README.md` — update if the service interface changed

**For new services or packages:**
- [ ] Add entry to root `README.md` architecture table
- [ ] Create `docs/technical/<service-name>.md`

**For API changes:**
- [ ] Update docstrings and OpenAPI descriptions
- [ ] Update `docs/technical/` API reference page

**For agent/MCP changes:**
- [ ] Update `docs/integrations/CLAUDE_AGENT_SDK.md` or `docs/integrations/OPENCLAW.md`
- [ ] Update `.claude/skills/kutana-meeting/SKILL.md` if tool signatures changed

**For infrastructure changes:**
- [ ] Update `claude_docs/DGX_Spark_Reference.md`
- [ ] Update relevant Helm chart docs in `charts/`

**For pattern changes:**
- [ ] Update relevant `claude_docs/*.md` reference doc
- [ ] Add a reference from `CLAUDE.md` if it's a new pattern
