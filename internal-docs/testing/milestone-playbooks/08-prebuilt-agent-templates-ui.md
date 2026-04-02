# Prebuilt Agent Templates UI

## Purpose
Verify the agent templates dashboard: browsing template cards, category filtering, activating a template for a meeting, and deactivating hosted sessions.

## Prerequisites
- [00-SETUP.md](./00-SETUP.md) completed
- `$TOKEN` exported
- API server (8000) and web frontend (5173) running
- Agent templates seeded in the database (via migrations or seed script)
- At least one meeting in "scheduled" or "active" status

## Step 1: Verify Templates Exist via API

```bash
curl -s http://localhost:8000/api/v1/agent-templates | jq '.[].name'
```

Expected: List of template names (e.g., assistant, summarizer, action-tracker, decision-logger).

> If empty, templates may need to be seeded. Check migration scripts or seed data.

## Step 2: Test Category Filter via API

```bash
# Filter by category
curl -s "http://localhost:8000/api/v1/agent-templates?category=productivity" | jq '.[].name'
curl -s "http://localhost:8000/api/v1/agent-templates?category=engineering" | jq '.[].name'
curl -s "http://localhost:8000/api/v1/agent-templates?category=general" | jq '.[].name'
```

Expected: Each query returns only templates matching the category.

## Step 3: Get Single Template

```bash
TEMPLATE_ID=$(curl -s http://localhost:8000/api/v1/agent-templates | jq -r '.[0].id')

curl -s http://localhost:8000/api/v1/agent-templates/$TEMPLATE_ID | jq .
```

Expected response:
```json
{
  "id": "...",
  "name": "...",
  "description": "...",
  "system_prompt": "...",
  "capabilities": ["listen", "transcribe", ...],
  "category": "productivity",
  "is_premium": false
}
```

## Step 4: Browse Templates in Web UI

1. Open `http://localhost:5173` and log in
2. Navigate to the **Templates** page (or `/templates`)
3. Verify:
   - Template cards displayed in a 2-column grid
   - Each card shows: name, category badge (color-coded), description, capability tags
   - **"Activate"** button on each card

## Step 5: Test Category Filter Buttons

1. On the Templates page, find the category filter buttons: **All**, **Productivity**, **Engineering**, **General**
2. Click **"Productivity"** — only productivity templates shown
3. Click **"Engineering"** — only engineering templates shown
4. Click **"General"** — only general templates shown
5. Click **"All"** — all templates shown again
6. Verify the active button is highlighted in blue, others in gray

## Step 6: Activate a Template

1. Ensure at least one meeting exists in "scheduled" or "active" status:
```bash
export MEETING_ID=$(curl -s -X POST http://localhost:8000/api/v1/meetings \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "title": "Template Activation Test",
    "platform": "kutana",
    "scheduled_at": "'"$(date -u +%Y-%m-%dT%H:%M:%SZ)"'"
  }' | jq -r '.id')
echo "MEETING_ID=$MEETING_ID"
```

2. On the Templates page, click **"Activate"** on any template card
3. In the activation modal:
   - Select the meeting from the dropdown (only scheduled/active meetings shown)
   - Optionally enter an Anthropic API key (or leave blank for platform key)
   - Click **Submit**
4. Verify success notification appears

## Step 7: Verify Hosted Session via API

```bash
curl -s -X POST http://localhost:8000/api/v1/agent-templates/$TEMPLATE_ID/activate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"meeting_id\": \"$MEETING_ID\"}" | jq .
```

Expected response (200):
```json
{
  "id": "<session-uuid>",
  "template_id": "...",
  "meeting_id": "...",
  "status": "active",
  "started_at": "..."
}
```

Save the session ID:
```bash
export SESSION_ID=$(curl -s -X POST http://localhost:8000/api/v1/agent-templates/$TEMPLATE_ID/activate \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"meeting_id\": \"$MEETING_ID\"}" | jq -r '.id')

echo "SESSION_ID=$SESSION_ID"
```

## Step 8: Deactivate Hosted Session

```bash
curl -s -o /dev/null -w "%{http_code}" \
  -X DELETE http://localhost:8000/api/v1/agent-templates/hosted-sessions/$SESSION_ID \
  -H "Authorization: Bearer $TOKEN"
```

Expected: `204`

## Step 9: Verify 404 for Invalid Template

```bash
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:8000/api/v1/agent-templates/00000000-0000-0000-0000-000000000000
```

Expected: `404`

## Verification Checklist

- [ ] GET `/agent-templates` returns template list
- [ ] Category filter (`?category=...`) filters correctly
- [ ] GET `/agent-templates/{id}` returns full template with system_prompt
- [ ] UI shows template grid with name, description, capabilities, category badge
- [ ] Category filter buttons work (All/Productivity/Engineering/General)
- [ ] Active filter button highlighted in blue
- [ ] Activate modal shows meeting dropdown (scheduled/active only)
- [ ] Activate modal has optional API key field
- [ ] POST `/agent-templates/{id}/activate` creates hosted session
- [ ] Hosted session has status "active" and `started_at`
- [ ] DELETE `/hosted-sessions/{id}` returns 204
- [ ] Invalid template ID returns 404

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| No templates in list | Templates need to be seeded — check migrations or run seed script |
| Category filter shows nothing | Verify template categories match filter values exactly |
| Activate modal has no meetings | Create a meeting first (must be scheduled or active) |
| 404 on activate | Verify template ID and meeting ID are valid UUIDs |
| Deactivate fails with 404 | Session may have already been deactivated |
| UI template page empty | Check browser console for API errors. Verify API server CORS config |

## Cleanup

```bash
# Clean up the test meeting
curl -s -X POST http://localhost:8000/api/v1/meetings/$MEETING_ID/end \
  -H "Authorization: Bearer $TOKEN" > /dev/null 2>&1
```
