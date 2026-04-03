import { useEffect, useState } from "react";
import type { Meeting } from "@/types";
import { listMeetings } from "@/api/meetings";
import { Button } from "@/components/ui/Button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/Card";

const DAYS_OF_WEEK = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

function getDaysInMonth(year: number, month: number): number {
  return new Date(year, month + 1, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 1).getDay();
}

function formatMonthYear(year: number, month: number): string {
  return new Date(year, month).toLocaleDateString(undefined, {
    month: "long",
    year: "numeric",
  });
}

function dateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formatTime(dateStr: string): string {
  return new Date(dateStr).toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  });
}

export function CalendarPage() {
  const today = new Date();
  const [year, setYear] = useState(today.getFullYear());
  const [month, setMonth] = useState(today.getMonth());
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await listMeetings();
        setMeetings(res.items);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load meetings",
        );
      } finally {
        setIsLoading(false);
      }
    }
    load();
  }, []);

  // Build a set of date keys that have meetings
  const meetingsByDay = new Map<string, Meeting[]>();
  for (const m of meetings) {
    const key = dateKey(new Date(m.scheduled_at));
    const existing = meetingsByDay.get(key);
    if (existing) {
      existing.push(m);
    } else {
      meetingsByDay.set(key, [m]);
    }
  }

  function goToPrevMonth() {
    if (month === 0) {
      setMonth(11);
      setYear(year - 1);
    } else {
      setMonth(month - 1);
    }
  }

  function goToNextMonth() {
    if (month === 11) {
      setMonth(0);
      setYear(year + 1);
    } else {
      setMonth(month + 1);
    }
  }

  // Build grid cells
  const daysInMonth = getDaysInMonth(year, month);
  const firstDay = getFirstDayOfMonth(year, month);

  // Previous month trailing days
  const prevMonth = month === 0 ? 11 : month - 1;
  const prevYear = month === 0 ? year - 1 : year;
  const daysInPrevMonth = getDaysInMonth(prevYear, prevMonth);

  const cells: Array<{
    day: number;
    month: number;
    year: number;
    isCurrentMonth: boolean;
    key: string;
  }> = [];

  // Leading days from previous month
  for (let i = firstDay - 1; i >= 0; i--) {
    const d = daysInPrevMonth - i;
    cells.push({
      day: d,
      month: prevMonth,
      year: prevYear,
      isCurrentMonth: false,
      key: `${prevYear}-${String(prevMonth + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
    });
  }

  // Current month days
  for (let d = 1; d <= daysInMonth; d++) {
    cells.push({
      day: d,
      month,
      year,
      isCurrentMonth: true,
      key: `${year}-${String(month + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
    });
  }

  // Trailing days from next month
  const nextMonth = month === 11 ? 0 : month + 1;
  const nextYear = month === 11 ? year + 1 : year;
  const remaining = 42 - cells.length; // 6 rows * 7 cols
  for (let d = 1; d <= remaining; d++) {
    cells.push({
      day: d,
      month: nextMonth,
      year: nextYear,
      isCurrentMonth: false,
      key: `${nextYear}-${String(nextMonth + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}`,
    });
  }

  const todayKey = dateKey(today);
  const selectedMeetings = selectedDay ? (meetingsByDay.get(selectedDay) ?? []) : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-50">Calendar</h1>
        <p className="mt-1 text-sm text-gray-400">
          View scheduled meetings by date
        </p>
      </div>

      {error && (
        <div className="rounded-lg border border-red-800 bg-red-950/50 px-4 py-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {isLoading && (
        <div className="py-12 text-center text-gray-400">
          Loading calendar...
        </div>
      )}

      {!isLoading && (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <Button variant="outline" size="sm" onClick={goToPrevMonth}>
                  <ChevronLeftIcon />
                </Button>
                <CardTitle>{formatMonthYear(year, month)}</CardTitle>
                <Button variant="outline" size="sm" onClick={goToNextMonth}>
                  <ChevronRightIcon />
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              {/* Day-of-week headers */}
              <div className="grid grid-cols-7 gap-px rounded-t-lg bg-gray-700">
                {DAYS_OF_WEEK.map((d) => (
                  <div
                    key={d}
                    className="bg-gray-900 py-2 text-center text-xs font-medium text-gray-400"
                  >
                    {d}
                  </div>
                ))}
              </div>

              {/* Day cells */}
              <div className="grid grid-cols-7 gap-px bg-gray-700">
                {cells.map((cell) => {
                  const hasMeetings = meetingsByDay.has(cell.key);
                  const isToday = cell.key === todayKey;
                  const isSelected = cell.key === selectedDay;

                  return (
                    <button
                      key={cell.key}
                      onClick={() => setSelectedDay(cell.key)}
                      className={`relative flex min-h-[3.5rem] flex-col items-center justify-start bg-gray-950 px-1 pt-2 text-sm transition-colors hover:bg-gray-800 ${
                        isSelected
                          ? "bg-emerald-600 text-white hover:bg-emerald-500"
                          : isToday
                            ? "ring-1 ring-inset ring-emerald-500"
                            : ""
                      } ${
                        cell.isCurrentMonth
                          ? isSelected
                            ? "text-white"
                            : "text-gray-50"
                          : "text-gray-600"
                      }`}
                    >
                      <span
                        className={`${
                          isSelected
                            ? "flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500 text-white"
                            : isToday
                              ? "flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400"
                              : ""
                        }`}
                      >
                        {cell.day}
                      </span>
                      {hasMeetings && (
                        <span className="mt-1 h-1.5 w-1.5 rounded-full bg-emerald-500" />
                      )}
                    </button>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {/* Selected day meeting list */}
          {selectedDay && (
            <div className="space-y-3">
              <h2 className="text-lg font-semibold text-gray-50">
                {new Date(selectedDay + "T00:00:00").toLocaleDateString(
                  undefined,
                  {
                    weekday: "long",
                    month: "long",
                    day: "numeric",
                    year: "numeric",
                  },
                )}
              </h2>

              {selectedMeetings.length === 0 ? (
                <Card>
                  <CardContent className="py-8 text-center">
                    <p className="text-gray-400">
                      No meetings scheduled for this day.
                    </p>
                  </CardContent>
                </Card>
              ) : (
                selectedMeetings.map((meeting) => (
                  <Card key={meeting.id}>
                    <CardHeader>
                      <div className="flex items-start justify-between">
                        <div>
                          <CardTitle>{meeting.title}</CardTitle>
                          <p className="mt-1 text-sm text-gray-400">
                            {formatTime(meeting.scheduled_at)}
                          </p>
                        </div>
                        <span
                          className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${
                            meeting.status === "active"
                              ? "border-green-500/30 bg-green-600/20 text-green-400"
                              : meeting.status === "completed"
                                ? "border-blue-500/30 bg-blue-600/20 text-blue-400"
                                : "border-gray-500/30 bg-gray-600/20 text-gray-400"
                          }`}
                        >
                          {meeting.status}
                        </span>
                      </div>
                    </CardHeader>
                  </Card>
                ))
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ── Icons ──────────────────────────────────────────────────────── */

function ChevronLeftIcon() {
  return (
    <svg
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M15.75 19.5 8.25 12l7.5-7.5"
      />
    </svg>
  );
}

function ChevronRightIcon() {
  return (
    <svg
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="m8.25 4.5 7.5 7.5-7.5 7.5"
      />
    </svg>
  );
}
