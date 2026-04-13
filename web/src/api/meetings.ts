import { apiFetch } from "./client";
import type {
  AgentSessionInfo,
  Meeting,
  MeetingTokenResponse,
  PaginatedResponse,
  SelectedAgent,
} from "@/types";

export interface LiveKitTokenResponse {
  token: string;
  url: string;
  roomName: string;
}

export async function listMeetings(): Promise<PaginatedResponse<Meeting>> {
  return apiFetch<PaginatedResponse<Meeting>>("/meetings");
}

export async function createMeeting(data: {
  platform: string;
  title: string;
  scheduled_at: string;
}): Promise<Meeting> {
  return apiFetch<Meeting>("/meetings", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getMeetingToken(
  meetingId: string
): Promise<MeetingTokenResponse> {
  return apiFetch<MeetingTokenResponse>("/token/meeting", {
    method: "POST",
    body: JSON.stringify({ meeting_id: meetingId }),
  });
}

export async function getLiveKitToken(
  meetingId: string
): Promise<LiveKitTokenResponse> {
  const raw = await apiFetch<{ token: string; url: string; room_name: string }>(
    `/meetings/${meetingId}/livekit-token`,
    { method: "POST" }
  );
  return { token: raw.token, url: raw.url, roomName: raw.room_name };
}

export async function startMeeting(meetingId: string): Promise<Meeting> {
  return apiFetch<Meeting>(`/meetings/${meetingId}/start`, {
    method: "POST",
  });
}

export async function deleteMeeting(meetingId: string): Promise<void> {
  return apiFetch<void>(`/meetings/${meetingId}`, {
    method: "DELETE",
  });
}

export async function endMeeting(meetingId: string): Promise<Meeting> {
  return apiFetch<Meeting>(`/meetings/${meetingId}/end`, {
    method: "POST",
  });
}

/** Replace the full set of selected agent templates for a meeting. */
export async function setSelectedAgents(
  meetingId: string,
  selections: SelectedAgent[]
): Promise<void> {
  return apiFetch<void>(`/meetings/${meetingId}/selected-agents`, {
    method: "PUT",
    body: JSON.stringify({ selections }),
  });
}

/** Load the current set of selected agent templates for a meeting. */
export async function getSelectedAgents(
  meetingId: string
): Promise<SelectedAgent[]> {
  const res = await apiFetch<{
    meeting_id: string;
    selections: SelectedAgent[];
  }>(`/meetings/${meetingId}/selected-agents`);
  return res.selections;
}

/** Snapshot of each selected agent's warming/ready/failed/stopped state. */
export async function getAgentSessions(
  meetingId: string
): Promise<AgentSessionInfo[]> {
  const res = await apiFetch<{
    meeting_id: string;
    sessions: AgentSessionInfo[];
  }>(`/meetings/${meetingId}/agent-sessions`);
  return res.sessions;
}

/** Ask the backend to re-warm a specific selected agent after a failure. */
export async function retryAgentSession(
  meetingId: string,
  templateId: string
): Promise<void> {
  return apiFetch<void>(
    `/meetings/${meetingId}/agent-sessions/${templateId}/retry`,
    { method: "POST" }
  );
}
