# Pre-Release Smoke Test Playbook

> **Target:** Run before every release candidate or production deploy.
> **Pass criteria:** All CLI gates green, all Playwright browser tests pass, all manual checks verified.
> **Estimated time:** ~45 minutes (CLI: 5 min, Playwright: 15 min, Manual: 25 min)

## Prerequisites

- [00-SETUP.md](./00-SETUP.md) completed (infrastructure running)
- API server, agent gateway, MCP server running (local or DGX)
- Frontend dev server running (`cd web && pnpm dev`)
- Test credentials: `test-ui@kutana.ai` / `KutanaTest2026`
- Playwright installed: `cd web && npx playwright install`
- Sentry project configured (for M-01)
- Stripe test mode enabled (for M-04)

---

## Section 1: CLI Gates

Run these from the repo root. All must pass before proceeding to browser tests.

### CLI-01: Ruff Formatting

```bash
uv run ruff format --check .
```

**Pass:** Exit code 0, no files would be reformatted.

### CLI-02: Ruff Linting

```bash
uv run ruff check .
```

**Pass:** Exit code 0, no lint violations.

### CLI-03: Mypy Type Checking

```bash
uv run mypy --strict packages/ services/
```

**Pass:** Exit code 0, `Success: no issues found`.

### CLI-04: Pytest (Backend)

```bash
uv run pytest services/api-server/tests/ -x -v
```

**Pass:** All tests pass, exit code 0.

### CLI-05: TypeScript Type Checking

```bash
cd web && npx tsc --noEmit
```

**Pass:** Exit code 0, no type errors.

### CLI Gates Checklist

- [ ] CLI-01: `ruff format --check` passes
- [ ] CLI-02: `ruff check` passes
- [ ] CLI-03: `mypy --strict` passes
- [ ] CLI-04: `pytest` passes
- [ ] CLI-05: `tsc --noEmit` passes

---

## Section 2: Playwright Browser Tests

Run the full Playwright suite or individual tests. All tests target `http://localhost:5173` (or the deployed URL).

```bash
cd web && npx playwright test
```

To run a single test:
```bash
cd web && npx playwright test -g "PW-01"
```

### Public Pages

#### PW-01: Landing Page Renders

- Navigate to `/`
- **Assert:** Page loads with the Kutana logo, hero section, and feature cards visible.
- **Assert:** "Get Started" and "Sign In" CTAs are present and clickable.
- **Assert:** No console errors.

#### PW-02: Pricing Page Renders

- Navigate to `/pricing`
- **Assert:** All 4 tier cards visible (Basic, Pro, Business, Enterprise).
- **Assert:** Each card shows price, feature list, and CTA button.
- **Assert:** Toggle between monthly/annual pricing works.

#### PW-03: 404 Page

- Navigate to `/this-page-does-not-exist`
- **Assert:** 404 page renders with "Page Not Found" message.
- **Assert:** "Go Home" link navigates back to `/`.

### Auth Flows

#### PW-04: Login Page Renders

- Navigate to `/login`
- **Assert:** Email and password fields visible.
- **Assert:** "Sign In" button is present and initially disabled (empty fields).
- **Assert:** "Forgot password?" and "Register" links visible.

#### PW-05: Login with Valid Credentials

- Navigate to `/login`
- Fill email: `test-ui@kutana.ai`, password: `KutanaTest2026`
- Click "Sign In"
- **Assert:** Redirected to `/` (dashboard).
- **Assert:** Sidebar navigation visible with user name.

#### PW-06: Login with Invalid Credentials

- Navigate to `/login`
- Fill email: `test-ui@kutana.ai`, password: `WrongPassword123`
- Click "Sign In"
- **Assert:** Error toast or inline message appears: "Invalid email or password".
- **Assert:** Remains on `/login`.

#### PW-07: Register Page Renders

- Navigate to `/register`
- **Assert:** Name, email, password, and confirm password fields visible.
- **Assert:** "Create Account" button present.

#### PW-08: Forgot Password Flow

