/**
 * Kutana "Rosette" logo mark — an 8-petal rosette (Swahili door motif)
 * with a green→purple gradient on a black rounded-rect background.
 *
 * Source: Figma "Kutana AI — Icon Exploration", node 44:14.
 */

interface LogoMarkProps {
  /** Width/height in pixels. Default: 28 */
  size?: number;
  /** Render on transparent background (no rounded rect fill). Default: false */
  bare?: boolean;
  className?: string;
}

export function KutanaRosetteMark({ size = 28, bare = false, className }: LogoMarkProps) {
  const gradId = "kutana-rosette-gradient";
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 512 512"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-label="Kutana"
    >
      <defs>
        <linearGradient id={gradId} x1="512" y1="512" x2="0" y2="0" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#16A34A" />
          <stop offset="0.5" stopColor="#2D7FB3" />
          <stop offset="1" stopColor="#9B30FF" />
        </linearGradient>
      </defs>

      {!bare && <rect width="512" height="512" rx="96" fill="#0B0B0F" />}

      <g transform="translate(256 256)" fill={`url(#${gradId})`}>
        <ellipse rx="85" ry="27.5" />
        <ellipse rx="85" ry="27.5" transform="rotate(45)" />
        <ellipse rx="85" ry="27.5" transform="rotate(90)" />
        <ellipse rx="85" ry="27.5" transform="rotate(135)" />
      </g>

      <circle cx="256" cy="256" r="20" fill="#E5E7EB" />
    </svg>
  );
}

// Back-compat aliases so existing callsites keep working.
export const KutanaKMark = KutanaRosetteMark;
export const KutanaLogoMark = KutanaRosetteMark;
