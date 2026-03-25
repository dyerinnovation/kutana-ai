# Writing Standards for Convene External Docs

These standards apply to every page in `docs/external/`. The goal is docs that
match Anthropic and OpenAI quality: high-fidelity, agent-searchable, and useful
to a developer who has never seen Convene before.

---

## The Non-Negotiables

These rules have no exceptions:

1. **No placeholder text.** Never commit a page with `TODO`, `TBD`, `coming soon`,
   `[placeholder]`, `[your text here]`, or `(details here)`. If you don't know the
   answer, find out before writing the doc.

2. **Every page has a working code example.** Not pseudocode. Not `# ... do stuff`.
   A complete snippet a developer can copy, paste, and run.

3. **Show real output.** If you show a code example, show what it actually prints
   or returns. Not `{ ... }`. Not `<response object>`.

4. **Parameter tables are complete.** Every parameter has: name, type,
   required/optional, default (if any), and a description.

5. **Links go to other `docs/external/` pages only.** Never link to `claude_docs/`,
   `docs/technical/`, or `docs/milestone-testing/`. Those are internal.

---

## Voice and Tone

Model your writing on Anthropic's Claude documentation and Stripe's API docs.

**What they do well:**
- Lead with what the reader needs, not how the system works internally
- Use active voice ("Call `list_meetings` to..." not "Meetings can be listed by...")
- Keep sentences short; one idea per sentence
- Define jargon at first use, then use it consistently
- Never condescend ("simply", "just", "easily", "obviously")

**Good:**
> Call `join_meeting` with a meeting ID and a list of capabilities. The server
> returns a session token valid for the duration of the meeting.

**Bad:**
> In order to join a meeting, you will need to make a call to the join_meeting
> endpoint which will then return a session token that can subsequently be used
> for the duration of the meeting session.

---

## Agent-Readable Structure

AI agents searching for how to use Convene read these docs too. Structure every
page so an agent can find the answer without reading the whole page.

### Heading hygiene

Use specific, descriptive headings. An agent should be able to scan headings and
know whether to read the section.

| Avoid | Prefer |
|---|---|
| Overview | What Is Turn Management |
| Details | Request Parameters |
| Usage | Connect an Agent via MCP |
| Notes | Rate Limits and Quotas |
| See Also | Related: Task Extraction, WebSocket Protocol |

### One concept per page

Don't mix "how to connect" with "available capabilities" with "error handling"
in one flat document. Each belongs on its own page. Link between them.

### Code blocks have language tags

Always tag code blocks: ` ```python `, ` ```bash `, ` ```json `. This enables
syntax highlighting and helps agents identify the language.

### Use consistent terminology

| Always say | Never say |
|---|---|
| meeting | session, call, room (unless referring to UI) |
| agent | bot, assistant (unless quoting user-facing UI) |
| participant | attendee, user (participant includes both humans and agents) |
| task | action item, to-do (task is the canonical term in the API) |
| MCP tool | function, method, API call (when referring to MCP tools specifically) |

---

## Code Example Quality

Every example must meet these bars:

### Complete, not excerpted

Show the full imports, setup, and call. If the setup is long, show it once at the
top and reference it in subsequent examples.

**Too short:**
```python
response = client.create_meeting(title="Standup")
```

**Complete:**
```python
import os
from convene import ConveneClient

client = ConveneClient(api_key=os.environ["CONVENE_API_KEY"])

meeting = client.meetings.create(
    title="Weekly Standup",
    scheduled_at="2026-04-01T09:00:00Z",
)
print(meeting.id)  # "mtg_01HXN4B7KXYZ"
```

### Use realistic values

Use realistic-looking IDs, timestamps, names, and data. Avoid `foo`, `bar`,
`test`, `example123`, or `YOUR_VALUE_HERE`.

| Avoid | Prefer |
|---|---|
| `meeting_id = "abc"` | `meeting_id = "mtg_01HXN4B7KXYZ"` |
| `api_key = "YOUR_KEY"` | `api_key = os.environ["CONVENE_API_KEY"]` |
| `name = "test user"` | `name = "Sarah Chen"` |
| `time = "2024-01-01"` | `time = "2026-04-01T09:00:00Z"` |

### Show the expected output

After every code example, show what the output looks like:

```python
tasks = client.tasks.list(meeting_id="mtg_01HXN4B7KXYZ")
for task in tasks:
    print(f"{task.description} → {task.assignee or 'unassigned'}")
