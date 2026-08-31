import { cn } from "@/lib/utils";

interface ScoreBarProps {
  label: string;
  value: number;
  className?: string;
  tone?: "accent" | "cyan";
}

export function ScoreBar({ label, value, className, tone = "accent" }: ScoreBarProps) {
  const clamped = Math.max(0, Math.min(100, value));
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <span className="w-24 shrink-0 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">{label}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2 border border-border">
        <div
          className={cn("h-full rounded-full", tone === "accent" ? "bg-accent" : "bg-cyan")}
          style={{ width: `${clamped}%` }}
        />
      </div>
      <span className="w-8 shrink-0 text-right font-mono text-xs tabular-nums text-ink-muted">
        {Math.round(clamped)}
      </span>
    </div>
  );
}
