import { apiFetch } from "./client";
import type {
  Agent,
  AgentKey,
  KeyCreateResponse,
  PaginatedResponse,
} from "@/types";

export async function listAgents(): Promise<PaginatedResponse<Agent>> {
  return apiFetch<PaginatedResponse<Agent>>("/agents");
}

export async function createAgent(data: {
  name: string;
  system_prompt: string;
  capabilities: string[];
}): Promise<Agent> {
  return apiFetch<Agent>("/agents", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getAgent(id: string): Promise<Agent> {
  return apiFetch<Agent>(`/agents/${id}`);
}

export async function deleteAgent(id: string): Promise<void> {
  return apiFetch<void>(`/agents/${id}`, {
    method: "DELETE",
  });
}

export async function createKey(
  agentId: string,
  data: { name: string }
): Promise<KeyCreateResponse> {
  return apiFetch<KeyCreateResponse>(`/agents/${agentId}/keys`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function listKeys(
  agentId: string
): Promise<PaginatedResponse<AgentKey>> {
  return apiFetch<PaginatedResponse<AgentKey>>(`/agents/${agentId}/keys`);
}

export async function revokeKey(
  agentId: string,
  keyId: string
): Promise<void> {
  return apiFetch<void>(`/agents/${agentId}/keys/${keyId}`, {
    method: "DELETE",
  });
}
