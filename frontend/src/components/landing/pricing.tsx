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
    credits: "10 AI credits / mo",
    features: ["Job feed for your market", "AI fit scoring", "Ghost-listing detection", "Daily digest"],
    cta: "Start free",
    featured: false,
  },
  {
    name: "Pro",
    tier: "pro",
    cadence: "/ month",
    credits: "100 AI credits / mo",
    features: [
      "Everything in Free",
      "Mock interview simulator",
      "Negotiation coach",
      "10x the AI credits",
      "Priority digest placement",
    ],
    cta: "Go Pro",
    featured: true,
  },
  {
    name: "Elite",
    tier: "elite",
    cadence: "/ month",
    credits: "500 AI credits / mo",
    features: [
      "Everything in Pro",
      "Autopilot — applies and reaches out for you",
      "Apollo hiring-manager discovery",
      "AI-drafted pitches, sent from your address or ours",
    ],
    cta: "Go Elite",
    featured: false,
  },
];

export function Pricing() {
  const plans = usePrices();

  const priceFor = (tier: string): string => {
    if (tier === "free") return "Free";
    const plan = plans?.find((p) => p.tier === tier);
    // Never guess at a number someone will be charged.
    return plan ? formatPrice(plan.price, plan.currency) : "—";
  };

  return (
    <section id="pricing" className="mx-auto max-w-6xl px-5 py-24">
      <Reveal className="mx-auto max-w-2xl text-center">
        <span className="eyebrow">Pricing</span>
        <h2 className="mt-3 text-3xl sm:text-4xl">Pay for reach, not for looking</h2>
        <p className="mt-4 text-ink-muted">
          Every action that costs AI — a fit score, an extracted alert, a drafted outreach —
          spends credits. Upgrade when you need more reach, not because a paywall says so.
        </p>
      </Reveal>

      <div className="mt-16 grid gap-6 lg:grid-cols-3">
        {PLANS.map((plan, i) => (
          <Reveal key={plan.name} delay={i as 0 | 1 | 2}>
            <Card
              className={cn(
                "flex h-full flex-col",
                plan.featured ? "border-violet/60 lift-lg" : "lift",
              )}
            >
              <CardHeader>
                {plan.featured && (
                  <span className="eyebrow mb-2 inline-block w-fit rounded-full bg-violet-soft px-2.5 py-1">
                    Most popular
                  </span>
                )}
                <CardTitle className="text-lg">{plan.name}</CardTitle>
                <div className="mt-2 flex items-baseline gap-1">
                  <span className="text-4xl font-bold text-ink">{priceFor(plan.tier)}</span>
                  <span className="text-sm text-ink-muted">{plan.cadence}</span>
                </div>
                <p className="mt-1 text-xs font-semibold uppercase tracking-widest text-ink-faint">
                  {plan.credits}
                </p>
              </CardHeader>
              <CardContent className="flex-1">
                <ul className="space-y-3">
                  {plan.features.map((feature) => (
                    <li key={feature} className="flex items-start gap-2 text-sm text-ink-muted">
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
    </section>
  );
}
