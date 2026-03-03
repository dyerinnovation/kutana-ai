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
