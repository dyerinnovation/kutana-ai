import { apiFetch } from "./client";
import type { Meeting, PaginatedResponse } from "@/types";

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
