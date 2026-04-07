import { apiFetch } from "./client";
import type { Integration, SlackChannel } from "@/types";

export async function listIntegrations(): Promise<Integration[]> {
  return apiFetch<Integration[]>("/integrations");
}

export async function connectSlack(): Promise<{ authorize_url: string }> {
  return apiFetch<{ authorize_url: string }>("/integrations/slack/connect", {
    method: "POST",
  });
}

export async function disconnectIntegration(id: string): Promise<void> {
  return apiFetch<void>(`/integrations/${id}`, { method: "DELETE" });
}

export async function listSlackChannels(): Promise<SlackChannel[]> {
  return apiFetch<SlackChannel[]>("/integrations/slack/channels");
}
