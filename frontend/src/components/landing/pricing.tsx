import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { Reveal } from "@/components/landing/reveal";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { billingApi } from "@/lib/api";

/* Prices are served, never written here. This page and the app each had their
   own copy and they drifted — it advertised $29/$79 while the app charged
   $24/$89, which reads as a bait and switch. The fallbacks below only show if
   the API is unreachable, and say so rather than inventing a number. */
function usePrices() {
  const { data } = useQuery({ queryKey: ["billing", "plans"], queryFn: billingApi.plans, retry: false });
  return data;
}

function formatPrice(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: amount % 1 === 0 ? 0 : 2,
    }).format(amount);
  } catch {
    return `${amount.toLocaleString()} ${currency}`;
  }
}

const PLANS = [
  {
    name: "Free",
    tier: "free",
    cadence: "forever",
    features: ["Job feed for your market", "AI fit scoring", "Ghost-listing detection", "Daily digest"],
    cta: "Start free",
    featured: false,
  },
  {
    name: "Pro",
    tier: "pro",
    cadence: "/ month",
    features: [
      "Everything in Free",
      "Mock interview simulator",
      "Negotiation coach",
      "Enough credits for about 20 applications a month",
      "Priority digest placement",
    ],
    cta: "Go Pro",
    featured: true,
  },
  {
    name: "Elite",
    tier: "elite",
    cadence: "/ month",
    features: [
      "Everything in Pro",
      "Unlimited concierge applications — credits are the only limit",
      "Hiring-manager lookup and direct messages",
      "About 65 applications a month, at the best credit rate",
    ],
    cta: "Go Elite",
    featured: false,
  },
];

export function Pricing() {
  const plans = usePrices();

  const priceFor = (tier: string): string => {
    const plan = plans?.find((p) => p.tier === tier);
    // "Free" is already the card's title; repeating it as the price read as
    // a duplication rather than as a number.
    if (tier === "free") return plan ? formatPrice(plan.price, plan.currency) : "$0";
    // Never guess at a number someone will be charged.
    return plan ? formatPrice(plan.price, plan.currency) : "—";
  };

  const creditsFor = (tier: string): string => {
    const plan = plans?.find((p) => p.tier === tier);
    // Guarded rather than assumed. During a deploy the browser can hold a
    // newer bundle than the API is serving, and reading a field that is not
    // there yet took the whole landing page down — a blank marketing site
    // for the length of a rollout is a worse bug than a missing line.
    const credits = plan?.credits;
    if (typeof credits !== "number") return "";
    return tier === "free"
      ? `${credits} credits to start`
      : `${credits.toLocaleString()} credits / month`;
  };

  return (
    <section id="pricing" className="relative isolate overflow-hidden py-28 lg:py-36">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-0 h-[32rem] w-[52rem] -translate-x-1/2 rounded-full bg-violet-soft/70 blur-[130px]" />
      </div>
      <div className="shell">
      <Reveal className="mx-auto max-w-3xl text-center">
        <span className="eyebrow t-eyebrow-lg">Pricing</span>
        <h2 className="t-h2 mt-4">Pay for reach, not for looking</h2>
        <p className="t-lead mt-5 text-ink-muted">
          Every action that costs AI — a fit score, an extracted alert, a drafted outreach —
          spends credits. Upgrade when you need more reach, not because a paywall says so.
        </p>
      </Reveal>

      <div className="mx-auto mt-16 grid max-w-6xl gap-6 lg:grid-cols-3 lg:gap-7">
        {PLANS.map((plan, i) => (
          <Reveal key={plan.name} delay={i as 0 | 1 | 2}>
            <Card
              className={cn(
                "flex h-full flex-col",
                "transition-all duration-300 hover:-translate-y-1",
                plan.featured
                  // The plan we want chosen is raised off the row rather
                  // than merely outlined — an outline is easy to miss at a
                  // glance, and this is the glance that decides.
                  ? "ring-gradient relative scale-[1.03] border-violet/60 bg-white lift-lg"
                  : "glass-light lift",
              )}
            >
              <CardHeader>
                {plan.featured && (
                  <span className="eyebrow mb-2 inline-block w-fit rounded-full bg-violet-soft px-2.5 py-1">
                    Most popular
                  </span>
                )}
                <CardTitle className="t-h3">{plan.name}</CardTitle>
                <div className="mt-2 flex items-baseline gap-1">
                  <span className="text-[clamp(2.4rem,3vw,3.4rem)] font-bold leading-none text-ink">{priceFor(plan.tier)}</span>
                  <span className="text-sm text-ink-muted">{plan.cadence}</span>
                </div>
                <p className="mt-1 text-xs font-semibold uppercase tracking-widest text-ink-faint">
                  {creditsFor(plan.tier)}
                </p>
              </CardHeader>
              <CardContent className="flex-1">
                <ul className="space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2.5 text-[0.98rem] leading-relaxed text-ink-muted">
                      <Check className="mt-0.5 h-4 w-4 shrink-0 text-good" strokeWidth={2} />
                      {feature}
                    </li>
                  ))}
                </ul>
              </CardContent>
              <CardFooter>
                <Button asChild variant={plan.featured ? "solid" : "outline"} className="w-full">
                  <Link to="/register">{plan.cta}</Link>
                </Button>
              </CardFooter>
            </Card>
          </Reveal>
        ))}
      </div>
      </div>
    </section>
  );
}
