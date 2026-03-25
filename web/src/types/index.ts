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
  | { type: "transcript"; meeting_id: string; speaker_id: string | null; text: string; start_time: number; end_time: number; confidence: number; is_final: boolean }
  | { type: "participant_update"; action: string; participant_id: string; name: string; role: string }
  | { type: "error"; code: string; message: string }
  | { type: "joined"; meeting_id: string; granted_capabilities: string[] }
  | { type: "left"; meeting_id: string };

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
