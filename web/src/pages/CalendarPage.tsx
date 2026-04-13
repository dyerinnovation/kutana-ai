import { useEffect, useRef, useState, type FormEvent } from "react";
import type { Meeting } from "@/types";
import { listMeetings, createMeeting } from "@/api/meetings";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { TimeSelect, defaultUpcomingHalfHourTime } from "@/components/ui/DateTimePicker";
import { Card, CardContent } from "@/components/ui/Card";
import { Dialog, DialogTitle, DialogFooter } from "@/components/ui/Dialog";
import { cn } from "@/lib/utils";

const DAY_NAMES = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const CELLS = 42; // 6 rows × 7 cols
const HOUR_START = 7;
const HOUR_END = 21; // 9pm exclusive → 7am-9pm = 15 slots

type ViewMode = "month" | "week" | "workweek" | "day";

/* ─── Helpers ────────────────────────────────────────────────────────────── */

function formatDateKey(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function getWeekStart(date: Date): Date {
  const d = new Date(date);
  d.setDate(d.getDate() - d.getDay()); // Sunday
  return d;
}

function getWeekDates(start: Date, count: number): Date[] {
  return Array.from({ length: count }, (_, i) => {
    const d = new Date(start);
    d.setDate(d.getDate() + i);
    return d;
  });
}

function formatTimeSlot(hour: number): string {
  const h = hour % 12 || 12;
  const ampm = hour < 12 ? "AM" : "PM";
  return `${h} ${ampm}`;
}

function exportMeetingIcs(meeting: Meeting) {
  const start = new Date(meeting.scheduled_at);
  const end = new Date(start.getTime() + 60 * 60 * 1000); // 1 hour default
  const fmt = (d: Date) =>
    d
      .toISOString()
      .replace(/[-:]/g, "")
      .replace(/\.\d{3}/, "");

  const ics = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//Kutana//Meeting//EN",
    "BEGIN:VEVENT",
    `DTSTART:${fmt(start)}`,
    `DTEND:${fmt(end)}`,
    `SUMMARY:${meeting.title || "Kutana Meeting"}`,
    `UID:${meeting.id}@kutana.ai`,
    "END:VEVENT",
    "END:VCALENDAR",
  ].join("\r\n");

  const blob = new Blob([ics], { type: "text/calendar" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${(meeting.title || "meeting").replace(/\s+/g, "-").toLowerCase()}.ics`;
  a.click();
  URL.revokeObjectURL(url);
}

function statusColor(status: string) {
  if (status === "active") return "bg-green-400";
  if (status === "scheduled") return "bg-blue-400";
  return "bg-gray-500";
}

// Meeting block colors.
// Rule: green = active (in progress), blue = scheduled (upcoming),
// gray = completed/other. Legend rendered in the calendar header.
function statusBlockColor(status: string) {
  if (status === "active")
    return "bg-green-500/25 border-green-400/60 text-green-50";
  if (status === "scheduled")
    return "bg-blue-500/25 border-blue-400/60 text-blue-50";
  return "bg-gray-500/25 border-gray-400/60 text-gray-100";
}

function StatusLegend() {
  const items: Array<{ label: string; dot: string }> = [
    { label: "Active", dot: "bg-green-400" },
    { label: "Scheduled", dot: "bg-blue-400" },
    { label: "Completed", dot: "bg-gray-400" },
  ];
  return (
    <div className="flex items-center gap-3 text-[11px] text-gray-400">
      {items.map((it) => (
        <span key={it.label} className="inline-flex items-center gap-1.5">
          <span className={cn("h-2 w-2 rounded-full", it.dot)} />
          {it.label}
        </span>
      ))}
    </div>
  );
}

/* ─── Component ──────────────────────────────────────────────────────────── */

export function CalendarPage() {
  const [viewMode, setViewMode] = useState<ViewMode>("week");
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
  const [createTime, setCreateTime] = useState(() => defaultUpcomingHalfHourTime());
  const [isCreating, setIsCreating] = useState(false);

  // Current time indicator (updates every minute)
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 60_000);
    return () => clearInterval(id);
  }, []);

  // Hover indicator for time grid
  const [hoverInfo, setHoverInfo] = useState<{ col: number; hour: number } | null>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  // Drag-to-create state
  const [dragStart, setDragStart] = useState<{ col: number; hour: number } | null>(null);
  const [dragEnd, setDragEnd] = useState<{ col: number; hour: number } | null>(null);
  const isDragging = dragStart !== null;

  // Schedule meeting dialog — extended fields
  const [createDescription, setCreateDescription] = useState("");
  const [createEndTime, setCreateEndTime] = useState(() => {
    const [h, m] = defaultUpcomingHalfHourTime().split(":").map(Number);
    const endH = Math.min(h + 1, HOUR_END);
    return `${String(endH).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
  });

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

  const today = new Date();
  const todayStr = formatDateKey(today);

  // The "reference date" used for week/day views
  const refDate = selectedDate ?? today;

  // Build the month calendar grid
  const year = currentMonth.getFullYear();
  const month = currentMonth.getMonth();
  const firstDay = new Date(year, month, 1);
  const startOffset = firstDay.getDay();

  const dates: Date[] = [];
  for (let i = 0; i < CELLS; i++) {
    const d = new Date(year, month, 1 - startOffset + i);
    dates.push(d);
  }

  /* ─── Navigation ─────────────────────────────────────────────────────── */

  function prev() {
    if (viewMode === "month") {
      setCurrentMonth(new Date(year, month - 1, 1));
      setSelectedDate(null);
    } else if (viewMode === "week" || viewMode === "workweek") {
      const d = new Date(refDate);
      d.setDate(d.getDate() - 7);
      setSelectedDate(d);
    } else {
      const d = new Date(refDate);
      d.setDate(d.getDate() - 1);
      setSelectedDate(d);
    }
  }

  function next() {
    if (viewMode === "month") {
      setCurrentMonth(new Date(year, month + 1, 1));
      setSelectedDate(null);
    } else if (viewMode === "week" || viewMode === "workweek") {
      const d = new Date(refDate);
      d.setDate(d.getDate() + 7);
      setSelectedDate(d);
    } else {
      const d = new Date(refDate);
      d.setDate(d.getDate() + 1);
      setSelectedDate(d);
    }
  }

  function goToday() {
    const now = new Date();
    setCurrentMonth(new Date(now.getFullYear(), now.getMonth(), 1));
    setSelectedDate(now);
  }

  /* ─── Header label ───────────────────────────────────────────────────── */

  function headerLabel(): string {
    if (viewMode === "month") {
      return currentMonth.toLocaleDateString(undefined, {
        month: "long",
        year: "numeric",
      });
    }
    if (viewMode === "week" || viewMode === "workweek") {
      const ws = getWeekStart(refDate);
      const we = new Date(ws);
      we.setDate(we.getDate() + 6);
      const fmtShort = (d: Date) =>
        d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
      const yr = we.getFullYear();
      return `${fmtShort(ws)} – ${fmtShort(we)}, ${yr}`;
    }
    // day
    return refDate.toLocaleDateString(undefined, {
      weekday: "long",
      month: "long",
      day: "numeric",
      year: "numeric",
    });
  }

  /* ─── Selected day meetings ──────────────────────────────────────────── */

  const selectedKey = selectedDate ? formatDateKey(selectedDate) : null;
  const selectedMeetings = selectedKey
    ? (meetingsByDate.get(selectedKey) ?? [])
    : [];

  function openSchedule(date?: Date, time?: string, endTime?: string) {
    const d = date ?? selectedDate ?? new Date();
    if (!selectedDate || date) setSelectedDate(d);
    setCreateTitle("");
    setCreateDescription("");
    const start = time ?? defaultUpcomingHalfHourTime();
    setCreateTime(start);
    setCreateEndTime(
      endTime ??
        (() => {
          const [sh, sm] = start.split(":").map(Number);
          const endH = Math.min(sh + 1, HOUR_END);
          return `${String(endH).padStart(2, "0")}:${String(sm).padStart(2, "0")}`;
        })(),
    );
    setShowCreate(true);
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

  /* ─── Time grid views (week / workweek / day) ───────────────────────── */

  function renderTimeGrid(columnDates: Date[]) {
    const hours = Array.from(
      { length: HOUR_END - HOUR_START },
      (_, i) => HOUR_START + i
    );
    const hourHeight = 60; // px per hour

    return (
      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <div className="min-w-[600px]">
            {/* Column headers */}
            <div
              className="grid border-b border-gray-800"
              style={{
                gridTemplateColumns: `60px repeat(${columnDates.length}, 1fr)`,
              }}
            >
              <div className="py-2 text-center text-xs text-gray-500" />
              {columnDates.map((d) => {
                const key = formatDateKey(d);
                const isToday = key === todayStr;
                return (
                  <div
                    key={key}
                    className={cn(
                      "py-2 text-center text-xs font-medium",
                      isToday ? "text-blue-400" : "text-gray-400"
                    )}
                  >
                    <span className="uppercase">
                      {DAY_NAMES[d.getDay()]}
                    </span>
                    <br />
                    <span
                      className={cn(
                        "inline-flex h-6 w-6 items-center justify-center rounded-full text-sm font-semibold mt-0.5",
                        isToday && "bg-blue-600 text-white"
                      )}
                    >
                      {d.getDate()}
                    </span>
                  </div>
                );
              })}
            </div>

            {/* Time rows */}
            <div
              ref={gridRef}
              className="grid relative"
              style={{
                gridTemplateColumns: `60px repeat(${columnDates.length}, 1fr)`,
              }}
              onMouseMove={(e) => {
                if (!gridRef.current) return;
                const rect = gridRef.current.getBoundingClientRect();
                const y = e.clientY - rect.top;
                const totalHeight = hours.length * hourHeight;
                if (y < 0 || y > totalHeight) { setHoverInfo(null); return; }
                const hour = HOUR_START + Math.floor(y / hourHeight);
                const x = e.clientX - rect.left;
                const colWidth = (rect.width - 60) / columnDates.length;
                const col = Math.floor((x - 60) / colWidth);
                if (col < 0 || col >= columnDates.length) { setHoverInfo(null); return; }
                setHoverInfo({ col, hour });
              }}
              onMouseLeave={() => { setHoverInfo(null); if (isDragging) { setDragStart(null); setDragEnd(null); } }}
              onMouseUp={() => {
                if (dragStart && dragEnd) {
                  const startH = Math.min(dragStart.hour, dragEnd.hour);
                  const endH = Math.max(dragStart.hour, dragEnd.hour) + 1;
                  openSchedule(
                    columnDates[dragStart.col],
                    `${String(startH).padStart(2, "0")}:00`,
                    `${String(Math.min(endH, HOUR_END)).padStart(2, "0")}:00`
                  );
                }
                setDragStart(null);
                setDragEnd(null);
              }}
            >
              {/* Hour labels + horizontal lines */}
              <div className="relative">
                {hours.map((h) => (
                  <div
                    key={h}
                    className="border-b-2 border-gray-800 text-right pr-2 text-[10px] text-gray-500"
                    style={{ height: `${hourHeight}px` }}
                  >
                    {formatTimeSlot(h)}
                  </div>
                ))}
              </div>

              {/* Day columns */}
              {columnDates.map((d, colIdx) => {
                const key = formatDateKey(d);
                const dayMeetings = meetingsByDate.get(key) ?? [];
                const isHoveredCol = hoverInfo?.col === colIdx;

                // Drag selection highlight range
                const dragMinH = dragStart && dragEnd && dragStart.col === colIdx
                  ? Math.min(dragStart.hour, dragEnd.hour) : null;
                const dragMaxH = dragStart && dragEnd && dragStart.col === colIdx
                  ? Math.max(dragStart.hour, dragEnd.hour) : null;

                return (
                  <div key={key} className="relative border-l-2 border-gray-800 select-none">
                    {/* Grid lines */}
                    {hours.map((h) => {
                      const inDragRange = dragMinH !== null && dragMaxH !== null && h >= dragMinH && h <= dragMaxH;
                      return (
                        <div
                          key={h}
                          className={cn(
                            "block w-full border-b-2 border-gray-800 transition-colors cursor-pointer",
                            inDragRange
                              ? "bg-blue-600/20"
                              : isHoveredCol && hoverInfo?.hour === h
                                ? "bg-blue-600/10"
                                : "hover:bg-gray-800/30"
                          )}
                          style={{ height: `${hourHeight}px` }}
                          onMouseDown={(e) => {
                            e.preventDefault();
                            setDragStart({ col: colIdx, hour: h });
                            setDragEnd({ col: colIdx, hour: h });
                          }}
                          onMouseEnter={() => {
                            if (isDragging && dragStart?.col === colIdx) {
                              setDragEnd({ col: colIdx, hour: h });
                            }
                          }}
                          onClick={() => {
                            if (!isDragging) {
                              openSchedule(d, `${String(h).padStart(2, "0")}:00`);
                            }
                          }}
                        />
                      );
                    })}

                    {/* Meeting blocks */}
                    {dayMeetings.map((m) => {
                      const mDate = new Date(m.scheduled_at);
                      const mHour =
                        mDate.getHours() + mDate.getMinutes() / 60;
                      const top =
                        (mHour - HOUR_START) * hourHeight;
                      // Clamp within visible range
                      if (mHour < HOUR_START || mHour >= HOUR_END)
                        return null;

                      return (
                        <div
                          key={m.id}
                          className={cn(
                            "absolute left-1 right-1 rounded border px-1.5 py-0.5 text-[11px] leading-tight overflow-hidden cursor-default antialiased subpixel-antialiased",
                            statusBlockColor(m.status)
                          )}
                          style={{
                            top: `${top}px`,
                            height: `${hourHeight - 2}px`,
                            textRendering: "geometricPrecision",
                          }}
                          title={`${m.title || "Untitled"} — ${mDate.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`}
                        >
                          <p className="font-medium truncate text-white">
                            {m.title || "Untitled"}
                          </p>
                          <p className="text-[10px] text-gray-200">
                            {mDate.toLocaleTimeString(undefined, {
                              hour: "numeric",
                              minute: "2-digit",
                            })}
                          </p>
                        </div>
                      );
                    })}
                  </div>
                );
              })}

              {/* Current time indicator line */}
              {(() => {
                const nowHour = now.getHours() + now.getMinutes() / 60;
                if (nowHour < HOUR_START || nowHour >= HOUR_END) return null;
                const topPx = (nowHour - HOUR_START) * hourHeight;
                // Check if today is visible in the current columns
                const todayCol = columnDates.findIndex(
                  (d) => formatDateKey(d) === formatDateKey(now)
                );
                if (todayCol < 0) return null;
                return (
                  <div
                    className="absolute pointer-events-none"
                    style={{
                      top: `${topPx}px`,
                      left: "60px",
                      right: 0,
                      height: 0,
                    }}
                  >
                    <div className="relative w-full border-t-2 border-red-500">
                      <div className="absolute -left-1 -top-1.5 h-3 w-3 rounded-full bg-red-500" />
                    </div>
                  </div>
                );
              })()}
            </div>
          </div>
        </CardContent>
      </Card>
    );
  }

  /* ─── Render ─────────────────────────────────────────────────────────── */

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h1 className="text-2xl font-bold text-gray-50">Calendar</h1>
        <div className="flex items-center gap-2">
          {/* View mode toggle */}
          <div className="flex rounded-lg border border-gray-700 overflow-hidden">
            {(["day", "week", "workweek", "month"] as const).map((mode) => (
              <button
                key={mode}
                onClick={() => setViewMode(mode)}
                className={cn(
                  "px-3 py-1.5 text-xs font-medium transition-colors",
                  viewMode === mode
                    ? "bg-blue-600 text-white"
                    : "bg-gray-800 text-gray-400 hover:text-gray-200"
                )}
              >
                {mode === "workweek"
                  ? "Work Week"
                  : mode.charAt(0).toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>

          {/* Navigation */}
          <div className="flex items-center rounded-lg border border-gray-800 bg-gray-900">
            <button
              onClick={prev}
              className="px-3 py-2 text-gray-400 hover:text-gray-50 transition-colors"
            >
              <ChevronLeftIcon />
            </button>
            <span className="px-3 py-2 text-sm font-medium text-gray-200 min-w-[140px] text-center">
              {headerLabel()}
            </span>
            <button
              onClick={next}
              className="px-3 py-2 text-gray-400 hover:text-gray-50 transition-colors"
            >
              <ChevronRightIcon />
            </button>
          </div>
          <Button variant="outline" size="sm" onClick={goToday}>
            Today
          </Button>
          <Button size="sm" onClick={() => openSchedule()}>
            Schedule Meeting
          </Button>
        </div>
      </div>

      <div className="flex justify-end">
        <StatusLegend />
      </div>

      {isLoading ? (
        <div className="text-center py-12 text-gray-400">Loading...</div>
      ) : (
        <>
          {/* ── Month View ──────────────────────────────────────────── */}
          {viewMode === "month" && (
            <>
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
                        selectedDate &&
                        key === formatDateKey(selectedDate);
                      const dayMeetings =
                        meetingsByDate.get(key) ?? [];

                      return (
                        <button
                          key={i}
                          onClick={() => setSelectedDate(date)}
                          className={cn(
                            "h-24 border-b border-r border-gray-800/50 p-2 text-left text-sm transition-colors flex flex-col items-start",
                            isCurrentMonth
                              ? "text-gray-200"
                              : "text-gray-600",
                            isToday && "bg-blue-600/10",
                            isSelected &&
                              "bg-blue-600/15 ring-1 ring-inset ring-blue-500/50",
                            "hover:bg-gray-800/50"
                          )}
                        >
                          <span
                            className={cn(
                              "inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium",
                              isToday && "bg-blue-600 text-white"
                            )}
                          >
                            {date.getDate()}
                          </span>
                          {dayMeetings.length > 0 && (
                            <div className="mt-1 flex flex-wrap gap-1">
                              {dayMeetings
                                .slice(0, 3)
                                .map((m) => (
                                  <span
                                    key={m.id}
                                    className={cn(
                                      "h-1.5 w-1.5 rounded-full",
                                      statusColor(m.status)
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

              {/* Selected Day Detail (month view only) */}
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
                      <Button
                        size="sm"
                        onClick={() => openSchedule()}
                      >
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
                                {new Date(
                                  m.scheduled_at
                                ).toLocaleTimeString(undefined, {
                                  hour: "numeric",
                                  minute: "2-digit",
                                })}
                              </p>
                            </div>
                            <div className="flex items-center gap-2 ml-2">
                              <button
                                type="button"
                                onClick={() =>
                                  exportMeetingIcs(m)
                                }
                                className="p-1 rounded text-gray-400 hover:text-gray-200 hover:bg-gray-700/50 transition-colors"
                                title="Download .ics"
                              >
                                <CalendarDownloadIcon />
                              </button>
                              <span
                                className={cn(
                                  "inline-flex flex-shrink-0 items-center rounded-md px-2 py-0.5 text-[10px] font-medium antialiased",
                                  m.status === "active"
                                    ? "bg-green-600/40 text-green-50 border border-green-400/60"
                                    : m.status ===
                                        "completed"
                                      ? "bg-blue-600/40 text-blue-50 border border-blue-400/60"
                                      : "bg-gray-600/40 text-gray-100 border border-gray-400/60"
                                )}
                              >
                                {m.status
                                  .charAt(0)
                                  .toUpperCase() +
                                  m.status.slice(1)}
                              </span>
                            </div>
                          </li>
                        ))}
                      </ul>
                    )}
                  </CardContent>
                </Card>
              )}
            </>
          )}

          {/* ── Week View ───────────────────────────────────────────── */}
          {viewMode === "week" &&
            renderTimeGrid(getWeekDates(getWeekStart(refDate), 7))}

          {/* ── Work Week View ──────────────────────────────────────── */}
          {viewMode === "workweek" &&
            (() => {
              const ws = getWeekStart(refDate);
              const mon = new Date(ws);
              mon.setDate(mon.getDate() + 1); // Monday
              return renderTimeGrid(getWeekDates(mon, 5));
            })()}

          {/* ── Day View ────────────────────────────────────────────── */}
          {viewMode === "day" && renderTimeGrid([refDate])}
        </>
      )}

      {/* Schedule Meeting Dialog */}
      <Dialog open={showCreate} onClose={() => setShowCreate(false)}>
        <form onSubmit={handleCreate}>
          <DialogTitle>
            Schedule Meeting —{" "}
            {selectedDate?.toLocaleDateString(undefined, {
              weekday: "short",
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
            <div className="grid grid-cols-2 gap-3">
              <TimeSelect
                label="Start"
                value={createTime}
                onChange={setCreateTime}
                required
              />
              <TimeSelect
                label="End"
                value={createEndTime}
                onChange={setCreateEndTime}
              />
            </div>
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-300">
                Description
              </label>
              <textarea
                className="h-20 w-full rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 text-sm text-gray-50 placeholder:text-gray-600 focus:border-blue-500 focus:ring-1 focus:ring-blue-500/50 focus:outline-none resize-none"
                placeholder="Meeting agenda or notes..."
                value={createDescription}
                onChange={(e) => setCreateDescription(e.target.value)}
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

/* ─── Icons ──────────────────────────────────────────────────────────────── */

function ChevronLeftIcon() {
  return (
    <svg
      className="h-4 w-4"
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2}
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
      strokeWidth={2}
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

function CalendarDownloadIcon() {
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
        d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 0 1 2.25-2.25h13.5A2.25 2.25 0 0 1 21 7.5v11.25m-18 0A2.25 2.25 0 0 0 5.25 21h13.5A2.25 2.25 0 0 0 21 18.75m-18 0v-7.5A2.25 2.25 0 0 1 5.25 9h13.5A2.25 2.25 0 0 1 21 11.25v7.5m-9-6h.008v.008H12v-.008ZM12 15h.008v.008H12V15Zm0 2.25h.008v.008H12v-.008ZM9.75 15h.008v.008H9.75V15Zm0 2.25h.008v.008H9.75v-.008ZM7.5 15h.008v.008H7.5V15Zm0 2.25h.008v.008H7.5v-.008Zm6.75-4.5h.008v.008h-.008v-.008Zm0 2.25h.008v.008h-.008V15Zm0 2.25h.008v.008h-.008v-.008Zm2.25-4.5h.008v.008H16.5v-.008Zm0 2.25h.008v.008H16.5V15Z"
      />
    </svg>
  );
}
