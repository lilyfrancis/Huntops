import { format, parseISO } from "date-fns";

/*
  Activity is a magnitude-over-time grid, so it takes a SEQUENTIAL single-hue
  ramp. Today the backend reports activity as a boolean per day, so only the
  top step is in use — the ramp is here so intensity levels can land later
  without re-picking colors. Validated against the dark card surface (#121a24):
  monotone L, adjacent ΔL >= 0.06, light-end contrast 2.26:1.
*/
const RAMP = ["#275a5e", "#347f85", "#40a3a9", "#4fc3c9"];
const EMPTY = "var(--color-surface-2)";

export function ActivityHeatmap({ days }: { days: { date: string; active: boolean }[] }) {
  // Column-major weeks: 8 columns of 7 days, oldest week first.
  const weeks: (typeof days)[] = [];
  for (let i = 0; i < days.length; i += 7) weeks.push(days.slice(i, i + 7));

  return (
    // Grid and footer share one inline-block, so the date labels line up with
    // the grid's real edges rather than the card's.
    <div className="mx-auto w-fit">
      {/*
        Fixed cell size, not flex-1: letting the cells stretch to the container
        turns a calendar grid into a wall of 70px blocks. 2px surface gaps do
        the separating — no borders on the cells.
      */}
      <div
        className="flex justify-center gap-[2px] overflow-x-auto"
        role="img"
        aria-label="Daily activity over the last 8 weeks"
      >
        {weeks.map((week, wi) => (
          <div key={wi} className="flex flex-col gap-[2px]">
            {week.map((day) => (
              <div
                key={day.date}
                className="h-3.5 w-3.5 rounded-[2px]"
                style={{ background: day.active ? RAMP[3] : EMPTY }}
                title={`${format(parseISO(day.date), "d MMM yyyy")} — ${day.active ? "active" : "no activity"}`}
              />
            ))}
          </div>
        ))}
      </div>

      <div className="mt-3 flex items-center justify-between gap-6">
        <span className="font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">
          {format(parseISO(days[0].date), "d MMM")}
        </span>
        <div className="flex items-center gap-1.5">
          <span className="font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">Quiet</span>
          <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: EMPTY }} />
          <span className="h-2.5 w-2.5 rounded-[2px]" style={{ background: RAMP[3] }} />
          <span className="font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">Active</span>
        </div>
        <span className="font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">
          {format(parseISO(days[days.length - 1].date), "d MMM")}
        </span>
      </div>
    </div>
  );
}
