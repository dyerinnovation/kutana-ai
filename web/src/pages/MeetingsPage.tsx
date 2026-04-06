import { useEffect, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
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

export function MeetingsPage() {
  const navigate = useNavigate();
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create meeting state
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [platform, setPlatform] = useState("kutana");
  const [scheduledAt, setScheduledAt] = useState("");
  const [isCreating, setIsCreating] = useState(false);

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
        platform,
        scheduled_at: new Date(scheduledAt).toISOString(),
      });
      setShowCreate(false);
      setTitle("");
      setPlatform("kutana");
      setScheduledAt("");
      await loadMeetings();
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
    try {
      await startMeeting(meetingId);
      await loadMeetings();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to start meeting"
      );
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

  function formatDateTime(dateStr: string): string {
    return new Date(dateStr).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-50">Meetings</h1>
          <p className="text-sm text-gray-400 mt-1">
            Schedule and manage your meetings
          </p>
        </div>
        <Button onClick={() => setShowCreate(true)}>Create Meeting</Button>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="text-center py-12 text-gray-400">
          Loading meetings...
        </div>
      )}

      {!isLoading && meetings.length === 0 && (
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-gray-400 mb-4">No meetings scheduled yet.</p>
            <Button onClick={() => setShowCreate(true)}>
              Schedule your first meeting
            </Button>
          </CardContent>
        </Card>
      )}

      {meetings.length > 0 && (
        <div className="space-y-3">
          {meetings.map((meeting) => (
            <Card key={meeting.id}>
              <CardHeader>
                <div className="flex items-start justify-between">
                  <div>
                    <CardTitle>{meeting.title}</CardTitle>
                    <p className="text-xs text-gray-500 font-mono mt-1">
                      {meeting.id}
                    </p>
                  </div>
                  <span
                    className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ${
                      meeting.status === "active"
                        ? "bg-green-600/20 text-green-400 border border-green-500/30"
                        : meeting.status === "completed"
                          ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                          : "bg-gray-600/20 text-gray-400 border border-gray-500/30"
                    }`}
                  >
                    {meeting.status.charAt(0).toUpperCase() + meeting.status.slice(1)}
                  </span>
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div className="flex gap-6 text-sm text-gray-400">
                    <div>
                      <span className="text-gray-500">Platform: </span>
                      {meeting.platform}
                    </div>
                    <div>
                      <span className="text-gray-500">Scheduled: </span>
                      {formatDateTime(meeting.scheduled_at)}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {meeting.status === "scheduled" && (
                      <Button
                        size="sm"
                        onClick={() => handleStart(meeting.id)}
                      >
                        Start
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
          ))}
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
              <label className="block text-sm font-medium text-gray-300">
                Platform
              </label>
              <select
                className="flex h-10 w-full rounded-lg border border-gray-700 bg-gray-900 px-3 py-2 text-sm text-gray-50 focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={platform}
                onChange={(e) => setPlatform(e.target.value)}
              >
                <option value="kutana">Kutana</option>
                <option value="zoom">Zoom</option>
                <option value="teams">Teams</option>
                <option value="meet">Google Meet</option>
              </select>
            </div>
            <Input
              label="Scheduled At"
              type="datetime-local"
              value={scheduledAt}
              onChange={(e) => setScheduledAt(e.target.value)}
              required
            />
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
