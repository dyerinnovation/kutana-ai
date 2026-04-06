---
name: stripe-webhook
description: Start a Stripe webhook forwarder against the DGX api-server for end-to-end billing testing. TRIGGER on: stripe webhook, test webhook, stripe listen, forward stripe events.
permissions:
  - Bash(stripe:*)
  - Bash(kubectl:*)
  - Bash(helm:*)
  - Bash(pkill:*)
  - Bash(curl:*)
---

# Stripe Webhook Forwarder

Starts a local Stripe CLI webhook listener that forwards events to the DGX api-server
for end-to-end billing testing. Uses `kubectl port-forward` to reach the api-server pod
and `stripe listen` to receive events from Stripe's test-mode dashboard.

## Steps

### 1. Preflight — Stripe CLI

```bash
which stripe
```

If missing, tell the user:
```
Install the Stripe CLI: brew install stripe/stripe-cli/stripe
Then run: stripe login
```

Check login status:
```bash
stripe config --list 2>&1 | grep -q test_mode
```

If no `test_mode_api_key`, instruct the user to run `! stripe login` (interactive, opens
browser) and then retry this skill.

### 2. Port-forward to api-server

Start a background port-forward so `stripe listen` can reach the api-server:

```bash
kubectl port-forward -n kutana svc/api-server 18000:8000 &
PF_PID=$!
```

Verify it's reachable:
```bash
curl -fsS http://localhost:18000/health
```

If the curl fails, kill `$PF_PID` and report the error.

### 3. Start the webhook forwarder

```bash
stripe listen \
  --forward-to http://localhost:18000/v1/billing/webhook \
  --events checkout.session.completed,customer.subscription.created,customer.subscription.updated,customer.subscription.deleted,customer.subscription.trial_will_end,invoice.payment_failed,invoice.paid
```

On startup, the CLI prints: `Your webhook signing secret is whsec_xxx`.
Capture the `whsec_…` value from stdout.

### 4. Sync signing secret (first run only)

Compare the captured `whsec_…` against the current value in
`charts/kutana/values-secrets.yaml` (`secrets.stripeWebhookSecret`).

If different:
1. Base64-encode the new value and update `values-secrets.yaml`
2. Helm upgrade:
   ```bash
   helm upgrade --install kutana charts/kutana -n kutana -f charts/kutana/values-secrets.yaml
   ```
3. Restart api-server to pick up the new secret:
   ```bash
   kubectl rollout restart deploy/api-server -n kutana
   kubectl rollout status deploy/api-server -n kutana --timeout=90s
   ```
4. Re-establish the port-forward (the restart kills it):
   ```bash
   kubectl port-forward -n kutana svc/api-server 18000:8000 &
   PF_PID=$!
   ```

### 5. Verification

From a separate terminal (or tell the user to run these):

```bash
# Fire a synthetic event
stripe trigger checkout.session.completed

# Check api-server logs for handling
kubectl logs -n kutana deploy/api-server --tail=20 | grep "Stripe webhook"
```

### 6. Cleanup

When done testing (or on `/stripe-webhook stop`):

```bash
kill $PF_PID 2>/dev/null
# stripe listen exits on Ctrl-C
```

## Testing Commands

Once the forwarder is running, trigger test events:

| Command | What it tests |
|---------|--------------|
| `stripe trigger checkout.session.completed` | New subscription created |
| `stripe trigger customer.subscription.updated` | Plan change / renewal |
| `stripe trigger customer.subscription.deleted` | Subscription canceled |
| `stripe trigger customer.subscription.trial_will_end` | Trial ending reminder |
| `stripe trigger invoice.payment_failed` | Payment failure handling |
| `stripe trigger invoice.paid` | Successful payment / cycle reset |

## Notes

- The `whsec_…` signing secret from `stripe listen` is **different** from the
  production webhook secret in the Stripe dashboard. The CLI uses its own
  signing key for forwarded events.
- For production webhooks, register `https://api-dev.kutana.ai/v1/billing/webhook`
  in the Stripe dashboard and use that endpoint's signing secret instead.
- Port 18000 is used to avoid conflicts with anything on 8000.
