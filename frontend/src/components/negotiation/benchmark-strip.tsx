import { AlertCircle } from "lucide-react";
import type { SalaryBenchmark } from "@/lib/types";

function money(value: number, currency: string) {
  return `${currency} ${Math.round(value).toLocaleString()}`;
}

/**
 * Where the offer sits against the p25–p75 band. Deliberately shows the sample
 * size and window inline: a benchmark the reader can't interrogate is just an
 * assertion, and this one may be driving a real financial decision.
 */
export function BenchmarkStrip({ data, base }: { data: SalaryBenchmark; base: number }) {
  // Pad the axis beyond the band so a marker outside p25–p75 stays on-screen.
  const low = Math.min(data.p25, base);
  const high = Math.max(data.p75, base);
  const pad = (high - low) * 0.15 || high * 0.1;
  const axisMin = low - pad;
  const axisMax = high + pad;
  const at = (value: number) => ((value - axisMin) / (axisMax - axisMin)) * 100;

  return (
    <div>
      <div className="relative h-14">
        {/* p25–p75 band, single accent hue — one measure, so no categorical colors. */}
        <div className="absolute inset-x-0 top-6 h-1.5 rounded-full bg-surface-3" />
        <div
          className="absolute top-6 h-1.5 rounded-full bg-accent/35"
          style={{ left: `${at(data.p25)}%`, width: `${at(data.p75) - at(data.p25)}%` }}
        />
        {/* Median tick */}
        <div
          className="absolute top-[1.125rem] h-4 w-0.5 rounded-full bg-accent"
          style={{ left: `${at(data.median)}%` }}
          title={`Median ${money(data.median, data.currency)}`}
        />
        {/* The offer: 10px marker with a 2px surface ring so it stays legible
            wherever it lands on the band. */}
        <div
          className="absolute top-[1.05rem] h-2.5 w-2.5 -translate-x-1/2 rounded-full bg-cyan ring-2 ring-surface"
          style={{ left: `${at(base)}%` }}
          title={`Your offer ${money(base, data.currency)}`}
        />
        <span
          className="absolute top-9 -translate-x-1/2 whitespace-nowrap font-mono text-[0.7rem] text-cyan"
          style={{ left: `${at(base)}%` }}
        >
          your offer
        </span>
      </div>

      <div className="flex justify-between font-mono text-[0.7rem] tabular-nums text-ink-muted">
        <span>{money(data.p25, data.currency)}</span>
        <span className="text-ink">{money(data.median, data.currency)} median</span>
        <span>{money(data.p75, data.currency)}</span>
      </div>

      <p className="mt-3 text-xs text-ink-faint">
        From <span className="text-ink-muted">{data.sample_size} real listings</span> in our feed
        over the last {data.lookback_days} days · cohort: {data.cohort} · {data.currency} only.
        Listings are advertised ranges, not accepted offers.
      </p>
    </div>
  );
}

export function NoBenchmarkNotice({ currency }: { currency: string }) {
  return (
    <div className="rounded-lg border border-warning/30 bg-warning-soft p-4">
      <p className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-warning">
        <AlertCircle className="h-3.5 w-3.5" /> No market data for {currency}
      </p>
      <p className="mt-2 text-sm text-ink-muted">
        We don't hold enough comparable listings to tell you what this role pays, so the coaching
        below is tactics only — it deliberately does not guess a number. For a market rate, check a
        source with real local data before you counter.
      </p>
    </div>
  );
}
