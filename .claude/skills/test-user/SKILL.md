---
name: test-user
description: Show or create test user credentials for Convene AI. TRIGGER on: test credentials, test user, test account, login credentials, demo user, get API key.
permissions:
  - Bash(curl:*)
  - Bash(ssh:*)
---

# Test User

Shows existing test credentials or creates a new test user via the Convene API.

## Usage

```bash
# Show existing test user credentials
bash .claude/skills/test-user/scripts/test-user.sh

# Create a fresh test user
bash .claude/skills/test-user/scripts/test-user.sh --create
```

## Output

Prints:
- Email and password for browser login
- JWT token for API testing
- API key for agent/MCP authentication

## Test Accounts

| Account | Email | Purpose |
|---|---|---|
| Free tier | `test-free@convene.test` | Test free plan limits |
| Pro tier | `test-pro@convene.test` | Test Pro features |
| Business tier | `test-biz@convene.test` | Test Business features |
