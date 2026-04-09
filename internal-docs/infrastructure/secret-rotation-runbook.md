# Secret Rotation Runbook

Procedure for rotating secrets used by Kutana AI services on the DGX Spark K3s cluster.

## Secrets Inventory

| Secret | Where Used | Rotation Trigger |
|--------|-----------|-----------------|
| `jwtSecret` | api-server (JWT signing) | Suspected compromise, scheduled rotation |
| `deepgramApiKey` | audio-service (STT) | Key leaked, Deepgram dashboard rotation |
| `anthropicApiKey` | agent-gateway (LLM) | Key leaked, scheduled rotation |
| `discordBotToken` | worker (Discord integration) | Token leaked, bot reset |
| `stripeSecretKey` | api-server (billing) | Key leaked, Stripe dashboard rotation |
| `stripeWebhookSecret` | api-server (webhook verify) | Endpoint recreated, key leaked |
| `slackClientId` / `slackClientSecret` | api-server (Slack OAuth) | App credentials rotated |
| `ttsCartesiaApiKey` | agent-gateway (TTS) | Key leaked, scheduled rotation |

## Rotation Procedure

### 1. Generate or Obtain the New Secret

- For API keys: rotate in the provider's dashboard (Deepgram, Anthropic, Stripe, etc.)
- For `jwtSecret`: generate a new random value:
  ```bash
  openssl rand -base64 32
  ```

### 2. Base64-Encode the New Value

Helm secrets in `values-secrets.yaml` are base64-encoded:

```bash
echo -n "your-new-secret-value" | base64
```

### 3. Transfer to DGX Securely

Never pass secrets as command-line arguments (they appear in process lists and shell history).

```bash
# Create a temporary file with the new values-secrets.yaml locally
# Then transfer via scp:
scp charts/kutana/values-secrets.yaml dgx:~/kutana-ai/charts/kutana/values-secrets.yaml
```

Alternatively, edit directly on DGX:

```bash
ssh dgx
vi ~/kutana-ai/charts/kutana/values-secrets.yaml
# Paste the new base64-encoded value, save, exit
```

### 4. Deploy with Updated Secrets

```bash
# From local machine (kubectl/helm target DGX K3s directly):
helm upgrade --install kutana charts/kutana \
  -n kutana \
  --create-namespace \
  -f charts/kutana/values-secrets.yaml
```

### 5. Verify the Rotation

```bash
# Check pods restarted with new config
kubectl get pods -n kutana -w

# Check service health
kubectl logs -n kutana deploy/api-server --tail=50

# Verify the old key no longer works (provider-specific)
# Verify the new key works by hitting a health endpoint or running a smoke test
```

### 6. Clean Up

- **Delete local copies** of `values-secrets.yaml` if they were created temporarily
- **Revoke the old key** in the provider's dashboard (if not already done)
- **Confirm** `values-secrets.yaml` is in `.gitignore` (it is — see line 60)

## Emergency Rotation (Key Leaked)

If a secret was committed to git or otherwise exposed:

1. **Immediately revoke** the old key in the provider's dashboard
2. Generate a new key (Step 1 above)
3. Deploy the new key (Steps 2-5 above)
4. **Audit git history**: check if the secret is in any commit
   ```bash
   gitleaks detect --source . --verbose
   ```
5. If the secret is in git history, consider:
   - Running `git filter-repo` to remove it (coordinate with team)
   - Or accepting the history leak and ensuring the key is revoked
6. Update `.gitleaks-baseline.json` if the historical finding is accepted:
   ```bash
   gitleaks detect --source . --baseline-path .gitleaks-baseline.json --report-path .gitleaks-baseline.json
   ```

## Schedule

| Secret | Rotation Frequency |
|--------|--------------------|
| `jwtSecret` | Every 90 days or on compromise |
| API keys (Deepgram, Anthropic, Cartesia) | Every 90 days or on compromise |
| `stripeSecretKey` / `stripeWebhookSecret` | On compromise only (Stripe manages expiry) |
| `discordBotToken` | On compromise only |
| Database passwords | Every 180 days or on compromise |

## Do NOT

- Pass secrets as CLI arguments (`--set secrets.anthropicApiKey=sk-...`) — they appear in `ps` output
- Commit `values-secrets.yaml` to git — it is gitignored for a reason
- Store secrets in Slack, email, or any unencrypted channel
- Use the same secret across environments (dev vs. production)
