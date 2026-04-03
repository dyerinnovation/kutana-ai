import { useEffect, useState, useMemo, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import "@/styles/datepicker-overrides.css";
import type { Meeting } from "@/types";
import { listMeetings, createMeeting, startMeeting, endMeeting } from "@/api/meetings";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/Card";
import { Dialog, DialogTitle, DialogFooter } from "@/components/ui/Dialog";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Sort meetings: Active first, then Scheduled (soonest first), then Completed (most recent first). */
function sortMeetings(meetings: Meeting[]): Meeting[] {
  const statusOrder: Record<string, number> = {
    active: 0,
    scheduled: 1,
    completed: 2,
    failed: 3,
  };

  return [...meetings].sort((a, b) => {
    const oa = statusOrder[a.status] ?? 99;
    const ob = statusOrder[b.status] ?? 99;
    if (oa !== ob) return oa - ob;

    if (a.status === "scheduled") {
      // Soonest first
      return new Date(a.scheduled_at).getTime() - new Date(b.scheduled_at).getTime();
    }
    if (a.status === "completed" || a.status === "failed") {
      // Most recent first
      const aEnd = a.ended_at ?? a.updated_at;
      const bEnd = b.ended_at ?? b.updated_at;
      return new Date(bEnd).getTime() - new Date(aEnd).getTime();
    }
    // Active — most recently started first
    const aStart = a.started_at ?? a.scheduled_at;
    const bStart = b.started_at ?? b.scheduled_at;
    return new Date(bStart).getTime() - new Date(aStart).getTime();
  });
}

function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/** Return a human-readable relative time string like "5 minutes ago" or "in 2 hours". */
function relativeTime(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const diffMs = now - then;
  const absDiff = Math.abs(diffMs);
  const inFuture = diffMs < 0;

  if (absDiff < 60_000) return inFuture ? "in less than a minute" : "just now";

  const minutes = Math.floor(absDiff / 60_000);
  if (minutes < 60) {
    const label = minutes === 1 ? "minute" : "minutes";
    return inFuture ? `in ${minutes} ${label}` : `${minutes} ${label} ago`;
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    const label = hours === 1 ? "hour" : "hours";
    return inFuture ? `in ${hours} ${label}` : `${hours} ${label} ago`;
  }

  const days = Math.floor(hours / 24);
  const label = days === 1 ? "day" : "days";
  return inFuture ? `in ${days} ${label}` : `${days} ${label} ago`;
}

/** Format a duration in ms to a compact string like "1h 23m" or "45m". */
function formatDuration(ms: number): string {
  const totalMinutes = Math.floor(ms / 60_000);
  if (totalMinutes < 1) return "<1m";
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  if (hours === 0) return `${minutes}m`;
  if (minutes === 0) return `${hours}h`;
  return `${hours}h ${minutes}m`;
}

/** Compute meeting duration string, or null if not applicable. */
function getMeetingDuration(meeting: Meeting): string | null {
  if (meeting.status === "active" && meeting.started_at) {
    return formatDuration(Date.now() - new Date(meeting.started_at).getTime());
  }
  if (meeting.status === "completed" && meeting.started_at && meeting.ended_at) {
    return formatDuration(
      new Date(meeting.ended_at).getTime() - new Date(meeting.started_at).getTime()
    );
  }
  return null;
}

// ---------------------------------------------------------------------------
// Status badge config
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<string, string> = {
  active: "bg-emerald-600/20 text-emerald-400 border border-emerald-500/30",
  scheduled: "bg-blue-600/20 text-blue-400 border border-blue-500/30",
  completed: "bg-gray-600/20 text-gray-400 border border-gray-500/30",
  failed: "bg-red-600/20 text-red-400 border border-red-500/30",
};

const STATUS_DOT: Record<string, string> = {
  active: "bg-emerald-400",
  scheduled: "bg-blue-400",
  completed: "bg-gray-400",
  failed: "bg-red-400",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MeetingsPage() {
  const navigate = useNavigate();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create meeting state
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [scheduledAt, setScheduledAt] = useState<Date | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [startingId, setStartingId] = useState<string | null>(null);

  // Tick for live duration updates
  const [, setTick] = useState(0);

  const sorted = useMemo(() => sortMeetings(meetings), [meetings]);
  const hasActive = sorted.some((m) => m.status === "active");

  // Tick every 30s if there are active meetings (for live duration display)
  useEffect(() => {
    if (!hasActive) return;
    const id = setInterval(() => setTick((t) => t + 1), 30_000);
    return () => clearInterval(id);
  }, [hasActive]);

  useEffect(() => {
    loadMeetings();
  }, []);

  async function loadMeetings() {
    try {
      const res = await listMeetings();
      setMeetings(res.items);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load meetings"
      );
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setIsCreating(true);
    setError(null);

    try {
      await createMeeting({
        title,
        platform: "kutana",
        scheduled_at: scheduledAt!.toISOString(),
      });
      await loadMeetings();
      setShowCreate(false);
      setTitle("");
      setScheduledAt(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to create meeting"
      );
    } finally {
      setIsCreating(false);
    }
  }

  async function handleStart(meetingId: string) {
    setError(null);
    setStartingId(meetingId);
    try {
      await startMeeting(meetingId);
      await loadMeetings();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start meeting"
      );
    } finally {
      setStartingId(null);
    }
  }

  async function handleEnd(meetingId: string) {
    setError(null);
    try {
      await endMeeting(meetingId);
      await loadMeetings();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to end meeting"
      );
    }
  }

  return (
    <div className="space-y-6">
      {/* Page header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-50">Meetings</h1>
          <p className="text-sm text-gray-400 mt-1">
            Schedule and manage your meetings
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>Create Meeting</Button>
      </div>

      {/* Error banner */}
      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex flex-col items-center justify-center py-20 text-gray-400">
          <svg
            className="h-8 w-8 animate-spin text-emerald-500 mb-3"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Loading meetings...
        </div>
      )}

      {/* Empty state */}
      {!isLoading && meetings.length === 0 && (
        <div className="flex flex-col items-center justify-center rounded-xl border border-gray-800 bg-gray-900/50 py-16 px-6">
          {/* Calendar icon */}
          <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-600/10 mb-5">
            <svg
              className="h-8 w-8 text-emerald-500"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth="1.5"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5m-9-6h.008v.008H12v-.008zM12 15h.008v.008H12V15zm0 2.25h.008v.008H12v-.008zM9.75 15h.008v.008H9.75V15zm0 2.25h.008v.008H9.75v-.008zM7.5 15h.008v.008H7.5V15zm0 2.25h.008v.008H7.5v-.008zm6.75-4.5h.008v.008h-.008v-.008zm0 2.25h.008v.008h-.008V15zm0 2.25h.008v.008h-.008v-.008zm2.25-4.5h.008v.008H16.5v-.008zm0 2.25h.008v.008H16.5V15z"
              />
            </svg>
          </div>
          <h2 className="text-lg font-semibold text-gray-50 mb-2">No meetings yet</h2>
          <p className="text-sm text-gray-400 mb-6 max-w-sm text-center">
            Schedule a meeting to get started. Invite AI agents and collaborators to join in real time.
          </p>
          <Button onClick={() => setShowCreate(true)}>Create Your First Meeting</Button>
        </div>
      )}

      {/* Meeting cards */}
      {sorted.length > 0 && (
        <div className="space-y-3">
          {sorted.map((meeting) => {
            const duration = getMeetingDuration(meeting);
            const statusStyle = STATUS_STYLES[meeting.status] ?? STATUS_STYLES.completed;
            const dotColor = STATUS_DOT[meeting.status] ?? STATUS_DOT.completed;

            return (
              <Card
                key={meeting.id}
                className="transition-all duration-200 hover:border-gray-600 hover:bg-gray-800/60"
              >
                <CardHeader>
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <CardTitle>{meeting.title ?? "Untitled Meeting"}</CardTitle>
                    </div>
                    <span
                      className={`inline-flex shrink-0 items-center gap-1.5 rounded-md px-2 py-0.5 text-xs font-medium ${statusStyle}`}
                    >
                      <span className={`inline-block h-1.5 w-1.5 rounded-full ${dotColor}`} />
                      {meeting.status.charAt(0).toUpperCase() + meeting.status.slice(1)}
                    </span>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center justify-between gap-4">
                    {/* Info chips */}
                    <div className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-gray-400">
                      {/* Scheduled time */}
                      <div className="flex items-center gap-1.5">
                        <svg className="h-3.5 w-3.5 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                        </svg>
                        {formatDateTime(meeting.scheduled_at)}
                      </div>

                      {/* Duration (active / completed) */}
                      {duration && (
                        <div className="flex items-center gap-1.5">
                          <svg className="h-3.5 w-3.5 text-gray-500" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 13.5l10.5-11.25L12 10.5h8.25L9.75 21.75 12 13.5H3.75z" />
                          </svg>
                          <span>
                            {meeting.status === "active" ? `Running for ${duration}` : duration}
                          </span>
                        </div>
                      )}

                      {/* Relative time context */}
                      {meeting.status === "active" && meeting.started_at && (
                        <div className="text-emerald-400/80">
                          Started {relativeTime(meeting.started_at)}
                        </div>
                      )}
                      {meeting.status === "scheduled" && (
                        <div className="text-blue-400/80">
                          Starts {relativeTime(meeting.scheduled_at)}
                        </div>
                      )}
                      {meeting.status === "completed" && meeting.ended_at && (
                        <div className="text-gray-500">
                          Ended {relativeTime(meeting.ended_at)}
                        </div>
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex shrink-0 gap-2">
                      {meeting.status === "scheduled" && (
                        <Button
                          size="sm"
                          onClick={() => handleStart(meeting.id)}
                          disabled={startingId === meeting.id}
                        >
                          {startingId === meeting.id ? "Starting..." : "Start"}
                        </Button>
                      )}
                      {meeting.status === "active" && (
                        <>
                          <Button
                            size="sm"
                            onClick={() =>
                              navigate(`/meetings/${meeting.id}/room`)
                            }
                          >
                            Join Room
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => handleEnd(meeting.id)}
                          >
                            End
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Create Meeting Dialog */}
      <Dialog open={showCreate} onClose={() => setShowCreate(false)}>
        <form onSubmit={handleCreate}>
          <DialogTitle>Schedule Meeting</DialogTitle>
          <div className="space-y-4">
            <Input
              label="Title"
              placeholder="Weekly standup"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              required
            />
            <div className="space-y-1.5">
              <label className="block text-xs font-medium uppercase tracking-widest text-gray-400">
                When<span className="text-red-400 ml-0.5">*</span>
              </label>
              <DatePicker
                selected={scheduledAt}
                onChange={(date: Date | null) => setScheduledAt(date)}
                showTimeSelect
                timeFormat="HH:mm"
                timeIntervals={15}
                dateFormat="MMMM d, yyyy h:mm aa"
                minDate={new Date()}
                placeholderText="Pick a date and time"
                className="flex h-9 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-50 placeholder:text-gray-500 transition-colors duration-150 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50"
                calendarClassName="kutana-calendar"
                required
              />
            </div>
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setShowCreate(false)}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isCreating}>
              {isCreating ? "Creating..." : "Create Meeting"}
            </Button>
          </DialogFooter>
        </form>
      </Dialog>
    </div>
  );
}
