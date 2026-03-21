# Convene CLI

## Purpose
Verify all CLI commands end-to-end: login, status, agents (create/list), meetings (create/list), keys (generate), and logout.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed
- API server running on port 8000
- Test user registered (`tester@convene.dev` / `TestPass123!`)
- CLI installed via workspace (`uv sync --all-packages`)

## Step 1: Verify CLI Installation

```bash
uv run convene --help
```

Expected output shows top-level commands:
```
Usage: convene [OPTIONS] COMMAND [ARGS]...

Commands:
  login     Authenticate and store credentials
  status    Show current authentication status
  logout    Clear stored credentials
  agents    Manage agents
  meetings  Manage meetings
  keys      Manage API keys
```

## Step 2: Login

```bash
uv run convene login
```

When prompted:
- Email: `tester@convene.dev`
- Password: `TestPass123!`

Expected output:
```
✓ Logged in as tester@convene.dev
```

> Use `--api-url http://localhost:8000` if the default doesn't connect.

## Step 3: Check Status

```bash
uv run convene status
```

Expected output shows authenticated user info:
```
✓ Authenticated
  User: Test User
  Email: tester@convene.dev
  API URL: http://localhost:8000
```

## Step 4: Create an Agent

```bash
uv run convene agents create "CLI Test Agent" -p "You are a test agent created via CLI."
```

Expected: Rich-formatted output showing agent details with ID, name, and capabilities.

Save the agent ID from the output for Step 7.

## Step 5: List Agents

```bash
uv run convene agents list
```

Expected: Rich table output showing:
```
┌──────────────────────────────────────┬─────────────────┬──────────────┬──────────────────────┐
│ ID                                   │ Name            │ Capabilities │ Created              │
├──────────────────────────────────────┼─────────────────┼──────────────┼──────────────────────┤
│ <uuid>                               │ CLI Test Agent  │ ...          │ 2026-03-07T...       │
└──────────────────────────────────────┴─────────────────┴──────────────┴──────────────────────┘
```

## Step 6: Create a Meeting

```bash
uv run convene meetings create "CLI Test Meeting"
```

Expected: Meeting details with ID, title, status "scheduled", and scheduled time.

```bash
# Create with custom time
uv run convene meetings create "Future Meeting" --at "2026-03-08T14:00:00"
```

## Step 7: List Meetings

```bash
uv run convene meetings list
```

Expected: Rich table with columns: ID, Title, Status, Scheduled.

## Step 8: Generate API Key

```bash
# Use the agent ID from Step 4
uv run convene keys generate <AGENT_ID>
```

Expected:
```
✓ API Key generated
  Key: cvn_...
  Name: default

  ⚠ Save this key — it won't be shown again!
```

```bash
# With custom name
uv run convene keys generate <AGENT_ID> -n "named-key"
```

## Step 9: Logout

```bash
uv run convene logout
```

Expected:
```
✓ Logged out
```

## Step 10: Verify Auth Required After Logout

```bash
uv run convene agents list
```

Expected: Error message indicating authentication is required.

```bash
uv run convene status
```

Expected: Shows "Not authenticated" or similar.

## Step 11: Re-login for Subsequent Tests

```bash
uv run convene login
# Email: tester@convene.dev
# Password: TestPass123!
```

## Verification Checklist

- [ ] `convene --help` shows all commands
- [ ] `convene login` authenticates successfully
- [ ] `convene status` shows authenticated user info
- [ ] `convene agents create` creates agent with name and prompt
- [ ] `convene agents list` shows table of agents
- [ ] `convene meetings create` creates meeting
- [ ] `convene meetings create --at` accepts custom datetime
- [ ] `convene meetings list` shows table of meetings
- [ ] `convene keys generate` returns raw key starting with `cvn_`
- [ ] `convene keys generate -n` accepts custom key name
- [ ] `convene logout` clears credentials
- [ ] Commands after logout fail with auth error
- [ ] `convene login` works again after logout

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `command not found: convene` | Run `UV_LINK_MODE=copy uv sync --all-packages` to install CLI entry point |
| Login fails with connection error | Verify API server is running. Use `--api-url http://localhost:8000` |
| `Invalid credentials` | Verify user was registered in 00-SETUP.md Step 7 |
| Rich tables garbled | Terminal must support Unicode. Try a different terminal emulator |
| Keys generate fails with 404 | Ensure the agent ID is correct (UUID from Step 4) |

## Cleanup

```bash
# Re-login if you logged out in Step 9
uv run convene login
```
