---
name: kutana
description: >
  Join and participate in Kutana AI meetings. Manage turn-taking, chat,
  transcripts, and task creation. Use when asked to join a meeting, check
  meeting status, or extract action items.
compatibility: Requires kutana CLI installed (pip install kutana-ai)
metadata:
  author: kutana-ai
  version: "1.0"
  tags: meetings, productivity, collaboration
  openclaw:
    requires:
      bins:
        - kutana
---

# Kutana Meeting Skill

Use the `kutana` CLI to join meetings, participate in discussions, manage
turn-taking, and extract structured information. All commands output JSON
by default, making them easy to parse programmatically.

## When to Use

Activate this skill when the user mentions:

- Joining, creating, or leaving a meeting
- Speaker queue, raising hand, or taking a turn
- Meeting transcripts or chat history
- Action items, tasks, or meeting recaps
- Standup facilitation or note-taking
- Meeting participants or status

## Quick Start

```bash
# Authenticate (one-time setup)
kutana auth login --url https://dev.kutana.ai --api-key cvn_...

# List meetings and join one
kutana meetings list
kutana join <meeting_id>

# Send a chat message
kutana chat send "Hello everyone, I'm here to help take notes."

# Speak via TTS so participants hear you
kutana speak "Hello everyone, I'm here to help take notes."

# Leave when done
kutana leave
```

## Meeting Lifecycle

### List and Create Meetings

```bash
# List all available meetings (returns JSON array)
kutana meetings list

# Create a new meeting
kutana meetings create --title "Sprint Planning"
```

### Join and Leave

```bash
# Join with text-only capability (chat + data, no audio)
kutana join <meeting_id> --capabilities text_only

# Join with TTS so you can speak aloud
kutana join <meeting_id> --capabilities tts_enabled

# Join or create by title (finds active meeting or creates new one)
kutana join-or-create --title "Daily Standup"

# Leave the current meeting
kutana leave
```

**Capability levels** (choose the minimum you need):

| Capability          | Chat | Transcript | TTS | Voice In |
|---------------------|------|------------|-----|----------|
| `text_only`         | yes  | yes        | no  | no       |
| `tts_enabled`       | yes  | yes        | yes | no       |
| `voice_in`          | yes  | yes        | yes | yes      |
| `voice_bidirectional` | yes | yes       | yes | yes      |

### Meeting Status

```bash
# Full status: participants, queue, recent activity
kutana status

# Just participants
kutana participants

# Get the meeting recap: tasks, decisions, key points, open questions
kutana recap
```

## Turn Management

The speaking queue ensures orderly discussion. You must hold the active
turn before speaking via TTS.

```bash
# Raise your hand to join the speaker queue
kutana turn raise
kutana turn raise --topic "API design question"
kutana turn raise --priority urgent

# Check the current queue
kutana turn status

# Speak (auto raises hand, waits for turn, speaks, finishes)
kutana speak "Here is my analysis of the performance data."

# Manually signal you are done speaking
kutana turn finish

# Withdraw from the queue without speaking
kutana turn cancel
```

The `kutana speak` command handles the full lifecycle: raise hand, wait
for your turn, synthesize speech, then mark finished. Use individual
turn commands only when you need fine-grained control.

## Chat

```bash
# Send a message to meeting chat
kutana chat send "I have a question about the timeline."

# Read recent chat messages
kutana chat history --last-n 20
```

## Meeting Context

```bash
# Get recent transcript segments
kutana transcript --last-n 50

# Search transcript for a specific topic
kutana context --query "database migration" --limit 10

# Get extracted entities by type
kutana entities --type task --limit 20
kutana entities --type decision
kutana entities --type question
kutana entities --type blocker
kutana entities --type key_point
kutana entities --type follow_up

# Get the full meeting recap
kutana recap
```

**Entity types available:** task, decision, question, entity_mention,
key_point, blocker, follow_up.

## Tasks

```bash
# List tasks extracted from the meeting
kutana tasks list <meeting_id>

# Accept/claim a task
kutana tasks accept <task_id>

# Update task status
kutana tasks update <task_id> --status in_progress --message "Started refactoring"
kutana tasks update <task_id> --status completed --message "PR submitted"
kutana tasks update <task_id> --status blocked --message "Waiting on API access"
kutana tasks update <task_id> --status needs_review --message "Ready for review"
```

**Task statuses:** in_progress, completed, blocked, needs_review.

## Common Workflows

### Join and Summarize

```bash
kutana join $MEETING_ID --capabilities text_only
TRANSCRIPT=$(kutana transcript --last-n 100)
# Analyze the transcript JSON for key discussion points
# Then share the summary with participants
kutana chat send "Summary of last 100 segments: [your summary]"
kutana leave
```

### Monitor and Report

```bash
kutana join $MEETING_ID --capabilities text_only
while true; do
  RECAP=$(kutana recap)
  # Parse recap JSON for task/decision counts
  kutana chat send "Status update: tracking action items and decisions"
  sleep 60
done
```

### Extract Action Items

```bash
ENTITIES=$(kutana entities --type task --limit 50)
# Parse the JSON array of extracted tasks
# Accept tasks assigned to you
kutana tasks accept $TASK_ID
kutana tasks update $TASK_ID --status in_progress --message "Working on it"
kutana chat send "Accepted 2 action items from the discussion"
```

### Facilitate Standup

```bash
kutana join $MEETING_ID --capabilities tts_enabled
PARTICIPANTS=$(kutana participants)
# Iterate over participant list from JSON
for PARTICIPANT in $(echo "$PARTICIPANTS" | jq -r '.[].name'); do
  kutana speak "Your turn, $PARTICIPANT. What did you work on yesterday?"
  sleep 30
  TRANSCRIPT=$(kutana transcript --last-n 10)
  # Extract and log the update
done
kutana speak "Thanks everyone. I have logged all updates."
kutana leave
```

### Answer Questions from Transcript

```bash
kutana join $MEETING_ID --capabilities tts_enabled
# Search transcript for a specific topic
CONTEXT=$(kutana context --query "deployment timeline" --limit 10)
# Analyze the matching segments
kutana speak "Based on the discussion, the deployment is planned for Friday."
kutana turn finish
```

## Output Format

All commands output JSON to stdout by default. Errors go to stderr as
`{"error": "message"}`. Parse output with `jq` or your language's JSON
library.

```bash
# Example: extract meeting IDs
kutana meetings list | jq '.[].id'

# Example: get participant names
kutana participants | jq -r '.[].name'

# Example: check if you are the active speaker
kutana turn status | jq '.active_speaker'
```

## MCP Fallback

Agents can also interact with Kutana via MCP tools directly. Run
`kutana mcp` to start an MCP server exposing the same capabilities.
The CLI is preferred for Bash-based agents because it avoids MCP protocol
overhead and produces simple JSON output.

## Reference

For complete command syntax, flags, output schemas, and error codes, see
`references/command-reference.md`.

For meeting and agent state transitions, see
`references/meeting-state-machine.md`.
