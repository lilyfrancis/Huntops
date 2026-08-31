import { Link } from "react-router-dom";
import { Check } from "lucide-react";
import { Reveal } from "@/components/landing/reveal";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const PLANS = [
  {
    name: "Free",
    price: "$0",
    cadence: "forever",
    credits: "10 AI credits / mo",
    features: ["Aggregated job feed", "AI fit scoring", "Gmail alert bridge", "Daily digest"],
    cta: "Start free",
    featured: false,
  },
  {
    name: "Pro",
    price: "$29",
    cadence: "/ month",
    credits: "100 AI credits / mo",
    features: [
      "Everything in Free",
      "10x the AI credits",
      "Priority digest placement",
      "Résumé re-scoring on demand",
    ],
    cta: "Go Pro",
    featured: true,
  },
  {
    name: "Elite",
    price: "$79",
    cadence: "/ month",
    credits: "500 AI credits / mo",
    features: [
      "Everything in Pro",
      "Autopilot Outreach unlocked",
      "Apollo recruiter discovery",
      "AI-drafted pitches sent from your Gmail",
    ],
    cta: "Go Elite",
    featured: false,
  },
];

export function Pricing() {
  return (
    <section id="pricing" className="mx-auto max-w-6xl px-6 py-28">
      <Reveal className="mx-auto max-w-2xl text-center">
        <span className="eyebrow">Pricing</span>
        <h2 className="mt-3 text-4xl">Pay for reach, not for looking</h2>
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
                plan.featured && "border-accent/50 shadow-[0_0_0_1px_var(--color-accent)_inset]",
              )}
            >
              <CardHeader>
                {plan.featured && (
                  <span className="eyebrow mb-2 inline-block w-fit rounded-full bg-accent-soft px-2.5 py-1">
                    Most popular
                  </span>
                )}
                <CardTitle className="text-lg">{plan.name}</CardTitle>
                <div className="mt-2 flex items-baseline gap-1">
                  <span className="font-display text-4xl text-ink">{plan.price}</span>
                  <span className="text-sm text-ink-muted">{plan.cadence}</span>
                </div>
                <p className="mt-1 font-mono text-xs uppercase tracking-widest text-ink-faint">
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
