import { cn } from "@/lib/utils";

/**
 * The JobQuick AI wordmark.
 *
 * Drawn rather than shipped as artwork: the previous logo was a PNG with the
 * old name baked into the pixels, which cannot be recoloured or re-lettered.
 * An SVG costs nothing, stays sharp at any size, and takes its colour from the
 * surface it sits on — so `variant` is a real switch here rather than a second
 * file to keep in step.
 *
 * Swap this for real artwork whenever there is some; nothing else changes,
 * because every surface already goes through this component.
 */
export function Logo({
  variant = "navy",
  className,
  height = 32,
}: {
  variant?: "navy" | "white";
  className?: string;
  height?: number;
}) {
  const ink = variant === "navy" ? "#091528" : "#ffffff";
  const accent = variant === "navy" ? "#6f5afb" : "#0edbf7";
  const id = `jq-mark-${variant}`;

  return (
    <svg
      viewBox="0 0 176 36"
      height={height}
      style={{ height }}
      className={cn("w-auto select-none", className)}
      role="img"
      aria-label="JobQuick AI"
    >
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#6f5afb" />
          <stop offset="100%" stopColor="#0edbf7" />
        </linearGradient>
      </defs>

      {/* The mark: a bolt in a rounded tile — "quick", without a stopwatch. */}
      <rect x="0" y="2" width="32" height="32" rx="10" fill={`url(#${id})`} />
      <path d="M18.8 8.4 11.9 19.8h4.6l-1.9 8.2 7.5-11.9h-4.8z" fill="#ffffff" />

      <text
        x="41"
        y="25.6"
        fill={ink}
        fontFamily="'Plus Jakarta Sans', 'Inter', system-ui, sans-serif"
        fontSize="20"
        fontWeight="800"
        letterSpacing="-0.8"
      >
        JobQuick
      </text>
      <text
        x="145"
        y="25.6"
        fill={accent}
        fontFamily="'Plus Jakarta Sans', 'Inter', system-ui, sans-serif"
        fontSize="20"
        fontWeight="800"
        letterSpacing="-0.4"
      >
        AI
      </text>
    </svg>
  );
}
