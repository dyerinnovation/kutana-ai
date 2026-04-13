import { useEffect, useMemo, useRef, useState } from "react";
import { cn } from "@/lib/utils";

/** Returns a new Date rounded up to the next :00 or :30 slot. */
export function nearestUpcomingHalfHour(from: Date = new Date()): Date {
  const d = new Date(from);
  d.setSeconds(0, 0);
  const m = d.getMinutes();
  if (m === 0 || m === 30) {
    d.setMinutes(m + 30);
  } else if (m < 30) {
    d.setMinutes(30);
  } else {
    d.setMinutes(60);
  }
  return d;
}

/** `yyyy-MM-ddTHH:mm` (matches <input type="datetime-local">). */
export function formatDateTimeLocal(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export function formatTime(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** Default time value for modals: nearest upcoming half-hour, as HH:mm. */
export function defaultUpcomingHalfHourTime(): string {
  return formatTime(nearestUpcomingHalfHour());
}

const HALF_HOUR_SLOTS: string[] = (() => {
  const out: string[] = [];
  for (let h = 0; h < 24; h++) {
    for (const m of [0, 30]) {
      out.push(`${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`);
    }
  }
  return out;
})();

function formatTimeLabel(hhmm: string): string {
  const [h, m] = hhmm.split(":").map(Number);
  const period = h >= 12 ? "PM" : "AM";
  const h12 = h % 12 === 0 ? 12 : h % 12;
  return `${h12}:${String(m).padStart(2, "0")} ${period}`;
}

interface TimeSelectProps {
  label?: string;
  value: string; // HH:mm
  onChange: (next: string) => void;
  required?: boolean;
  id?: string;
}

export function TimeSelect({ label, value, onChange, required, id }: TimeSelectProps) {
  const selectId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
  const options = useMemo(() => {
    if (!value || HALF_HOUR_SLOTS.includes(value)) return HALF_HOUR_SLOTS;
    return [value, ...HALF_HOUR_SLOTS].sort();
  }, [value]);

  return (
    <div className="space-y-1.5">
      {label && (
        <label
          htmlFor={selectId}
          className="block text-xs font-medium uppercase tracking-widest text-gray-400"
        >
          {label}
        </label>
      )}
      <select
        id={selectId}
        value={value}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className={cn(
          "flex h-9 w-full appearance-none rounded-lg border border-gray-700 bg-gray-950 px-3 py-2 pr-8",
          "text-sm text-gray-50",
          "transition-colors duration-150",
          "focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50",
          "bg-[length:12px] bg-[right_0.75rem_center] bg-no-repeat",
          "bg-[url('data:image/svg+xml;utf8,<svg xmlns=%22http://www.w3.org/2000/svg%22 fill=%22none%22 viewBox=%220 0 24 24%22 stroke=%22%239ca3af%22 stroke-width=%222%22><path stroke-linecap=%22round%22 stroke-linejoin=%22round%22 d=%22M19 9l-7 7-7-7%22/></svg>')]",
        )}
      >
        {options.map((slot) => (
          <option key={slot} value={slot} className="bg-gray-950 text-gray-50">
            {formatTimeLabel(slot)}
          </option>
        ))}
      </select>
    </div>
  );
}

/* ── Date popover ───────────────────────────────────────────────────────── */

interface DatePickerProps {
  label?: string;
  /** yyyy-MM-dd */
  value: string;
  onChange: (next: string) => void;
  id?: string;
}

function parseDateOnly(yyyyMmDd: string): Date {
  const [y, m, d] = yyyyMmDd.split("-").map(Number);
  return new Date(y, m - 1, d);
}

function formatDateOnly(d: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function formatDateLabel(d: Date): string {
  return d.toLocaleDateString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function DatePicker({ label, value, onChange, id }: DatePickerProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const btnId = id ?? label?.toLowerCase().replace(/\s+/g, "-");

  const selected = value ? parseDateOnly(value) : null;
  const [viewMonth, setViewMonth] = useState<Date>(() => {
    const base = selected ?? new Date();
    return new Date(base.getFullYear(), base.getMonth(), 1);
  });

  useEffect(() => {
    if (!open) return;
    function onDocClick(e: MouseEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const firstDow = new Date(viewMonth.getFullYear(), viewMonth.getMonth(), 1).getDay();
  const daysInMonth = new Date(
    viewMonth.getFullYear(),
    viewMonth.getMonth() + 1,
    0,
  ).getDate();

  const cells: Array<Date | null> = [
    ...Array.from({ length: firstDow }, () => null),
    ...Array.from(
      { length: daysInMonth },
      (_, i) => new Date(viewMonth.getFullYear(), viewMonth.getMonth(), i + 1),
    ),
  ];

  return (
    <div className="relative space-y-1.5" ref={rootRef}>
      {label && (
        <label
          htmlFor={btnId}
          className="block text-xs font-medium uppercase tracking-widest text-gray-400"
        >
          {label}
        </label>
      )}
      <button
        id={btnId}
        type="button"
        onClick={() => setOpen((o) => !o)}
        className={cn(
          "flex h-9 w-full items-center justify-between rounded-lg border border-gray-700 bg-gray-950 px-3 py-2",
          "text-left text-sm text-gray-50",
          "transition-colors duration-150",
          "focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50",
          !selected && "text-gray-500",
        )}
      >
        <span>{selected ? formatDateLabel(selected) : "Pick a date"}</span>
        <svg
          className="h-4 w-4 text-gray-400"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={2}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"
          />
        </svg>
      </button>

      {open && (
        <div className="absolute left-0 z-50 mt-1 w-72 rounded-lg border border-gray-700 bg-gray-950 p-3 shadow-xl shadow-black/40">
          <div className="mb-2 flex items-center justify-between">
            <button
              type="button"
              onClick={() =>
                setViewMonth(
                  new Date(viewMonth.getFullYear(), viewMonth.getMonth() - 1, 1),
                )
              }
              className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-gray-50"
              aria-label="Previous month"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
              </svg>
            </button>
            <div className="text-sm font-medium text-gray-100">
              {viewMonth.toLocaleDateString(undefined, { month: "long", year: "numeric" })}
            </div>
            <button
              type="button"
              onClick={() =>
                setViewMonth(
                  new Date(viewMonth.getFullYear(), viewMonth.getMonth() + 1, 1),
                )
              }
              className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-gray-50"
              aria-label="Next month"
            >
              <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          </div>

          <div className="grid grid-cols-7 gap-1 text-center text-[10px] font-medium uppercase tracking-wider text-gray-500">
            {["S", "M", "T", "W", "T", "F", "S"].map((d, i) => (
              <div key={i} className="py-1">
                {d}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 gap-1">
            {cells.map((cell, i) => {
              if (!cell) return <div key={i} />;
              const isSelected =
                selected &&
                cell.getFullYear() === selected.getFullYear() &&
                cell.getMonth() === selected.getMonth() &&
                cell.getDate() === selected.getDate();
              const isToday =
                cell.getFullYear() === today.getFullYear() &&
                cell.getMonth() === today.getMonth() &&
                cell.getDate() === today.getDate();
              return (
                <button
                  key={i}
                  type="button"
                  onClick={() => {
                    onChange(formatDateOnly(cell));
                    setOpen(false);
                  }}
                  className={cn(
                    "h-8 rounded text-sm text-gray-200 hover:bg-gray-800",
                    isToday && !isSelected && "text-emerald-400",
                    isSelected && "bg-emerald-600 text-white hover:bg-emerald-600",
                  )}
                >
                  {cell.getDate()}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Combined date+time picker (replaces <input type="datetime-local">) ──── */

interface DateTimePickerProps {
  label?: string;
  /** `yyyy-MM-ddTHH:mm` */
  value: string;
  onChange: (next: string) => void;
  required?: boolean;
}

export function DateTimePicker({ label, value, onChange }: DateTimePickerProps) {
  const [datePart, timePart] = (() => {
    if (!value) return ["", ""];
    const [d, t] = value.split("T");
    return [d ?? "", (t ?? "").slice(0, 5)];
  })();

  function update(nextDate: string, nextTime: string) {
    if (!nextDate || !nextTime) return;
    onChange(`${nextDate}T${nextTime}`);
  }

  return (
    <div className="space-y-1.5">
      {label && (
        <label className="block text-xs font-medium uppercase tracking-widest text-gray-400">
          {label}
        </label>
      )}
      <div className="grid grid-cols-[1fr_auto] gap-2">
        <DatePicker
          value={datePart}
          onChange={(d) => update(d, timePart || defaultUpcomingHalfHourTime())}
        />
        <div className="w-32">
          <TimeSelect
            value={timePart}
            onChange={(t) => update(datePart || formatDateOnly(new Date()), t)}
          />
        </div>
      </div>
    </div>
  );
}