- Navigate to `/forgot-password`
- Fill email: `test-ui@kutana.ai`
- Click "Send Reset Link"
- **Assert:** Success message: "Check your email for a reset link" (or similar).
- **Assert:** No server error.

#### PW-09: Verify Email Page

- Navigate to `/verify-email?token=invalid-token`
- **Assert:** Page renders without crash.
- **Assert:** Shows error or "invalid token" message.

#### PW-10: Logout

- Log in as test user (PW-05)
- Click user menu → "Sign Out"
- **Assert:** Redirected to landing page `/`.
- **Assert:** Navigating to `/agents` redirects back to `/login`.

### Authenticated App

#### PW-11: Dashboard Loads

- Log in as test user
- **Assert:** Dashboard page renders at `/`.
- **Assert:** Recent meetings section visible (may be empty).
- **Assert:** Quick-action buttons (New Meeting, View Agents) visible.

#### PW-12: Agents Page

- Navigate to `/agents`
- **Assert:** Page renders with agent list (or empty state).
- **Assert:** "Create Agent" button visible.
- **Assert:** If managed templates exist, template cards render with names and descriptions.

#### PW-13: Agent Templates Page

- Navigate to `/templates`
- **Assert:** Template cards render with name, description, category.
- **Assert:** "Activate" button visible on each card.
- **Assert:** Premium templates show tier badge.

#### PW-14: Meetings Page

- Navigate to `/meetings`
- **Assert:** Page renders with meeting list (or empty state).
- **Assert:** "New Meeting" button visible.

#### PW-15: Create Meeting Flow

- Navigate to `/meetings`
- Click "New Meeting"
- Fill in meeting title: "Smoke Test Meeting"
- Submit the form
- **Assert:** Meeting created and appears in the meeting list.
- **Assert:** Meeting status shows "scheduled".

#### PW-16: Meeting Room Page

- Create a meeting (PW-15) and open it
- Navigate to `/meetings/<id>/room`
- **Assert:** Meeting room layout renders (chat panel, participant list, controls).
- **Assert:** No WebSocket connection errors in console.

#### PW-17: Profile Page

- Navigate to `/settings/profile`
- **Assert:** User name and email displayed.
- **Assert:** Edit form fields are populated with current values.

#### PW-18: Billing Page

- Navigate to `/settings/billing`
- **Assert:** Current plan displayed.
- **Assert:** Upgrade options or Stripe portal link visible.

### API Smoke

#### PW-19: API Health Check

- Fetch `GET /api/v1/health` from the browser (or via Playwright request context)
- **Assert:** Response `200` with `{"status": "healthy", "service": "api-server"}`.
- Fetch `GET /gateway/health`
- **Assert:** Response `200` with `{"status": "healthy", "service": "agent-gateway"}`.

### Playwright Checklist

- [ ] PW-01: Landing page renders
- [ ] PW-02: Pricing page renders
- [ ] PW-03: 404 page works
- [ ] PW-04: Login page renders
- [ ] PW-05: Login with valid credentials
- [ ] PW-06: Login with invalid credentials
- [ ] PW-07: Register page renders
- [ ] PW-08: Forgot password flow
- [ ] PW-09: Verify email page
- [ ] PW-10: Logout flow
- [ ] PW-11: Dashboard loads
- [ ] PW-12: Agents page
- [ ] PW-13: Agent templates page
- [ ] PW-14: Meetings page
- [ ] PW-15: Create meeting flow
- [ ] PW-16: Meeting room page
- [ ] PW-17: Profile page
- [ ] PW-18: Billing page
- [ ] PW-19: API health check

---

## Section 3: Manual Verification

These checks require manual interaction or external service access.

### M-01: Sentry Error Tracking

1. Trigger a client-side error (e.g., navigate to a broken route or use browser devtools to throw)
2. Open the Sentry dashboard for the Kutana project
3. **Verify:** The error appears in Sentry within 30 seconds with correct source maps, stack trace, and environment tag.

**Pass:** Error captured with readable stack trace and correct release tag.

