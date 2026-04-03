import { apiFetch } from "./client";
import type { Meeting, MeetingTokenResponse, PaginatedResponse } from "@/types";

export async function listMeetings(): Promise<PaginatedResponse<Meeting>> {
  return apiFetch<PaginatedResponse<Meeting>>("/meetings");
}

export async function createMeeting(data: {
  title: string;
  scheduled_at: string;
  platform?: string;
}): Promise<Meeting> {
  return apiFetch<Meeting>("/meetings", {
    method: "POST",
    body: JSON.stringify({ platform: "kutana", ...data }),
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

export async function startMeeting(meetingId: string): Promise<Meeting> {
  return apiFetch<Meeting>(`/meetings/${meetingId}/start`, {
    method: "POST",
  });
}

export async function endMeeting(meetingId: string): Promise<Meeting> {
  return apiFetch<Meeting>(`/meetings/${meetingId}/end`, {
    method: "POST",
  });
}
