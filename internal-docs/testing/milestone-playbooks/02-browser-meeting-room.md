# Browser Meeting Room

## Purpose
Verify the browser-based meeting room: microphone capture, WebSocket audio streaming, live transcript display, mute/unmute, and participant sidebar.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed
- [01-meeting-lifecycle.md](./01-meeting-lifecycle.md) Part A verified
- API server (8000), gateway (8003), web frontend (5173) all running
- STT provider running (Whisper endpoint or alternative)
- A microphone connected to the test machine
- Chrome or Firefox (for `getUserMedia` support)

## Step 1: Create and Start a Meeting

```bash
export MEETING_ID=$(curl -s -X POST http://localhost:8000/api/v1/meetings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "Browser Room Test",
    "platform": "kutana",
    "scheduled_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"
  }' | jq -r '.id')

curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/start \
  -H "Authorization: Bearer $TOKEN" | jq .status
```

Expected: `"active"`

## Step 2: Login to Web UI

1. Open `http://localhost:5173`
2. Log in with `tester@kutana.dev` / `TestPass123!`
3. Navigate to the Meetings page

## Step 3: Join the Meeting Room

1. Find the meeting card showing "Browser Room Test" with green **"active"** badge
2. Click **"Join Room"**
3. Browser will navigate to `/meetings/{id}/room`

## Step 4: Grant Microphone Permission

1. Browser will prompt for microphone access — click **Allow**
2. Verify the connection status indicator shows **"connected"** (top of page)
3. If it shows **"error"**, check the gateway is running on port 8003

> **Audio config:** The room captures at 16kHz mono with echo cancellation and noise suppression enabled. Audio is chunked (4096 samples), converted to Int16 PCM, base64-encoded, and sent over WebSocket.

## Step 5: Speak and Observe Transcripts

1. Speak clearly into the microphone for 10-15 seconds
2. Watch the transcript panel — segments should appear within 5-10 seconds
3. Each segment shows:
   - **Speaker name** (blue text)
   - **Timestamp** (MM:SS format)
   - **Text** — final segments in white/gray-200, interim segments in gray-400 italic

> **No transcripts appearing?** The STT provider must be running. Check the gateway terminal for errors. If using Whisper remote, verify `WHISPER_API_URL` in `.env`.

## Step 6: Test Mute/Unmute

1. Click the **Mute** button in the control bar
2. Speak — no new transcript segments should appear (audio not sent while muted)
3. Click **Unmute**
4. Speak again — transcripts should resume appearing

## Step 7: Verify Participants Sidebar

1. Check the participants sidebar on the right
2. You should see your own name with a blue avatar
3. If another user joins (from a different browser/incognito window), they appear with a gray avatar
4. Muted participants show a mute indicator

## Step 8: Leave the Meeting

1. Click the **"Leave Meeting"** button (destructive/red styling)
2. You should be redirected back to the Meetings page
3. The meeting remains active (leaving does not end the meeting)

## Step 9: Verify Meeting Can Be Ended

```bash
curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/end \
  -H "Authorization: Bearer $TOKEN" | jq .status
```

Expected: `"completed"`

## Verification Checklist

- [ ] Meeting room page loads at `/meetings/{id}/room`
- [ ] Connection status shows "connected" after joining
- [ ] Microphone permission granted successfully
- [ ] Speaking produces transcript segments within 5-10 seconds
- [ ] Final transcripts render in normal text; interim in italic
- [ ] Muting stops new transcript generation
- [ ] Unmuting resumes transcript generation
- [ ] Participants sidebar shows current user
- [ ] Leave button redirects to meetings page
- [ ] Meeting can still be ended via API after leaving

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "error" connection status | Verify gateway is running on port 8003. Check browser console for WebSocket errors |
| Microphone permission denied | Check browser settings → Site Settings → Microphone. Ensure `localhost` is allowed |
| No transcripts appearing | Check STT provider is running. Gateway logs should show `transcript.segment.final` events |
| WebSocket disconnects immediately | Check `/api/v1/token/meeting` endpoint is working. Verify `AGENT_GATEWAY_JWT_SECRET` matches between API server and gateway |
| Audio choppy or missing | Check sample rate (must be 16kHz). Some browsers need `--autoplay-policy=no-user-gesture-required` flag |
| CORS errors in console | Verify API server CORS middleware includes `http://localhost:5173` |

## Cleanup

```bash
# Meeting was already ended in Step 9
# No additional cleanup needed
```
