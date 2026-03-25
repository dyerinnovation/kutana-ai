/**
 * Convene AI logo mark — a C-arc ring with an AI node dot in the gap.
 *
 * Concept: the arc represents meeting participants arranged in a circle
 * (with a gap); the dot in the gap is the AI agent connecting to the meeting.
 *
 * The gradient background variant (default) uses a signal-green emerald fill.
 * The bare variant (bare=true) renders just the mark on a transparent bg,
 * useful for embedding inside an already-colored container.
 */
interface LogoMarkProps {
  /** Width/height in pixels. Default: 28 */
  size?: number;
  /** Render on transparent background (no rounded rect fill). Default: false */
  bare?: boolean;
  className?: string;
}

export function ConveneLogoMark({ size = 28, bare = false, className }: LogoMarkProps) {
  // Arc geometry: center (14,14), radius 7
  // Opening on the right — gap spans roughly 45° to 315° (clockwise through right)
  // Arc endpoints: at ±45° from the right side (i.e., 315° and 45°)
  //   315°: x = 14 + 7*cos(315°) = 18.95,  y = 14 + 7*sin(315°) = 9.05
  //    45°: x = 18.95,                       y = 18.95
  // SVG arc: large-arc=1, sweep=0 (CCW) traverses the long way through the left.
  // AI node dot sits at the midpoint of the gap: rightmost point (21, 14).
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 28 28"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Convene AI"
    >
      <defs>
        <linearGradient
          id="convene-logo-gradient"
          x1="0"
          y1="0"
          x2="28"
          y2="28"
          gradientUnits="userSpaceOnUse"
        >
          <stop stopColor="#6ee7b7" />
          <stop offset="1" stopColor="#059669" />
        </linearGradient>
      </defs>

      {/* Background — omitted in bare mode */}
      {!bare && (
        <rect width="28" height="28" rx="7" fill="url(#convene-logo-gradient)" />
      )}

      {/* C-arc: participants in a meeting ring */}
      <path
        d="M18.95 9.05 A7 7 0 1 0 18.95 18.95"
        stroke="white"
        strokeWidth="2.25"
        strokeLinecap="round"
      />

      {/* AI node dot: the agent connecting to the meeting */}
      <circle cx="21" cy="14" r="1.75" fill="white" />
    </svg>
  );
}
