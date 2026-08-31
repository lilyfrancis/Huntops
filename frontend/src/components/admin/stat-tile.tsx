import type { LucideIcon } from "lucide-react";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface StatTileProps {
  icon: LucideIcon;
  label: string;
  value: string | number;
  sub?: string;
  tone?: "default" | "good" | "danger";
}

export function StatTile({ icon: Icon, label, value, sub, tone = "default" }: StatTileProps) {
  return (
    <Card className="p-4">
      <div className="mb-2 flex items-center gap-2 text-ink-faint">
        <Icon className="h-3.5 w-3.5" />
        <span className="font-mono text-[0.65rem] uppercase tracking-wide">{label}</span>
      </div>
      <p
        className={cn(
          "font-mono text-2xl font-semibold tabular-nums",
          tone === "good" && "text-good",
          tone === "danger" && "text-danger",
          tone === "default" && "text-ink"
        )}
      >
        {value}
      </p>
      {sub && <p className="mt-1 text-xs text-ink-muted">{sub}</p>}
    </Card>
  );
}
