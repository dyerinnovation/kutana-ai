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
  systemPromptOverride?: string,
  sopId?: string,
): Promise<HostedSession> {
  return apiFetch<HostedSession>(
    `/agent-templates/${templateId}/activate`,
    {
      method: "POST",
      body: JSON.stringify({
        meeting_id: meetingId,
        system_prompt_override: systemPromptOverride || null,
        sop_id: sopId || null,
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
