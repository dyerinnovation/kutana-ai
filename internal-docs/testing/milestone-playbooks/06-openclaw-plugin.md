# OpenClaw Plugin

## Purpose
Verify the OpenClaw plugin: build, install, configure, and test all 6 tool calls against a live Kutana instance.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed
- [03-mcp-auth-flow.md](./03-mcp-auth-flow.md) verified (API key → MCP token works)
- `$API_KEY` exported (valid, non-expired, non-revoked)
- API server (8000) and MCP server (3001) running
- Node.js 18+ installed
- OpenClaw desktop application installed

## Step 1: Build the Plugin

```bash
cd integrations/openclaw-plugin
npm install
npm run build
```

Expected: Build completes without errors, `dist/index.js` is created.

```bash
ls -la dist/index.js
```

Expected: File exists with recent timestamp.

## Step 2: Verify Plugin Manifest

```bash
cat openclaw.plugin.json
```

Expected:
```json
{
  "name": "kutana",
  "version": "0.1.0",
  "description": "...",
  "entry": "dist/index.js",
  "skills": ["skills/kutana"],
  "config": {
    "apiKey": { "type": "string", "required": true, "description": "..." },
    "mcpUrl": { "type": "string", "default": "http://localhost:3001/mcp", "description": "..." }
  }
}
```

## Step 3: Install in OpenClaw

1. Open OpenClaw desktop application
2. Navigate to **Settings → Plugins**
3. Click **"Install Local Plugin"** (or drag the plugin folder)
4. Point to the `integrations/openclaw-plugin` directory
5. Configure:
   - **apiKey:** Paste your `$API_KEY` value (starts with `cvn_`)
   - **mcpUrl:** `http://localhost:3001/mcp` (default)
6. Click **Save / Enable**

## Step 4: Create a Test Meeting (if needed)

```bash
export MEETING_ID=$(curl -s -X POST http://localhost:8000/api/v1/meetings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "OpenClaw Plugin Test",
    "platform": "kutana",
    "scheduled_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"
  }' | jq -r '.id')

curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/start \
  -H "Authorization: Bearer $TOKEN" > /dev/null

echo "MEETING_ID=$MEETING_ID"
```

## Step 5: Test `kutana_list_meetings`

In OpenClaw, invoke:
> "List my Kutana meetings"

The plugin should call `kutana_list_meetings` (no parameters).

Expected: Returns JSON array of meetings including "OpenClaw Plugin Test" with status "active".

## Step 6: Test `kutana_create_meeting`

In OpenClaw, invoke:
> "Create a new Kutana meeting called 'Plugin Created Meeting'"

The plugin should call `kutana_create_meeting` with `title: "Plugin Created Meeting"`.

Expected: Returns new meeting object with ID and status "scheduled".

## Step 7: Test `kutana_join_meeting`

In OpenClaw, invoke:
> "Join meeting {MEETING_ID}"

The plugin should call `kutana_join_meeting` with the meeting ID.

Expected: Returns join confirmation with room name and granted capabilities.

## Step 8: Test `kutana_get_transcript`

In OpenClaw, invoke:
> "Get the latest transcript"

The plugin should call `kutana_get_transcript` (default: last 50 segments).

Expected: Returns transcript segments array (may be empty if no audio has been streamed).

## Step 9: Test `kutana_create_task`

In OpenClaw, invoke:
> "Create a task for meeting {MEETING_ID}: Review plugin integration — priority high"

The plugin should call `kutana_create_task` with:
- `meeting_id`: the meeting ID
- `description`: "Review plugin integration"
- `priority`: "high"

Expected: Returns created task object with ID and priority.

## Step 10: Test `kutana_get_participants`

In OpenClaw, invoke:
> "Who's in the meeting?"

The plugin should call `kutana_get_participants` (no parameters).

Expected: Returns participant list including the agent that joined in Step 7.

## Step 11: Verify Error Handling

1. **Invalid API key:** Change plugin config to use `cvn_invalid_key`
2. Try "List my Kutana meetings"
3. Expected: Plugin reports authentication error

4. **Restore valid API key** in plugin settings

## Verification Checklist

- [ ] `npm run build` succeeds, `dist/index.js` created
- [ ] Plugin manifest matches expected schema
- [ ] Plugin installs in OpenClaw without errors
- [ ] `kutana_list_meetings` returns meeting list
- [ ] `kutana_create_meeting` creates a new meeting
- [ ] `kutana_join_meeting` joins an active meeting
- [ ] `kutana_get_transcript` returns transcript (or empty array)
- [ ] `kutana_create_task` creates task with correct priority
- [ ] `kutana_get_participants` returns participant list
- [ ] Invalid API key produces clear error message

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `npm run build` fails | Check Node.js version (18+). Run `npm install` first |
| Plugin not appearing in OpenClaw | Verify `openclaw.plugin.json` is valid JSON. Check OpenClaw plugin directory |
| "Authentication failed" on all tools | Verify API key is valid (not expired/revoked). Check MCP server is running on port 3001 |
| "Connection refused" | Verify MCP server URL in plugin config. Default: `http://localhost:3001/mcp` |
| Join meeting fails | Ensure meeting is in "active" status (start it first) |
| Empty transcript | Expected if no audio has been streamed to the meeting |

## Cleanup

```bash
# End the test meeting
curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/end \
  -H "Authorization: Bearer $TOKEN" > /dev/null
```
