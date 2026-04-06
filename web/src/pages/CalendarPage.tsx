import { useEffect, useState, type FormEvent } from "react";
import type { Meeting } from "@/types";
import { listMeetings, createMeeting } from "@/api/meetings";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardContent } from "@/components/ui/Card";
import { Dialog, DialogTitle, DialogFooter } from "@/components/ui/Dialog";
import { cn } from "@/lib/utils";

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const CELLS = 42; // 6 rows × 7 cols

export function CalendarPage() {
  const [currentMonth, setCurrentMonth] = useState(() => {
    const now = new Date();
    return new Date(now.getFullYear(), now.getMonth(), 1);
  });
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Create meeting dialog
  const [showCreate, setShowCreate] = useState(false);
  const [createTitle, setCreateTitle] = useState("");
  const [createTime, setCreateTime] = useState("09:00");
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    loadMeetings();
  }, []);

  async function loadMeetings() {
    try {
      const res = await listMeetings();
      setMeetings(res.items);
    } catch {
      // Silently fail — calendar will show empty
    } finally {
      setIsLoading(false);
    }
  }

  // Group meetings by YYYY-MM-DD
  const meetingsByDate = new Map<string, Meeting[]>();
  for (const m of meetings) {
    const key = m.scheduled_at.slice(0, 10);
    const list = meetingsByDate.get(key) ?? [];
    list.push(m);
    meetingsByDate.set(key, list);
  }

  // Build the calendar grid
  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();
  const firstDay = new Date(year, month, 1);
  const startOffset = firstDay.getDay(); // 0=Sun

  const dates: Date[] = [];
  for (let i = 0; i < CELLS; i++) {
    const d = new Date(year, month, 1 - startOffset + i);
    dates.push(d);
  }

  const today = new Date();
  const todayStr = formatDateKey(today);

  function formatDateKey(d: Date): string {
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }

  const monthLabel = currentMonth.toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });

  function prevMonth() {
    setCurrentMonth(new Date(year, month - 1, 1));
    setSelectedDate(null);
  }

  function nextMonth() {
    setCurrentMonth(new Date(year, month + 1, 1));
    setSelectedDate(null);
  }

  function goToday() {
    setCurrentMonth(new Date(today.getFullYear(), today.getMonth(), 1));
    setSelectedDate(today);
  }

  // Meetings for the selected day
  const selectedKey = selectedDate ? formatDateKey(selectedDate) : null;
  const selectedMeetings = selectedKey ? (meetingsByDate.get(selectedKey) ?? []) : [];

  function openSchedule() {
    if (selectedDate) {
      setCreateTitle("");
      setCreateTime("09:00");
      setShowCreate(true);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!selectedDate) return;
    setIsCreating(true);
    try {
      const dt = new Date(selectedDate);
      const [h, m] = createTime.split(":").map(Number);
      dt.setHours(h, m, 0, 0);
      await createMeeting({
        title: createTitle,
        platform: "kutana",
        scheduled_at: dt.toISOString(),
      });
      setShowCreate(false);
      await loadMeetings();
    } catch {
      // Error handling could be added
    } finally {
      setIsCreating(false);
    }
  }

  function exportIcs() {
    const lines = [
      "BEGIN:VCALENDAR",
      "VERSION:2.0",
      "PRODID:-//Kutana AI//Calendar//EN",
    ];
    for (const m of meetings) {
      const dt = new Date(m.scheduled_at);
      const dtStr = dt
        .toISOString()
        .replace(/[-:]/g, "")
        .replace(/\.\d+/, "");
      lines.push(
        "BEGIN:VEVENT",
        `DTSTART:${dtStr}`,
        `SUMMARY:${m.title.replace(/[,;\\]/g, "")}`,
        `UID:${m.id}@kutana.ai`,
        "END:VEVENT"
      );
    }
    lines.push("END:VCALENDAR");

    const blob = new Blob([lines.join("\r\n")], { type: "text/calendar" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "kutana-meetings.ics";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-50">Calendar</h1>
        <div className="flex items-center gap-2">
          <div className="flex items-center rounded-lg border border-gray-800 bg-gray-900">
            <button
              onClick={prevMonth}
              className="px-3 py-2 text-gray-400 hover:text-gray-50 transition-colors"
            >
              <ChevronLeftIcon />
            </button>
            <span className="px-3 py-2 text-sm font-medium text-gray-200 min-w-[140px] text-center">
              {monthLabel}
            </span>
            <button
              onClick={nextMonth}
              className="px-3 py-2 text-gray-400 hover:text-gray-50 transition-colors"
            >
              <ChevronRightIcon />
            </button>
          </div>
          <Button variant="outline" size="sm" onClick={goToday}>
            Today
          </Button>
          <Button variant="outline" size="sm" onClick={exportIcs}>
            Export .ics
          </Button>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-400">Loading...</div>
      ) : (
        <>
          {/* Calendar Grid */}
          <Card>
            <CardContent className="p-0">
              {/* Day headers */}
              <div className="grid grid-cols-7 border-b border-gray-800">
                {DAY_NAMES.map((day) => (
                  <div
                    key={day}
                    className="py-2 text-center text-xs font-medium uppercase tracking-wider text-gray-500"
                  >
                    {day}
                  </div>
                ))}
              </div>

              {/* Date cells */}
              <div className="grid grid-cols-7">
                {dates.map((date, i) => {
                  const key = formatDateKey(date);
                  const isCurrentMonth = date.getMonth() === month;
                  const isToday = key === todayStr;
                  const isSelected =
                    selectedDate && key === formatDateKey(selectedDate);
                  const dayMeetings = meetingsByDate.get(key) ?? [];

                  return (
                    <button
                      key={i}
                      onClick={() => setSelectedDate(date)}
                      className={cn(
                        "h-24 border-b border-r border-gray-800/50 p-2 text-left text-sm transition-colors",
                        isCurrentMonth
                          ? "text-gray-200"
                          : "text-gray-600",
                        isToday && "bg-blue-600/10",
                        isSelected && "bg-blue-600/15 ring-1 ring-inset ring-blue-500/50",
                        "hover:bg-gray-800/50"
                      )}
                    >
                      <span
                        className={cn(
                          "inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium",
                          isToday &&
                            "bg-blue-600 text-white"
                        )}
                      >
                        {date.getDate()}
                      </span>
                      {dayMeetings.length > 0 && (
                        <div className="mt-1 flex flex-wrap gap-1">
                          {dayMeetings.slice(0, 3).map((m) => (
                            <span
                              key={m.id}
                              className={cn(
                                "h-1.5 w-1.5 rounded-full",
                                m.status === "active"
                                  ? "bg-green-400"
                                  : m.status === "scheduled"
                                    ? "bg-blue-400"
                                    : "bg-gray-500"
                              )}
                            />
                          ))}
                          {dayMeetings.length > 3 && (
                            <span className="text-[10px] text-gray-500">
                              +{dayMeetings.length - 3}
                            </span>
                          )}
                        </div>
                      )}
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Selected Day Detail */}
          {selectedDate && (
            <Card>
              <CardContent className="py-4">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-sm font-semibold text-gray-50">
                    {selectedDate.toLocaleDateString(undefined, {
                      weekday: "long",
                      month: "long",
                      day: "numeric",
                      year: "numeric",
                    })}
                  </h2>
                  <Button size="sm" onClick={openSchedule}>
                    Schedule Meeting
                  </Button>
                </div>

                {selectedMeetings.length === 0 ? (
                  <p className="text-sm text-gray-500 py-4 text-center">
                    No meetings on this day.
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {selectedMeetings.map((m) => (
                      <li
                        key={m.id}
                        className="flex items-center justify-between rounded-lg border border-gray-800 px-3 py-2"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-gray-200 truncate">
                            {m.title || "Untitled Meeting"}
                          </p>
                          <p className="text-xs text-gray-500">
                            {new Date(m.scheduled_at).toLocaleTimeString(
                              undefined,
                              { hour: "numeric", minute: "2-digit" }
                            )}
                          </p>
                        </div>
                        <span
                          className={cn(
                            "ml-2 inline-flex flex-shrink-0 items-center rounded-md px-2 py-0.5 text-[10px] font-medium",
                            m.status === "active"
                              ? "bg-green-600/20 text-green-400 border border-green-500/30"
                              : m.status === "completed"
                                ? "bg-blue-600/20 text-blue-400 border border-blue-500/30"
                                : "bg-gray-600/20 text-gray-400 border border-gray-500/30"
                          )}
                        >
                          {m.status.charAt(0).toUpperCase() + m.status.slice(1)}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Schedule Meeting Dialog */}
      <Dialog open={showCreate} onClose={() => setShowCreate(false)}>
        <form onSubmit={handleCreate}>
          <DialogTitle>
            Schedule Meeting —{" "}
            {selectedDate?.toLocaleDateString(undefined, {
              month: "short",
              day: "numeric",
            })}
          </DialogTitle>
          <div className="space-y-4">
            <Input
              label="Title"
              placeholder="Weekly standup"
              value={createTitle}
              onChange={(e) => setCreateTitle(e.target.value)}
              required
            />
            <Input
              label="Time"
              type="time"
              value={createTime}
              onChange={(e) => setCreateTime(e.target.value)}
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

/* ─── Icons ──────────────────────────────────────────────────────────────── */

function ChevronLeftIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5 8.25 12l7.5-7.5" />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
      <path strokeLinecap="round" strokeLinejoin="round" d="m8.25 4.5 7.5 7.5-7.5 7.5" />
    </svg>
  );
}
