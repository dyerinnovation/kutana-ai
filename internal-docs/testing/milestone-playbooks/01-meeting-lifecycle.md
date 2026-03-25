# Meeting Lifecycle

## Purpose
Verify the full meeting CRUD and state machine: create, list, update, start, end, and invalid transitions.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed
- `$TOKEN` exported (user JWT)
- API server running on port 8000

## Part A — API Testing

### Step 1: Create a Meeting

```bash
export MEETING_ID=$(curl -s -X POST http://localhost:8000/api/v1/meetings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "Lifecycle Test Meeting",
    "platform": "convene",
    "scheduled_at": "'"$(date -u -v+1H +%Y-%m-%dT%H:%M:%SZ)"'"
  }' | jq -r '.id')

echo "MEETING_ID=$MEETING_ID"
```

Expected response (201):
```json
{
  "id": "<uuid>",
  "platform": "convene",
  "title": "Lifecycle Test Meeting",
  "status": "scheduled",
  "scheduled_at": "...",
  "started_at": null,
  "ended_at": null
}
```

### Step 2: List Meetings

```bash
curl -s http://localhost:8000/api/v1/meetings \
  -H "Authorization: Bearer $TOKEN" | jq .
```

Expected response (200):
```json
{
  "items": [ { "id": "...", "title": "Lifecycle Test Meeting", "status": "scheduled", ... } ],
  "total": 1
}
```

### Step 3: Get Single Meeting

```bash
curl -s http://localhost:8000/api/v1/meetings/$MEETING_ID \
  -H "Authorization: Bearer $TOKEN" | jq .
```

Expected: 200 with matching meeting object.

### Step 4: Update Meeting

```bash
curl -s -X PATCH http://localhost:8000/api/v1/meetings/$MEETING_ID \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "Updated Lifecycle Test"}' | jq .
```

Expected: 200 with `"title": "Updated Lifecycle Test"`.

### Step 5: Start Meeting

```bash
curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/start \
  -H "Authorization: Bearer $TOKEN" | jq .
```

Expected: 200 with `"status": "active"` and `"started_at"` set.

### Step 6: Verify Double-Start Rejected (409)

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/start \
  -H "Authorization: Bearer $TOKEN"
```

Expected: `409` (meeting already active).

### Step 7: End Meeting

```bash
curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/end \
  -H "Authorization: Bearer $TOKEN" | jq .
```

Expected: 200 with `"status": "completed"` and `"ended_at"` set.

### Step 8: Verify Double-End Rejected (409)

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/end \
  -H "Authorization: Bearer $TOKEN"
```

Expected: `409` (meeting already completed).

### Step 9: Verify 404 for Missing Meeting

```bash
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/api/v1/meetings/00000000-0000-0000-0000-000000000000 \
  -H "Authorization: Bearer $TOKEN"
```

Expected: `404`.

### Step 10: Verify 401 Without Auth

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/meetings
```

Expected: `401`.

## Part B — UI Testing

### Step 1: Login
1. Open `http://localhost:5173` in a browser
2. Log in with `tester@convene.dev` / `TestPass123!`

### Step 2: View Meetings Page
1. Navigate to the Meetings page
2. Verify the meeting list shows any previously created meetings
3. Each card displays: title, meeting ID (monospace), and status badge

### Step 3: Create Meeting via UI
1. Click **"Create Meeting"** button
2. Fill in: Title = "UI Test Meeting", Platform = "convene", Scheduled At = future time
3. Click **Submit**
4. Verify new card appears with status badge **"scheduled"** (gray)

### Step 4: Start Meeting via UI
1. On the scheduled meeting card, click **"Start"**
2. Verify status badge changes to **"active"** (green)
3. Verify **"Join Room"** button appears

### Step 5: End Meeting via UI
1. On the active meeting card, click **"End"**
2. Verify status badge changes to **"completed"** (blue)
3. Verify Start/Join/End buttons are no longer shown

## Verification Checklist

- [ ] POST `/meetings` returns 201 with status "scheduled"
- [ ] GET `/meetings` returns list with total count
- [ ] GET `/meetings/{id}` returns single meeting
- [ ] PATCH `/meetings/{id}` updates title
- [ ] POST `/meetings/{id}/start` transitions to "active"
- [ ] POST `/meetings/{id}/start` on active meeting returns 409
- [ ] POST `/meetings/{id}/end` transitions to "completed"
- [ ] POST `/meetings/{id}/end` on completed meeting returns 409
- [ ] GET `/meetings/{invalid-id}` returns 404
- [ ] GET `/meetings` without auth returns 401
- [ ] UI: Create meeting shows in list with "scheduled" badge
- [ ] UI: Start transitions badge to "active" (green)
- [ ] UI: End transitions badge to "completed" (blue)

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| 401 on all requests | Re-export `$TOKEN` — JWTs expire |
| 422 on create | Check `scheduled_at` is valid ISO 8601 datetime |
| UI shows empty list | Verify API server is running, check browser console for CORS errors |
| Status badge not updating | Hard-refresh the page (Cmd+Shift+R) |

## Cleanup

```bash
# No cleanup needed — completed meetings remain in DB for other tests
# To create a fresh meeting for subsequent tests:
export MEETING_ID=$(curl -s -X POST http://localhost:8000/api/v1/meetings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "Fresh Test Meeting",
    "platform": "convene",
    "scheduled_at": "'"$(date -u -v+1H +%Y-%m-%dT%H:%M:%SZ)"'"
  }' | jq -r '.id')
```
