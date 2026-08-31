import type { FunnelStage } from "@/lib/types";

/*
  Funnel stages are ORDINAL, not categorical — swapping their order would change
  the meaning — so they take a single-hue ramp with monotone lightness rather
  than four unrelated hues. These four steps were validated against the app's
  dark card surface (#121a24): monotone L, adjacent ΔL >= 0.06, and a light-end
  contrast of 2.36:1, clearing the 2:1 floor.
*/
const RAMP = ["#7a4a1f", "#ab6527", "#cf7f39", "#f2994a"];

export function FunnelChart({ stages }: { stages: FunnelStage[] }) {
  const max = Math.max(...stages.map((s) => s.count), 1);

  return (
    <div className="space-y-3">
      {stages.map((stage, i) => {
        const pct = (stage.count / max) * 100;
        const dropoff =
          i > 0 && stages[i - 1].count > 0
            ? Math.round((stage.count / stages[i - 1].count) * 100)
            : null;

        return (
          <div key={stage.stage} className="flex items-center gap-3">
            <span className="w-24 shrink-0 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">
              {stage.label}
            </span>

            <div className="flex min-w-0 flex-1 items-center gap-2">
              {/* Track is the surface, so the bar's own length is the only ink. */}
              <div className="h-4 min-w-0 flex-1">
                <div
                  className="h-full rounded-r-[4px] transition-[width] duration-500"
                  style={{ width: `${Math.max(pct, stage.count > 0 ? 2 : 0)}%`, background: RAMP[i] }}
                  title={`${stage.label}: ${stage.count}`}
                />
              </div>
              {/* Value rides the tip; text keeps a text token, never the mark's hue. */}
              <span className="w-8 shrink-0 text-right font-mono text-xs tabular-nums text-ink">
                {stage.count}
              </span>
              <span className="w-12 shrink-0 text-right font-mono text-[0.7rem] tabular-nums text-ink-faint">
                {dropoff !== null ? `${dropoff}%` : ""}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