```

Output:
```
Update roadmap with Q2 priorities → sarah@example.com
Schedule infrastructure review → unassigned
Send follow-up to investors → james@example.com
```

---

## What Belongs in External vs Internal Docs

### External docs (`docs/external/`) — write this

- How to call an API endpoint (with examples)
- What a concept means from the user's perspective
- How to connect an agent and what it can do
- Error codes and what they mean for the caller
- Limits, quotas, pricing tiers that affect behavior
- Step-by-step integration guides

### Internal docs (`docs/technical/`, `claude_docs/`) — keep it there

- Why an architectural decision was made
- How a provider is implemented internally
- Database schema and ORM details
- CoWork automation and task queues
- Implementation patterns for Claude Code sessions
- DGX Spark deployment details

**The test:** Would a developer using Convene need this to build something?
If yes → external docs. If it's about how Convene is built internally → internal.

---

## Linking Rules

### Within a page

Use anchor links for long pages with multiple sections:
```markdown
See [Rate Limits](#rate-limits) below.
```

### Between external doc pages

Use relative paths from the current file:
```markdown
See [MCP Connection](../agents/mcp-connection.md) for auth details.
```

### To external resources

Link to official SDKs, RFC standards, or third-party docs when relevant. Do not
link to GitHub issues or internal tracking systems.

### Never link to

- `claude_docs/` — internal implementation docs
- `docs/technical/` — internal architecture docs
- `docs/milestone-testing/` — QA playbooks
- GitHub issue URLs
- Slack messages or internal notes

---

## Error Documentation

Every API reference page must document errors. For each error:
- HTTP status code
- Error code string (from the response body)
- Human-readable description
- What the caller should do

```markdown
| Status | Code | Description | Resolution |
|---|---|---|---|
| `401` | `invalid_api_key` | API key is missing or invalid | Check `CONVENE_API_KEY` |
| `403` | `meeting_access_denied` | User not authorized for this meeting | Verify the meeting ID and your account permissions |
| `404` | `meeting_not_found` | No meeting with this ID | Check the ID; the meeting may have been deleted |
| `429` | `rate_limit_exceeded` | Too many requests | Retry after the `Retry-After` header value |
```

---

## Page Length Guidelines

| Page type | Target length | Max |
|---|---|---|
| Overview | 300–500 words | 800 words |
| Getting started / quickstart | 400–700 words | 1000 words |
| Concept | 400–600 words | 900 words |
| Feature | 500–800 words | 1200 words |
| API reference (per resource) | 600–1000 words | 1500 words |
| Integration | 600–900 words | 1200 words |
| Example | 400–700 words | 1000 words |

If a page exceeds the max, split it into sub-pages and use the parent as a
navigation index.

---

## Review Checklist (before committing a doc)

Run through this for every page before committing:

**Content**
- [ ] No placeholder text anywhere on the page
- [ ] Every claim is accurate and tested against the real API
- [ ] All parameter types match what the API actually accepts
- [ ] Response examples match what the API actually returns

**Examples**
- [ ] At least one complete, runnable code example
- [ ] Expected output shown after each example
- [ ] Real-looking values (not `foo`, `bar`, `test123`)
- [ ] API keys loaded from environment variables, not hardcoded

**Structure**
- [ ] Headings are descriptive noun or verb phrases
- [ ] Related pages linked at the bottom
- [ ] No links to internal docs (`claude_docs/`, `docs/technical/`)
- [ ] New page added to `docs/external/overview.md`

**Agent-readability**
- [ ] A scan of headings reveals the page's content without reading the body
- [ ] Terminology matches the canonical Convene glossary in this file
- [ ] Code blocks have language tags
