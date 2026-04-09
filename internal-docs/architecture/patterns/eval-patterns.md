# Eval Patterns

Architecture patterns for the Kutana managed agent evaluation framework.

---

## LLM-as-Judge Pattern

The eval framework uses **LLM-as-Judge** to score agent behavior. A separate Claude model evaluates the agent's output against rubric criteria.

```
                    ┌──────────────┐
                    │  Synthetic   │
                    │  Transcript  │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  Agent Under │
                    │  Evaluation  │
                    │  (Messages   │
                    │   API)       │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │  Agent Response:        │
              │  - Text output          │
              │  - tool_use blocks      │
              └────────────┬────────────┘
                           │
          ┌────────────────▼────────────────┐
          │  LLM Judge (claude-sonnet-4-6)  │
          │  Input:                         │
          │  - Transcript                   │
          │  - Agent response               │
          │  - Rubric criteria              │
          │  - Expected behaviors           │
          │  - Anti-patterns                │
          │                                 │
          │  Output: JSON scores (1-5)      │
          └────────────────┬────────────────┘
                           │
                    ┌──────▼───────┐
                    │  EvalResult  │
                    │  → Langfuse  │
                    └──────────────┘
```

### Why LLM-as-Judge?

Agent behavior is qualitative — a meeting notetaker's output can't be verified with string matching. The judge evaluates:

- **Structural compliance** — does the output follow the expected format?
- **Content accuracy** — are facts and attributions correct?
- **Behavioral compliance** — does the agent follow its role constraints?
- **Quality** — is the output useful, concise, well-organized?

### Judge Configuration

- **Model:** `claude-sonnet-4-6` (fast, capable enough for scoring)
- **System prompt:** Instructs JSON-only output with criterion/score/reason structure
- **Temperature:** Default (not set — deterministic enough for scoring)
- **Max tokens:** 2048 (enough for 6-8 criteria with reasons)

### Scoring Reliability

To improve scoring reliability:
1. Each criterion has a clear, specific description
2. The judge receives both expected behaviors and anti-patterns
3. Weights allow emphasizing critical criteria (e.g., "Silent Observer" weighted 1.5)
4. Results include per-criterion reasons for auditability

## Mock Eval Architecture

Mock evals test agent behavior without a running cluster.

```
┌─────────────┐     ┌────────────────────┐     ┌──────────────┐
│  Scenario    │────▶│  Mock Runner        │────▶│  Judge       │
│  + Transcript│     │  1. Build context   │     │  Score (1-5) │
│  + Rubric    │     │  2. Send to API     │     │  per criteria│
└─────────────┘     │  3. Get tool_use    │     └──────────────┘
                    │  4. Synthetic results│
                    │  5. Multi-turn loop  │
                    └────────────────────┘
```

The mock runner:
1. Loads the agent's system prompt
2. Formats the transcript as a user message
3. Calls Anthropic Messages API with Kutana tool definitions
4. When the model returns `tool_use` blocks, provides synthetic responses
5. Continues for up to 5 turns (configurable)
6. Collects all text and tool_use blocks for the judge

### Synthetic Tool Results

The mock runner provides static responses for tool calls to keep the conversation flowing:

| Tool | Synthetic Result |
|------|-----------------|
| `kutana_get_transcript` | Empty segments |
| `kutana_get_participants` | Alice, Bob, Charlie |
| `kutana_send_chat_message` | `{"status": "sent"}` |
| `kutana_create_task` | `{"status": "created"}` |
| `kutana_raise_hand` | `{"position": 1}` |
| Others | `{"status": "ok"}` |

## E2E Eval Architecture

E2E evals test against the live dev cluster.

```
┌─────────────┐     ┌──────────────────────┐     ┌──────────────┐
│  Scenario    │────▶│  E2E Runner           │────▶│  Judge       │
│  + Transcript│     │  1. Create meeting    │     │  Score (1-5) │
│  + Rubric    │     │  2. Activate agent    │     │  per criteria│
└─────────────┘     │  3. Start meeting     │     └──────────────┘
                    │  4. Inject transcript  │
                    │  5. Observe events     │
                    │  6. End meeting        │
                    │  7. Cleanup            │
                    └──────────────────────┘
                           │
                    ┌──────▼───────┐
                    │  Dev Cluster │
                    │  - API Server│
                    │  - Gateway   │
                    │  - Redis     │
                    │  - PostgreSQL│
                    └──────────────┘
```

The E2E runner:
1. Creates a real meeting via the API
2. Activates the agent under test
3. Starts the meeting (triggers `meeting.started`)
4. Injects transcript segments into Redis (mimics audio pipeline)
5. Observes agent events from the Redis stream
6. Ends the meeting and collects final output
7. Cleans up the meeting

## MinIO Data Structure

Eval data is stored in MinIO under the `kutana-eval-data` bucket:

```
kutana-eval-data/
├── transcripts/
│   ├── standup-10min-3speakers.json
│   ├── architecture-review-30min-4speakers.json
│   ├── sprint-planning-45min-5speakers.json
│   ├── sprint-retro-20min-4speakers.json
│   ├── user-interview-25min-2speakers.json
│   ├── team-onboarding-20min-3speakers.json
│   ├── silent-meeting-5min-2speakers.json
│   └── code-review-15min-3speakers.json
├── scenarios/
│   ├── meeting-notetaker/
│   │   ├── happy-path-standup.json
│   │   ├── edge-case-silent.json
│   │   └── adversarial-long-meeting.json
│   ├── meeting-summarizer/
│   │   └── ... (3 files per agent)
│   └── ... (10 agent directories)
└── rubrics/
    ├── common.json
    ├── meeting-notetaker.json
    ├── meeting-summarizer.json
    └── ... (10 agent-specific + 1 common = 11 files)
```

### Upload Script

```bash
# Upload all data
python scripts/upload_eval_data.py

# Verify (dry run)
python scripts/upload_eval_data.py --dry-run
```

## Langfuse Integration

Eval results are reported to Langfuse for tracking and regression detection:

- Each eval run creates a Langfuse **trace**
- The agent invocation is a **generation** span
- The judge invocation is a separate **generation** span
- Scores are attached as Langfuse **scores** on the trace

This enables:
- Score trending over time
- Regression detection when prompts change
- Comparison across model versions
- Filtering by agent, scenario type, or tier
