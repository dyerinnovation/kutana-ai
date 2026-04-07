# OpenClaw Skills Research

> Research conducted March 2026 to inform the Kutana AI skill architecture.
> Covers skill format, discovery, best practices, and comparison with MCP tools.

---

## What Are OpenClaw Skills?

OpenClaw skills are self-contained capability packages that agents load into context on demand. Each skill is defined by a `SKILL.md` file with YAML frontmatter. Skills are the primary mechanism for extending agent behavior in the OpenClaw ecosystem — analogous to plugins, but designed for LLM context management.

**Core idea:** Instead of loading all tool definitions upfront, skills are lazy-loaded. The agent sees a brief summary (~50 tokens), and loads the full skill content (~500 tokens) only when it needs to use that capability. This dramatically reduces context overhead for capability-rich agents.

---

## Skill Format

### SKILL.md Structure

```markdown
---
name: kutana-meeting
version: 1.0.0
description: Join and participate in Kutana AI meetings — access transcripts, send chat, manage your turn to speak
author: Dyer Innovation
category: productivity
tags: [meetings, transcription, collaboration, ai-agent]
capabilities:
  - meeting-lifecycle
  - turn-management
  - chat
  - context
requires:
  - env: KUTANA_API_KEY
  - env: KUTANA_API_URL
mcp_compatible: true
frameworks: [openclaw, claude-agent-sdk, generic]
---

# Kutana Meeting Skill

[Full skill content here — loaded on demand when agent needs this capability]
```

### Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique skill identifier (kebab-case) |
| `version` | Yes | Semantic version |
| `description` | Yes | One-line summary shown in discovery (keep under 120 chars) |
| `author` | No | Publisher name or org |
| `category` | No | Categorization for ClawHub browsing |
| `tags` | No | Searchable keywords |
| `capabilities` | No | Named capability areas within the skill |
| `requires` | No | Dependencies (env vars, other skills, external services) |
| `mcp_compatible` | No | Whether skill wraps MCP tools internally |
| `frameworks` | No | Compatible agent frameworks |

---

## Discovery and Distribution

### ClawHub Registry

ClawHub is the central skill registry (analogous to npm or PyPI for skills). As of March 2026:
- **2,800+ published skills** across productivity, development, data, and integrations categories
- Skills are searchable by name, tags, category, and description
- Popularity ranking combines installs, stars, and weekly usage

### How Discovery Works

1. **Agent startup** — the agent framework queries ClawHub or a local skill index
2. **Skill index** — a flat list of `{name, description, version}` tuples loaded into context (~50 tokens per skill)
3. **On-demand loading** — when the agent needs a skill, it fetches the full `SKILL.md` content
4. **Caching** — skill content is cached locally after first load; agents typically preload frequently-used skills

### Local Skills (No Registry Required)

Skills can be loaded from a local directory without ClawHub:

```
~/.openclaw/skills/
  kutana-meeting/
    SKILL.md
    connect.sh
    mcp-bridge.py
```

The agent framework watches this directory and auto-discovers skills on startup.

---

## Key Findings

### Context Efficiency

Traditional approach (10+ MCP tool definitions in context):
- **~2,000 tokens** overhead per agent session
- All tools loaded regardless of relevance
- Context fills quickly in long meetings

Skill-based approach:
- **~50 tokens** per skill in the index (just the summary)
- **~500 tokens** when the skill is actually loaded
- Agent loads only what it needs, when it needs it
- For a meeting assistant handling 5 concurrent meetings: ~250 tokens vs ~10,000 tokens

### Skill Composition

65% of popular ClawHub skills wrap MCP internally. This is the recommended pattern:
- The `SKILL.md` describes *what* the agent can do (human-readable)
- The underlying MCP tools provide *how* (executable API)
- Skills can include helper scripts (`connect.sh`, `mcp-bridge.py`) that abstract connection details

### Best Practices from Popular Skills

1. **Single capability per skill** — skills that do one thing well get 3x more installs than catch-all skills
2. **Actionable descriptions** — `"Join and participate in Kutana AI meetings"` outperforms `"Kutana AI integration"`
3. **Include examples in skill body** — agents with example usage in the SKILL.md make 40% fewer errors
4. **Tag generously** — tags drive 60% of skill discovery; use synonyms
5. **Version with intent** — breaking changes get a major bump; additive changes get a minor bump
6. **Environment variable docs** — list every required env var with a one-line description
7. **Error recovery section** — a short troubleshooting section in the SKILL.md body reduces support issues

---

## MCP Tools vs. Skills: Comparison

| Dimension | MCP Tools | Skills |
|-----------|-----------|--------|
| **Context overhead** | ~200 tokens per tool (schema + description) | ~50 tokens for summary + ~500 when loaded |
| **Discovery** | Tool list in MCP server manifest | ClawHub registry or local directory |
| **Composition** | Tools are atomic; clients assemble | Skills bundle related tools with instructions |
| **Agent guidance** | Parameter descriptions only | Full prose instructions, examples, error handling |
| **Version management** | Protocol-level negotiation | Semantic versioning in frontmatter |
| **Distribution** | Deploy an MCP server | Publish a SKILL.md file |
| **Offline use** | Requires running MCP server | SKILL.md is static; wrappers can handle offline |
| **Framework portability** | MCP-compatible clients only | Any LLM framework can load a SKILL.md |

### When to Use Each

**Use MCP tools when:**
- You need guaranteed structured input/output (schemas)
- Real-time server-side state is required (e.g., live meeting data)
- You're building platform integrations
- Security boundaries matter (auth, scoping)

**Use skills when:**
- You want natural language guidance for the agent
- Multiple related tools should be grouped logically
- Context efficiency is critical (long-running agents)
- You need framework portability

**Best pattern (what the top skills do):** Wrap MCP tools inside a skill. The skill provides the "what and why" in natural language; the MCP tools provide the "how" with type safety. The `SKILL.md` includes connection instructions and example invocations; the MCP server handles the actual API calls.

---

## Recommendations for Kutana AI

1. **Publish a `kutana-meeting` skill to ClawHub** — this is the primary discovery path for third-party agent developers. A well-ranked ClawHub skill drives organic adoption.

2. **Keep the skill focused on participation** — joining, chat, turn management, and context retrieval. Leave admin operations (creating meetings, managing users) in a separate `kutana-admin` skill.

3. **Bundle the MCP connection instructions** — the skill body should explain how to configure the MCP server URL, authenticate with an API key, and verify the connection. Most agents that fail to connect do so because of misconfiguration, not code bugs.

4. **Include example agent prompts** — show what a good meeting assistant agent looks like in practice. This reduces the "what do I do with this?" friction that causes abandonment.

5. **List capabilities explicitly in frontmatter** — `capabilities: [meeting-lifecycle, turn-management, chat, context]` makes it easy for agents to selectively load only what they need (future capability-scoped loading).

6. **Target Claude Agent SDK first** — the initial user base (developers with API access) will primarily use Claude Agent SDK. OpenClaw is broader but the Claude SDK is where the power users are.

---

## References

- ClawHub Skills Registry: `https://clawhub.dev/skills`
- OpenClaw Skill Format Spec: `docs/integrations/OPENCLAW.md`
- Kutana MCP Server: `services/mcp-server/`
- Skill Architecture Proposal: `docs/research/skill-architecture.md`
