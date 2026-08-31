import { Link } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Counter } from "@/components/landing/counter";
import { Reveal } from "@/components/landing/reveal";

const STATS = [
  { to: 6, suffix: "", label: "job sources aggregated" },
  { to: 30, suffix: "s", label: "avg. time to first score" },
  { to: 500, suffix: "", label: "AI credits on Elite" },
];

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden pt-40 pb-28">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute left-1/2 top-[-10%] h-[560px] w-[560px] -translate-x-1/2 animate-radar-sweep rounded-full border border-accent/10" />
        <div className="absolute left-1/2 top-[-10%] h-[380px] w-[380px] -translate-x-1/2 animate-radar-sweep-slow rounded-full border border-cyan/10" />
        <div className="absolute inset-x-0 top-0 h-[600px] bg-[radial-gradient(ellipse_at_top,_var(--color-accent-soft),_transparent_60%)]" />
      </div>

      <div className="mx-auto max-w-4xl px-6 text-center">
        <Reveal>
          <span className="eyebrow inline-flex items-center gap-2 rounded-full border border-border-strong bg-surface px-3 py-1">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-good" />
            Live job intelligence, running now
          </span>
        </Reveal>

        <Reveal delay={1}>
          <h1 className="mt-6 text-5xl leading-[1.05] sm:text-6xl">
            Stop refreshing job boards.
            <br />
            <span className="text-accent">Let HuntOps hunt.</span>
          </h1>
        </Reveal>

        <Reveal delay={2}>
          <p className="mx-auto mt-6 max-w-2xl text-lg text-ink-muted">
            HuntOps pulls jobs from six live sources and your own inbox, scores every one
            against your résumé, and — on Elite — reaches out to the recruiter for you.
            One dashboard, zero tab-hoarding.
          </p>
        </Reveal>

        <Reveal delay={3}>
          <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link to="/register">Get started free</Link>
            </Button>
            <Button asChild variant="outline" size="lg">
              <a href="#how-it-works">See how it works</a>
            </Button>
          </div>
        </Reveal>

        <Reveal delay={4}>
          <dl className="mx-auto mt-20 grid max-w-2xl grid-cols-3 gap-6 border-t border-border pt-10">
            {STATS.map((stat) => (
              <div key={stat.label}>
                <dt className="sr-only">{stat.label}</dt>
                <dd className="font-display text-4xl text-ink">
                  <Counter to={stat.to} suffix={stat.suffix} />
                </dd>
                <p className="mt-1 font-mono text-[11px] uppercase tracking-widest text-ink-faint">
                  {stat.label}
                </p>
              </div>
            ))}
          </dl>
        </Reveal>
      </div>
    </section>
  );
}
