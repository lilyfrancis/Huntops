import type { HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "accent" | "good" | "warning" | "danger" | "cyan";

const toneClasses: Record<Tone, string> = {
  neutral: "bg-surface-2 text-ink-muted border-border-strong",
  accent: "bg-accent-soft text-accent-strong border-accent/30",
  good: "bg-good-soft text-good border-good/30",
  warning: "bg-warning-soft text-warning border-warning/30",
  danger: "bg-danger-soft text-danger border-danger/30",
  cyan: "bg-cyan-soft text-cyan border-cyan/30",
};

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone;
}

export function Badge({ className, tone = "neutral", ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-md border px-2 py-0.5 font-mono text-[0.7rem] font-medium uppercase tracking-wide",
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}
