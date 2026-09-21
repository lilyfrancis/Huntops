import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Reveal } from "@/components/landing/reveal";
import { useReveal } from "@/hooks/use-reveal";
import { billingApi } from "@/lib/api";
import type { CreditCosts, Plan, SubscriptionTier } from "@/lib/types";

/* Every number on this chart is served, never written here. The counts are
   plan credits divided by what the backend actually charges for the action,
   so the page cannot advertise a month's worth of work the product will then
   refuse to do. If either call fails the section removes itself rather than
   showing invented arithmetic. */

/* Three categorical hues, one per plan. Checked with the palette validator
   rather than chosen by eye: all three clear the lightness band and the
   chroma floor, the worst adjacent pair separates by ΔE 17.4 under deuteranopia
   (target >= 8) and 23.3 under normal vision, and all three clear 3:1 against
   the surface. Colour follows the plan, never the bar's rank, so the order
   below is fixed. */
const PLAN_STYLE: Record<string, { name: string; hue: string }> = {
  free: { name: "Free", hue: "#b06a00" },
  pro: { name: "Pro", hue: "#6f5afb" },
  elite: { name: "Elite", hue: "#0e9fb0" },
};
const PLAN_ORDER: SubscriptionTier[] = ["free", "pro", "elite"];

const ACTIONS = [
  {
    key: "concierge" as const,
    label: "Apply for me",
    note: "We fill in the form on the board and file it under your name.",
  },
  {
    key: "tailor" as const,
    label: "Tailor my CV",
    note: "Your CV rewritten for that one role, with a cover letter.",
  },
  {
    key: "unlock" as const,
    label: "Unlock a job",
    note: "The company, the full title and the link, kept for good.",
  },
];

interface Row {
  action: string;
  note: string;
  cost: number;
  counts: { tier: SubscriptionTier; name: string; hue: string; n: number }[];
}

function buildRows(plans: Plan[], costs: CreditCosts): Row[] {
  const byTier = new Map(plans.map((p) => [p.tier, p]));
  return ACTIONS.map((a) => ({
    action: a.label,
    note: a.note,
    cost: costs[a.key],
    counts: PLAN_ORDER.flatMap((tier) => {
      const plan = byTier.get(tier);
      const style = PLAN_STYLE[tier];
      if (!plan || !style || costs[a.key] <= 0) return [];
      return [{ tier, name: style.name, hue: style.hue, n: Math.floor(plan.credits / costs[a.key]) }];
    }),
  })).filter((r) => r.counts.length > 0);
}

