export interface User {
  id: string;
  email: string;
  name: string;
  created_at: string;
}

export interface Agent {
  id: string;
  name: string;
  system_prompt: string;
  capabilities: string[];
  owner_id: string;
  created_at: string;
  updated_at: string;
}

export interface AgentKey {
  id: string;
  name: string;
  key_prefix: string;
  agent_id: string;
  created_at: string;
  revoked_at: string | null;
}

export interface KeyCreateResponse {
  id: string;
  raw_key: string;
  key_prefix: string;
  name: string;
  created_at: string;
}

export interface Meeting {
  id: string;
  title: string;
  platform: string;
  scheduled_at: string;
  status: string;
  created_at: string;
  owner_id: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export interface TranscriptSegment {
  speaker_id: string;
  speaker_name: string | null;
  text: string;
  start_time: number;
  end_time: number;
  confidence: number;
  is_final: boolean;
}

export interface MeetingTokenResponse {
  token: string;
  meeting_id: string;
}

/** WebSocket message types for the agent gateway */
export type GatewayMessage =
  | { type: "join_meeting"; meeting_id: string }
  | { type: "leave_meeting" }
  | { type: "audio_data"; data: string; sample_rate: number }
  | { type: "transcript"; meeting_id: string; speaker_id: string | null; speaker_name: string | null; text: string; start_time: number; end_time: number; confidence: number; is_final: boolean }
  | { type: "participant_update"; action: string; participant_id: string; name: string; role: string }
  | { type: "error"; code: string; message: string }
  | { type: "joined"; meeting_id: string; granted_capabilities: string[] }
  | { type: "left"; meeting_id: string }
  | { type: "event"; event_type: string; payload: Record<string, unknown> }
  | { type: "turn.speaker.changed"; speaker_id: string | null; speaker_name: string | null }
  | { type: "turn.queue.updated"; queue: TurnQueueEntry[] }
  | { type: "turn.your_turn" }
  | { type: "chat"; sender_id: string; sender_name: string; text: string; timestamp: number; is_agent: boolean };

export interface ChatMessage {
  id: string;
  sender_id: string;
  sender_name: string;
  text: string;
  timestamp: number;
  is_agent: boolean;
}

export interface TurnQueueEntry {
  participant_id: string;
  name: string;
}

export interface TtsAudioPayload {
  meeting_id: string;
  speaker_session_id: string;
  speaker_name: string;
  data: string;       // base64-encoded audio
  format: string;     // "pcm_s16le" | "wav" | "mp3"
  sample_rate?: number; // source sample rate (e.g. 24000 for Cartesia)
  char_count: number;
}

export interface Participant {
  id: string;
  name: string;
  role: string;
  is_muted: boolean;
  avatar_url?: string;
  is_speaking?: boolean;
}

export interface AgentTemplate {
  id: string;
  name: string;
  description: string;
  system_prompt: string;
  capabilities: string[];
  category: string;
  is_premium: boolean;
}

export interface HostedSession {
  id: string;
  template_id: string;
  meeting_id: string;
  status: string;
  started_at: string;
}

export interface Feed {
  id: string;
  user_id: string;
  name: string;
  platform: string;
  direction: "inbound" | "outbound" | "bidirectional";
  delivery_type: "mcp" | "channel";
  mcp_server_url: string | null;
  channel_name: string | null;
  data_types: string[];
  context_types: string[];
  trigger: string;
  meeting_tag: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  last_triggered_at: string | null;
  last_error: string | null;
  token_hint: string | null;
}

export interface FeedCreate {
  name: string;
  platform: string;
  direction: "inbound" | "outbound" | "bidirectional";
  delivery_type: "mcp" | "channel";
  mcp_server_url?: string;
  mcp_auth_token?: string;
  channel_name?: string;
  data_types: string[];
  context_types?: string[];
  trigger: string;
  meeting_tag?: string;
}

export interface FeedRun {
  id: string;
  feed_id: string;
  meeting_id: string;
  trigger: string;
  direction: string;
  status: "pending" | "running" | "delivered" | "failed";
  started_at: string;
  finished_at: string | null;
  error: string | null;
}
