import { apiFetch } from "./client";
import type { Feed, FeedCreate, FeedRun, PaginatedResponse } from "@/types";

export async function listFeeds(): Promise<PaginatedResponse<Feed>> {
  return apiFetch<PaginatedResponse<Feed>>("/feeds");
}

export async function createFeed(data: FeedCreate): Promise<Feed> {
  return apiFetch<Feed>("/feeds", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function getFeed(id: string): Promise<Feed> {
  return apiFetch<Feed>(`/feeds/${id}`);
}

export async function updateFeed(
  id: string,
  data: Partial<FeedCreate>
): Promise<Feed> {
  return apiFetch<Feed>(`/feeds/${id}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteFeed(id: string): Promise<void> {
  return apiFetch<void>(`/feeds/${id}`, {
    method: "DELETE",
  });
}

export async function toggleFeed(
  id: string,
  active: boolean
): Promise<Feed> {
  return apiFetch<Feed>(`/feeds/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ is_active: active }),
  });
}

export async function triggerFeed(id: string, meetingId: string): Promise<FeedRun> {
  return apiFetch<FeedRun>(`/feeds/${id}/trigger`, {
    method: "POST",
    body: JSON.stringify({ meeting_id: meetingId }),
  });
}

export async function listFeedRuns(
  feedId: string
): Promise<PaginatedResponse<FeedRun>> {
  return apiFetch<PaginatedResponse<FeedRun>>(`/feeds/${feedId}/runs`);
}
