import { AlertTriangle, Ghost } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { GhostBand } from "@/lib/types";

const CONFIG = {
  likely_ghost: { tone: "danger", icon: Ghost, label: "Likely ghost job" },
  caution: { tone: "warning", icon: AlertTriangle, label: "Worth a second look" },
} as const;

export function GhostBadge({ band }: { band: GhostBand }) {
  if (band !== "likely_ghost" && band !== "caution") return null;
  const { tone, icon: Icon, label } = CONFIG[band];
  return (
    <Badge tone={tone} className="gap-1">
      <Icon className="h-3 w-3" strokeWidth={2} />
      {label}
    </Badge>
  );
}

export function GhostReasons({ band, flags }: { band: GhostBand; flags: string[] }) {
  if (flags.length === 0 || (band !== "likely_ghost" && band !== "caution")) return null;
  const isGhost = band === "likely_ghost";
  return (
    <div
      className={`rounded-lg border p-3 ${
        isGhost ? "border-danger/30 bg-danger-soft" : "border-warning/30 bg-warning-soft"
      }`}
    >
      <p className={`font-mono text-[11px] uppercase tracking-widest ${isGhost ? "text-danger" : "text-warning"}`}>
        {isGhost ? "Why this looks like a ghost job" : "Why this is worth checking"}
      </p>
      <ul className="mt-2 space-y-1">
        {flags.map((flag) => (
          <li key={flag} className="text-sm text-ink-muted">
            — {flag}
          </li>
        ))}
      </ul>
    </div>
  );
}
