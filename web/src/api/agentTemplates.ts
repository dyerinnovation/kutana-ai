import { apiFetch } from "./client";
import type { AgentTemplate, HostedSession } from "@/types";

export async function listTemplates(
  category?: string
): Promise<AgentTemplate[]> {
  const params = category ? `?category=${encodeURIComponent(category)}` : "";
  return apiFetch<AgentTemplate[]>(`/agent-templates${params}`);
}

export async function getTemplate(id: string): Promise<AgentTemplate> {
  return apiFetch<AgentTemplate>(`/agent-templates/${id}`);
}

export async function activateTemplate(
  templateId: string,
  meetingId: string,
  anthropicApiKey?: string
): Promise<HostedSession> {
  return apiFetch<HostedSession>(
    `/agent-templates/${templateId}/activate`,
    {
      method: "POST",
      body: JSON.stringify({
        meeting_id: meetingId,
        anthropic_api_key: anthropicApiKey || null,
      }),
    }
  );
}

export async function deactivateSession(sessionId: string): Promise<void> {
  return apiFetch<void>(
    `/agent-templates/hosted-sessions/${sessionId}`,
    { method: "DELETE" }
  );
}
