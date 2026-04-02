# Kutana CLI

## Purpose
Verify all CLI commands end-to-end: login, status, agents (create/list), meetings (create/list), keys (generate), and logout.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed
- API server running on port 8000
- Test user registered (`tester@kutana.dev` / `TestPass123!`)
- CLI installed via workspace (`uv sync --all-packages`)

## Step 1: Verify CLI Installation

```bash
uv run kutana --help
```

Expected output shows top-level commands:
```
Usage: kutana [OPTIONS] COMMAND [ARGS]...

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
uv run kutana login
```

When prompted:
- Email: `tester@kutana.dev`
- Password: `TestPass123!`

Expected output:
```
✓ Logged in as tester@kutana.dev
```

> Use `--api-url http://localhost:8000` if the default doesn't connect.

## Step 3: Check Status

```bash
uv run kutana status
```

Expected output shows authenticated user info:
```
✓ Authenticated
  User: Test User
  Email: tester@kutana.dev
  API URL: http://localhost:8000
```

## Step 4: Create an Agent

```bash
uv run kutana agents create "CLI Test Agent" -p "You are a test agent created via CLI."
```

Expected: Rich-formatted output showing agent details with ID, name, and capabilities.

Save the agent ID from the output for Step 7.

## Step 5: List Agents

```bash
uv run kutana agents list
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
uv run kutana meetings create "CLI Test Meeting"
```

Expected: Meeting details with ID, title, status "scheduled", and scheduled time.

```bash
# Create with custom time
uv run kutana meetings create "Future Meeting" --at "2026-03-08T14:00:00"
```

## Step 7: List Meetings

```bash
uv run kutana meetings list
```

Expected: Rich table with columns: ID, Title, Status, Scheduled.

## Step 8: Generate API Key

```bash
# Use the agent ID from Step 4
uv run kutana keys generate <AGENT_ID>
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
uv run kutana keys generate <AGENT_ID> -n "named-key"
```

## Step 9: Logout

```bash
uv run kutana logout
```

Expected:
```
✓ Logged out
```

## Step 10: Verify Auth Required After Logout

```bash
uv run kutana agents list
```

Expected: Error message indicating authentication is required.

```bash
uv run kutana status
```

Expected: Shows "Not authenticated" or similar.

## Step 11: Re-login for Subsequent Tests

```bash
uv run kutana login
# Email: tester@kutana.dev
# Password: TestPass123!
```

## Verification Checklist

- [ ] `kutana --help` shows all commands
- [ ] `kutana login` authenticates successfully
- [ ] `kutana status` shows authenticated user info
- [ ] `kutana agents create` creates agent with name and prompt
- [ ] `kutana agents list` shows table of agents
- [ ] `kutana meetings create` creates meeting
- [ ] `kutana meetings create --at` accepts custom datetime
- [ ] `kutana meetings list` shows table of meetings
- [ ] `kutana keys generate` returns raw key starting with `cvn_`
- [ ] `kutana keys generate -n` accepts custom key name
- [ ] `kutana logout` clears credentials
- [ ] Commands after logout fail with auth error
- [ ] `kutana login` works again after logout

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `command not found: kutana` | Run `UV_LINK_MODE=copy uv sync --all-packages` to install CLI entry point |
| Login fails with connection error | Verify API server is running. Use `--api-url http://localhost:8000` |
| `Invalid credentials` | Verify user was registered in 00-SETUP.md Step 7 |
| Rich tables garbled | Terminal must support Unicode. Try a different terminal emulator |
| Keys generate fails with 404 | Ensure the agent ID is correct (UUID from Step 4) |

## Cleanup

```bash
# Re-login if you logged out in Step 9
uv run kutana login
```
