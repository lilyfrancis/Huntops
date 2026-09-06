import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/landing/reveal";
import { Counter } from "@/components/landing/counter";

const PROOF = [
  { to: 6, suffix: "", label: "live job sources" },
  { to: 60, suffix: "s", label: "to your first matches" },
  { to: 0, suffix: "", label: "job boards to refresh", literal: "0" },
];

export function Hero() {
  return (
    <section id="top" className="relative overflow-hidden pt-28 pb-16 sm:pt-32">
      {/* Ambient brand wash. Decorative only — never carries meaning. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -top-40 left-1/2 h-[520px] w-[820px] -translate-x-1/2 rounded-full bg-violet-soft blur-3xl" />
        <div className="absolute right-[-10%] top-40 h-[320px] w-[320px] rounded-full bg-cyan-soft blur-3xl" />
      </div>

      <div className="mx-auto grid max-w-6xl items-center gap-12 px-5 lg:grid-cols-[1.05fr_1fr]">
        <div>
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border border-border bg-white px-3 py-1.5 text-xs font-semibold text-ink-muted lift">
              <span className="relative flex h-2 w-2">
                <span className="animate-pulse-ring absolute inline-flex h-full w-full rounded-full bg-violet" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-violet" />
              </span>
              Sourcing jobs right now
            </span>
          </Reveal>

          <Reveal delay={1}>
            <h1 className="mt-5 text-4xl leading-[1.08] sm:text-5xl lg:text-6xl">
              Stop refreshing job boards.
              <br />
              <span className="brand-gradient-text">Let HuntOps hunt.</span>
            </h1>
          </Reveal>

          <Reveal delay={2}>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-muted">
              Tell us the role and the market you want. HuntOps pulls matching openings
              from six live sources, scores every one against your CV, and reaches out to
              the hiring manager for you.
            </p>
          </Reveal>

          <Reveal delay={3}>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg">
                <Link to="/register">
                  Start free <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg">
                <a href="#how">See how it works</a>
              </Button>
            </div>
          </Reveal>

          <Reveal delay={4}>
            <ul className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-muted">
              {["No credit card", "No inbox to connect", "Free forever tier"].map((t) => (
                <li key={t} className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 text-good" strokeWidth={2} />
                  {t}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>

        <Reveal delay={2} className="relative">
          <div className="animate-float-slow overflow-hidden rounded-2xl border border-border bg-white lift-lg">
            <img
              src="/brand/hero-dashboard.webp"
              alt="The HuntOps dashboard showing scored job matches"
              width={1400}
              height={1400}
              className="w-full"
              fetchPriority="high"
            />
          </div>

          {/* Floating proof chip — the product's promise, stated as a number. */}
          <div className="absolute -bottom-5 -left-4 hidden rounded-xl border border-border bg-white px-4 py-3 lift-lg sm:block">
            <p className="text-2xl font-bold text-ink">
              <Counter to={92} suffix="%" />
            </p>
            <p className="text-xs text-ink-muted">top match score today</p>
          </div>
        </Reveal>
      </div>

      <Reveal delay={4}>
        <dl className="mx-auto mt-20 grid max-w-3xl grid-cols-3 gap-6 border-t border-border px-5 pt-10 text-center">
          {PROOF.map((s) => (
            <div key={s.label}>
              <dt className="sr-only">{s.label}</dt>
              <dd className="text-3xl font-bold text-ink sm:text-4xl">
                {s.literal ?? <Counter to={s.to} suffix={s.suffix} />}
              </dd>
              <p className="mt-1 text-sm text-ink-muted">{s.label}</p>
            </div>
          ))}
        </dl>
      </Reveal>
    </section>
  );
}