### M-02: Voice Agent / TTS

1. Log in and create a meeting
2. Activate a managed agent with TTS capability (or connect a custom agent with `capabilities: ["tts_enabled"]`)
3. The agent calls `kutana_speak` with a test message
4. **Verify:** Audio plays in the browser meeting room.
5. **Verify:** Agent appears in the participant list with correct name.

**Pass:** TTS audio is audible, no distortion, correct agent attribution.

### M-03: Stripe Subscription Flow

1. Navigate to `/pricing`
2. Click "Subscribe" on the Pro tier
3. Complete Stripe Checkout using test card: `4242 4242 4242 4242`, any future expiry, any CVC
4. **Verify:** Redirected back to the app with Pro tier active.
5. Navigate to `/settings/billing`
6. **Verify:** Current plan shows "Pro".
7. **Verify:** Stripe dashboard shows the test subscription.

**Pass:** Subscription created, tier upgraded, billing page reflects new plan.

### M-04: Stripe Webhook Processing

1. After completing M-03, check the API server logs for webhook events
2. **Verify:** `invoice.payment_succeeded` and `checkout.session.completed` events processed.
3. Trigger a subscription cancellation from `/settings/billing`
4. **Verify:** `customer.subscription.updated` webhook received and user tier downgraded.

**Pass:** All webhook events processed without errors.

### M-05: Email Delivery

1. Register a new test account with a real email address (or check a mail trap)
2. **Verify:** Welcome/verification email arrives within 2 minutes.
3. Use "Forgot Password" flow with the same email
4. **Verify:** Password reset email arrives within 2 minutes.
5. **Verify:** Reset link works and redirects to the password reset form.

**Pass:** Both emails delivered with correct content and working links.

### M-06: Open Graph / Social Previews

1. Paste the landing page URL into the [Facebook Sharing Debugger](https://developers.facebook.com/tools/debug/) or [Twitter Card Validator](https://cards-dev.twitter.com/validator)
2. **Verify:** OG title, description, and image render correctly.
3. **Verify:** No missing `og:` or `twitter:` meta tags.
4. Check `/pricing` page as well.

**Pass:** Social preview cards render with correct branding and content.

### M-07: Turn Management (Multi-Participant)

1. Open the meeting room in two browser tabs (same meeting, same user — or two users)
2. In Tab 1: raise hand
3. In Tab 2: verify the speaker queue updates in real time
4. In Tab 1: finish speaking
5. In Tab 2: verify queue advances
6. Connect an agent via MCP and have it call `kutana_raise_hand`
7. **Verify:** Agent appears in the queue in the browser UI.

**Pass:** Queue updates propagate to all participants within 500ms, agent turns work correctly.

### Manual Verification Checklist

- [ ] M-01: Sentry captures errors with source maps
- [ ] M-02: Voice agent TTS audio plays in browser
- [ ] M-03: Stripe subscription flow completes
- [ ] M-04: Stripe webhooks processed correctly
- [ ] M-05: Emails delivered (verification + password reset)
- [ ] M-06: OG tags render in social debuggers
- [ ] M-07: Turn management works across participants

---

## Final Checklist

- [ ] All CLI gates pass (CLI-01 through CLI-05)
- [ ] All Playwright tests pass (PW-01 through PW-19)
- [ ] All manual checks verified (M-01 through M-07)
- [ ] No ERROR-level entries in service logs during testing
- [ ] Release candidate is ready for deploy

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Playwright tests timeout | Ensure frontend dev server is running on port 5173 |
| Login test fails | Verify test user exists: check `testing/test-human-creds.md` |
| TTS test has no audio | Check `STT_PROVIDER` and TTS provider config in `.env` |
| Stripe checkout fails | Ensure `STRIPE_SECRET_KEY` is set to test mode key |
| Emails not arriving | Check email provider config; try mail trap for local testing |
| Sentry not capturing | Verify `SENTRY_DSN` is set in the frontend `.env` |
| Type check fails on web | Run `cd web && pnpm install` first to ensure deps are current |