export function CreditsChart() {
  const { ref, isVisible } = useReveal<HTMLDivElement>();
  const [hover, setHover] = useState<string | null>(null);

  const plansQuery = useQuery({
    queryKey: ["billing", "plans"],
    queryFn: billingApi.plans,
    retry: false,
  });
  const costsQuery = useQuery({
    queryKey: ["billing", "credit-costs"],
    queryFn: billingApi.creditCosts,
    retry: false,
  });

  if (!plansQuery.data || !costsQuery.data) return null;
  const rows = buildRows(plansQuery.data, costsQuery.data);
  if (rows.length === 0) return null;

  // One scale across the whole figure. Free's bars really are slivers next to
  // Elite's — that is the honest shape of 15 credits against 1,000 — so every
  // bar carries its number at the tip and the axis ticks are dropped.
  const max = Math.max(...rows.flatMap((r) => r.counts.map((c) => c.n)), 1);
  const credits = new Map(plansQuery.data.map((p) => [p.tier, p.credits]));

  return (
    <section className="relative isolate overflow-hidden bg-bg-tint py-28 lg:py-36">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -right-52 top-0 h-[30rem] w-[30rem] rounded-full bg-violet-soft blur-[120px]" />
        <div className="absolute -left-40 bottom-0 h-[26rem] w-[26rem] rounded-full bg-cyan-soft blur-[120px]" />
      </div>

      <div className="shell">
        <div className="grid gap-12 lg:grid-cols-[0.85fr_1.15fr] lg:items-start lg:gap-20">
          <Reveal>
            <span className="eyebrow t-eyebrow-lg">Credits</span>
            <h2 className="t-h2 mt-4">One month of credits, counted out</h2>
            <p className="t-lead mt-5 text-ink-muted">
              Credits are the only thing you spend. No action is locked behind a tier — a
              free account and an Elite account can do exactly the same things, and the
              plan decides only how much of it fits in a month.
            </p>
            <dl className="mt-9 space-y-4">
              {ACTIONS.map((a) => (
                <div key={a.key} className="flex items-baseline justify-between gap-6 border-b border-border pb-3">
                  <dt className="t-body font-semibold text-ink">{a.label}</dt>
                  <dd className="whitespace-nowrap font-mono text-sm text-ink-muted">
                    {costsQuery.data[a.key]} credits
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-6 text-sm leading-relaxed text-ink-muted">
              Run out mid-month and you top up from the wallet — you do not have to
              change plan to keep going.
            </p>
            <a
              href="#pricing"
              className="mt-5 inline-flex items-center gap-1.5 text-sm font-semibold text-violet-dark hover:underline"
            >
              See the plans <span aria-hidden>&rarr;</span>
            </a>
          </Reveal>

          <Reveal delay={1}>
            <figure
              ref={ref}
              className="glass-light rounded-2xl p-6 lift sm:p-9"
              aria-describedby="credits-chart-caption"
            >
              <figcaption className="flex flex-wrap items-baseline justify-between gap-x-6 gap-y-3">
                <p className="t-h3 font-display font-bold text-ink">
                  How many, per month
                </p>
                {/* Identity never rests on colour alone: the legend names every
                    series and each bar is labelled in the table below. */}
                <ul className="flex flex-wrap items-center gap-x-5 gap-y-2">
                  {PLAN_ORDER.map((tier) => {
                    const style = PLAN_STYLE[tier];
                    const c = credits.get(tier);
                    if (!style || c === undefined) return null;
                    return (
                      <li key={tier} className="flex items-center gap-2 text-sm text-ink-muted">
                        <span
                          aria-hidden
                          className="h-2.5 w-2.5 rounded-full"
                          style={{ background: style.hue }}
                        />
                        {style.name}
                        <span className="font-mono text-xs text-ink-faint">
                          {c.toLocaleString()} cr
                        </span>
                      </li>
                    );
                  })}
                </ul>
              </figcaption>

              <div className="mt-8 space-y-8">
                {rows.map((row) => (
                  <div key={row.action}>
                    <p className="text-sm font-semibold text-ink">{row.action}</p>
                    <div className="mt-3 space-y-[2px]">
                      {row.counts.map((c) => {
                        const id = `${row.action}-${c.tier}`;
                        return (
                          <div
                            key={c.tier}
                            className="relative flex items-center gap-3"
                            onMouseEnter={() => setHover(id)}
                            onMouseLeave={() => setHover(null)}
                            onFocus={() => setHover(id)}
                            onBlur={() => setHover(null)}
                            tabIndex={0}
                          >
                            <span className="w-12 shrink-0 text-right text-[0.8rem] text-ink-faint">
                              {c.name}
                            </span>
                            <div className="relative h-5 min-w-0 flex-1">
                              <div
                                className="h-full rounded-r-[4px] transition-[width] duration-[900ms] ease-out"
                                style={{
                                  // Scaled against the track less the room the
                                  // number needs, so the label always sits at
                                  // the tip instead of being pushed off the
                                  // end. A count of 3 against a scale of 200 is
                                  // a two-pixel smear, so the floor keeps the
                                  // mark visible; the number is what is read.
                                  width: isVisible
                                    ? `max(8px, calc((100% - 3.5rem) * ${c.n / max}))`
                                    : "0%",
                                  background: c.hue,
                                }}
                              />
                              <span
                                className="pointer-events-none absolute top-1/2 -translate-y-1/2 pl-2 font-mono text-sm tabular-nums text-ink transition-[left] duration-[900ms] ease-out"
                                style={{
                                  left: isVisible
                                    ? `max(8px, calc((100% - 3.5rem) * ${c.n / max}))`
                                    : "0",
                                }}
                              >
                                {c.n.toLocaleString()}
                              </span>
                              {hover === id && (
                                <div
                                  role="tooltip"
                                  className="absolute left-0 top-7 z-10 w-max max-w-xs rounded-lg bg-navy px-3 py-2 text-xs leading-relaxed text-white/85 shadow-lg"
                                >
                                  <strong className="font-semibold text-white">
                                    {c.name}: {c.n.toLocaleString()} × {row.action.toLowerCase()}
                                  </strong>
                                  <br />
                                  {(credits.get(c.tier) ?? 0).toLocaleString()} credits ÷ {row.cost} each
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>

              <p id="credits-chart-caption" className="mt-8 text-sm leading-relaxed text-ink-muted">
                Each bar is a whole month spent on that one action. In practice you mix
                them, and unspent credits are gone at the end of the month.
              </p>

              {/* The numbers are never gated behind a hover. */}
              <details className="mt-4 text-sm">
                <summary className="cursor-pointer font-medium text-violet-dark">
                  Show the numbers
                </summary>
                <table className="mt-3 w-full border-collapse text-left">
                  <thead>
                    <tr>
                      <th scope="col" className="border-b border-border py-2 pr-3 font-semibold">
                        Action
                      </th>
                      <th scope="col" className="border-b border-border py-2 pr-3 font-semibold">
                        Credits
                      </th>
                      {PLAN_ORDER.map((tier) => (
                        <th
                          key={tier}
                          scope="col"
                          className="border-b border-border py-2 pr-3 text-right font-semibold"
                        >
                          {PLAN_STYLE[tier]?.name}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="text-ink-muted">
                    {rows.map((row) => (
                      <tr key={row.action}>
                        <th scope="row" className="border-b border-border py-2 pr-3 font-normal">
                          {row.action}
                        </th>
                        <td className="border-b border-border py-2 pr-3 font-mono">{row.cost}</td>
                        {row.counts.map((c) => (
                          <td
                            key={c.tier}
                            className="border-b border-border py-2 pr-3 text-right font-mono tabular-nums"
                          >
                            {c.n.toLocaleString()}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>
            </figure>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
