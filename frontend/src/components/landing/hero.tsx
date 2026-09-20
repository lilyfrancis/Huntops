import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, FileText, MessageSquare, Mic, Send, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/landing/reveal";
import { Counter } from "@/components/landing/counter";

// The whole product, in the order it happens. Five short beats rather than
// a features section, because the reason to believe the headline is seeing
// that there is a mechanism behind it — and mock interviews and negotiation
// have nowhere else to appear this high up without crowding it.
const ARC = [
  { icon: Target, label: "Matched", body: "Every role scored against your CV, ghosts flagged." },
  { icon: FileText, label: "CV tailored", body: "Rewritten for the job, with a cover letter to match." },
  { icon: Send, label: "Applied for you", body: "We fill in the form on the board. You never open it." },
  { icon: MessageSquare, label: "Manager messaged", body: "We find whoever is hiring and write to them." },
  { icon: Mic, label: "Interview ready", body: "Mock screens and offer coaching when it lands." },
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
              Filing applications right now
            </span>
          </Reveal>

          <Reveal delay={1}>
            {/* The headline is the whole proposition, because it is the one
                thing no other job tool does: the applying itself. Everything
                else here — sourcing, scoring, ghost detection — is table
                stakes that a reader will assume anyway. */}
            {/* Sized to land in two lines in this column. At 4rem it broke
                into four, which turns a claim into a paragraph. */}
            <h1 className="mt-5 text-[2.6rem] leading-[1.05] tracking-tight sm:text-5xl lg:text-[3.4rem]">
              You pick the jobs.
              <br />
              <span className="brand-gradient-text">We do the applying.</span>
            </h1>
          </Reveal>

          <Reveal delay={2}>
            <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-muted sm:text-xl">
              Every role scored against your CV. Your CV rewritten for the ones you
              want. The application <strong className="font-semibold text-ink">filed
              for you</strong>, and the hiring manager messaged directly — while you
              watch it happen from one dashboard.
            </p>
          </Reveal>

          <Reveal delay={3}>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg">
                <Link to="/register">
                  Apply to your first job free <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
              <Button asChild variant="outline" size="lg">
                <a href="#how">See how it works</a>
              </Button>
            </div>
          </Reveal>

          <Reveal delay={4}>
            <ul className="mt-6 flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-muted">
              {["Your first application is free", "No card to start", "Cancel anytime"].map((t) => (
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
            {/* The actual product, not a stock desk. It carries the whole
                proposition without a caption: fit scores, salaries in the
                reader's own currency, "Apply for me", one already filed,
                and a locked row showing what unlocking is for. */}
            <img
              src="/brand/hero-product.webp"
              alt="The HuntOps job feed: roles scored against your CV, salaries shown, one already applied for"
              width={1400}
              height={837}
              className="w-full"
              fetchPriority="high"
            />
          </div>

          {/* Floating proof chip — the product's promise, stated as a number. */}
          <div className="absolute -bottom-6 -left-5 hidden rounded-xl border border-border bg-white px-4 py-3 lift-lg sm:block">
            <p className="text-2xl font-bold text-ink">
              <Counter to={92} suffix="%" />
            </p>
            <p className="text-xs text-ink-muted">fit — filed for you this morning</p>
          </div>
        </Reveal>
      </div>

      <Reveal delay={4}>
        <ol className="mx-auto mt-20 grid max-w-5xl gap-y-8 border-t border-border px-5 pt-10 sm:grid-cols-2 lg:grid-cols-5 lg:gap-x-4">
          {ARC.map((step, i) => (
            <li key={step.label} className="flex gap-3 lg:block">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-soft text-violet lg:mb-3">
                <step.icon className="h-4.5 w-4.5" strokeWidth={2} />
              </span>
              <div>
                <p className="text-sm font-semibold text-ink">
                  <span className="font-mono text-xs text-ink-faint">{i + 1}. </span>
                  {step.label}
                </p>
                <p className="mt-0.5 text-sm text-ink-muted">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </Reveal>
    </section>
  );
}
