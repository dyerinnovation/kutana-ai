# Discord Bot Setup for Kutana Feeds

This guide walks through creating a Discord bot and deploying its token so the Kutana worker can send/receive messages via Discord feeds.

## Architecture

Kutana uses the [official Claude Discord channel plugin](https://github.com/anthropics/claude-plugins-official/tree/main/external_plugins/discord) — an MCP server that communicates over stdio. The worker spawns it as a subprocess for each Discord feed run and passes the bot token via environment variable.

```
Worker pod → ClaudeCodeChannelAdapter → bun plugins/discord/server.ts (stdio MCP) → Discord API
```

## Prerequisites

- A Discord account
- A Discord server (guild) where you have admin/manage permissions
- Access to the DGX Spark K3s cluster

## Step 1: Create a Discord Application

1. Go to https://discord.com/developers/applications
2. Click **New Application**
3. Name it (e.g., "Kutana Bot") and click **Create**

## Step 2: Create the Bot

1. In the application settings, go to the **Bot** tab
2. Click **Add Bot** (if not already created)
3. Under **Privileged Gateway Intents**, enable:
   - **Server Members Intent** (optional, for member lookups)
   - **Message Content Intent** (required — the bot reads message content)
4. Click **Save Changes**

## Step 3: Copy the Bot Token

1. On the **Bot** tab, click **Reset Token**
2. Copy the token immediately — you won't see it again
3. This is your `DISCORD_BOT_TOKEN`

> **Security:** Never commit the token to git. It goes in Helm secrets only.

## Step 4: Set Bot Permissions

1. Go to the **OAuth2** tab
2. Click **URL Generator**
3. Under **Scopes**, select: `bot`
4. Under **Bot Permissions**, select:
   - Send Messages
   - Read Messages / View Channels
   - Read Message History
   - Add Reactions
   - Manage Messages (optional, for edit operations)
5. Copy the generated URL

## Step 5: Invite the Bot to Your Server

1. Open the generated URL in your browser
2. Select your Discord server from the dropdown
3. Click **Authorize**
4. The bot should now appear in your server's member list (offline until the worker connects)

## Step 6: Deploy the Token

Base64-encode the token and deploy via Helm:

```bash
# Encode the token
TOKEN_B64=$(echo -n 'YOUR_DISCORD_BOT_TOKEN_HERE' | base64)

# Deploy with the token
ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
  /home/jondyer3/.local/bin/helm upgrade --install kutana charts/kutana \
  -n kutana --set secrets.discordBotToken='"$TOKEN_B64"''
```

Or set it directly in `charts/kutana/values.yaml` under `secrets.discordBotToken` (base64-encoded).

The worker pod reads `DISCORD_BOT_TOKEN` from the Kubernetes secret and passes it to the Discord plugin subprocess.

## Step 7: Create a Discord Feed

Use the Kutana API to create a feed targeting your Discord channel:

```bash
curl -X POST https://kutana.spark-b0f2.local/api/feeds \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Discord Alerts",
    "platform": "discord",
    "channel_name": "kutana-alerts",
    "direction": "outbound",
    "data_types": ["summary", "tasks"],
    "trigger": "meeting_end"
  }'
```

Store the bot token as a feed secret:

```bash
curl -X PUT https://kutana.spark-b0f2.local/api/feeds/<feed-id>/secret \
  -H "Authorization: Bearer <your-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"token": "YOUR_DISCORD_BOT_TOKEN_HERE"}'
```

## Step 8: Verify

1. Check the worker pod is running:
   ```bash
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
     kubectl get pods -n kutana -l app.kubernetes.io/name=worker'
   ```

2. Trigger a test feed run and check worker logs:
   ```bash
   ssh dgx 'echo JDf33nawm3! | sudo -S env KUBECONFIG=/etc/rancher/k3s/k3s.yaml \
     kubectl logs -n kutana deploy/worker --tail=50'
   ```

3. Verify the message appears in your Discord channel

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `DISCORD_BOT_TOKEN required` | Token not in env | Check Helm secret, redeploy |
| `Disallowed intents` | Message Content Intent not enabled | Enable in Discord Developer Portal > Bot > Intents |
| `Missing Access` | Bot not in server or missing channel perms | Re-invite with correct permissions |
| `Stdio MCP server closed stdout` | Plugin crash | Check worker logs for stderr output |
