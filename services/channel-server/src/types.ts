/**
 * TypeScript types for the Convene AI Channel Server.
 *
 * Mirrors the Python domain models from convene-core so both sides of the
 * WebSocket boundary share the same vocabulary.
 */

// ---------------------------------------------------------------------------
// Agent configuration
// ---------------------------------------------------------------------------

/** Subscription mode controlling which meeting events are forwarded to Claude. */
export type AgentMode = "transcript" | "insights" | "both" | "selective";

/** Entity types extracted from meeting transcripts (matches Python EntityType literals). */
export type EntityType =
  | "task"
  | "decision"
  | "question"
  | "entity_mention"
  | "key_point"
  | "blocker"
  | "follow_up";

// ---------------------------------------------------------------------------
// Extracted entities (mirror of convene_core/extraction/types.py)
// ---------------------------------------------------------------------------

/** Fields shared by every extracted entity type. */
export interface ExtractedEntity {
  id: string;
  entity_type: EntityType;
  meeting_id: string;
  confidence: number;
  extracted_at: string;
  batch_id: string;
}

export interface TaskEntity extends ExtractedEntity {
  entity_type: "task";
  title: string;
  assignee: string | null;
  deadline: string | null;
  priority: "high" | "medium" | "low";
  status: "identified" | "accepted" | "completed";
  source_speaker: string | null;
  source_segment_id: string | null;
}

export interface DecisionEntity extends ExtractedEntity {
  entity_type: "decision";
  summary: string;
  participants: string[];
  rationale: string;
  source_segment_ids: string[];
}

export interface QuestionEntity extends ExtractedEntity {
  entity_type: "question";
  text: string;
  asker: string | null;
  status: "open" | "answered";
  answer: string | null;
  source_segment_id: string | null;
}

export interface EntityMentionEntity extends ExtractedEntity {
  entity_type: "entity_mention";
  name: string;
  kind: "person" | "system" | "concept" | "org";
  context: string;
  first_mention_segment_id: string | null;
}

export interface KeyPointEntity extends ExtractedEntity {
  entity_type: "key_point";
  summary: string;
  speaker: string | null;
  topic: string;
  importance: "high" | "medium" | "low";
  source_segment_id: string | null;
}

export interface BlockerEntity extends ExtractedEntity {
  entity_type: "blocker";
  description: string;
  owner: string | null;
  severity: "critical" | "high" | "medium" | "low";
  related_tasks: string[];
  source_segment_id: string | null;
}

export interface FollowUpEntity extends ExtractedEntity {
  entity_type: "follow_up";
  description: string;
  owner: string | null;
  due_context: string | null;
  source_segment_id: string | null;
}

/** Discriminated union over all entity types. */
export type AnyExtractedEntity =
  | TaskEntity
  | DecisionEntity
  | QuestionEntity
  | EntityMentionEntity
  | KeyPointEntity
  | BlockerEntity
  | FollowUpEntity;

// ---------------------------------------------------------------------------
// Gateway WebSocket messages
// ---------------------------------------------------------------------------

/** Real-time transcript segment received from the agent gateway. */
export interface TranscriptSegment {
  type: "transcript";
  meeting_id: string;
  segment_id: string;
  speaker: string | null;
  text: string;
  start_time: number;
  end_time: number;
  confidence: number;
  is_final: boolean;
}

/** Insight batch event delivered via data channel. */
export interface InsightPayload {
  batch_id: string;
  entities: AnyExtractedEntity[];
  processing_time_ms: number;
}

/** Generic gateway event wrapper. */
export interface GatewayEvent {
  type: "event";
  event_type: string;
  data?: Record<string, unknown>;
  payload?: Record<string, unknown>;
}

/** Gateway error message. */
export interface GatewayError {
  type: "error";
  code: string;
  message: string;
}

/** "Joined" confirmation from the gateway after a successful join_meeting. */
export interface JoinedMessage {
  type: "joined";
  meeting_id: string;
  agent_id?: string;
  capabilities?: string[];
}

/** Union of all messages the gateway may send. */
export type GatewayMessage =
  | TranscriptSegment
  | GatewayEvent
  | GatewayError
  | JoinedMessage;

// ---------------------------------------------------------------------------
// Channel notifications (MCP → Claude Code)
// ---------------------------------------------------------------------------

/** A structured message pushed to Claude Code via the channel protocol. */
export interface ChannelMessage {
  /** Semantic topic — used as the MCP notification logger name. */
  topic: "transcript" | "insight" | "recap" | "meeting_context" | "chat";
  /** Fine-grained type within the topic (e.g. entity_type for insights). */
  type: string;
  /** Human-readable content string sent as notification data. */
  content: string;
  /** Optional key-value metadata. */
  metadata?: Record<string, string>;
}
