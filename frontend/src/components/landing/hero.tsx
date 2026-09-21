import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2, FileText, MessageSquare, Mic, Send, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/landing/reveal";
import { Counter } from "@/components/landing/counter";
import { useParallax } from "@/hooks/use-parallax";

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
  // The screenshot drifts against the page as you scroll. Small on purpose:
  // enough to feel like depth, not enough to notice as an effect.
  const shot = useParallax<HTMLDivElement>(-0.06);

  return (
    <section
      id="top"
      className="grain relative isolate overflow-hidden bg-navy pt-28 pb-28 sm:pt-32 lg:pb-36"
    >
      {/* Aurora. Frosted panels need something with structure behind them,
          and on a white page there is nothing for glass to frost. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute inset-0 grid-fade" />
        <div className="animate-drift-a absolute -top-1/3 left-1/2 h-[46rem] w-[46rem] -translate-x-1/2 rounded-full bg-violet/35 blur-[120px]" />
        <div className="animate-drift-b absolute -right-40 top-20 h-[34rem] w-[34rem] rounded-full bg-cyan/20 blur-[130px]" />
        <div className="absolute -bottom-40 left-0 h-[30rem] w-[30rem] rounded-full bg-violet-dark/25 blur-[140px]" />
        {/* Hands the section back to the page below instead of ending on a
            hard edge. */}
        <div className="absolute inset-x-0 bottom-0 h-24 bg-gradient-to-b from-transparent to-bg" />
      </div>

      <div className="shell grid items-center gap-14 lg:grid-cols-[1.02fr_1fr] lg:gap-16">
        <div>
          <Reveal>
            <span className="glass inline-flex items-center gap-2 rounded-full px-3.5 py-1.5 text-xs font-semibold text-white/85">
              <span className="relative flex h-2 w-2">
                <span className="animate-pulse-ring absolute inline-flex h-full w-full rounded-full bg-cyan" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-cyan" />
              </span>
              Filing applications right now
            </span>
          </Reveal>

          <Reveal delay={1}>
            <h1 className="t-display mt-6 font-semibold text-white">
              You pick the jobs.
              <br />
              <span className="text-gradient-bright">We do the applying.</span>
            </h1>
          </Reveal>

          <Reveal delay={2}>
            <p className="t-lead mt-7 max-w-2xl text-white/70">
              Every role scored against your CV. Your CV rewritten for the ones you want.
              The application <strong className="font-semibold text-white">filed for you</strong>,
              and the hiring manager messaged directly — while you watch it happen from one
              dashboard.
            </p>
          </Reveal>

          <Reveal delay={3}>
            <div className="mt-9 flex flex-col gap-3 sm:flex-row">
              <Button asChild size="lg" className="group relative overflow-hidden">
                <Link to="/register">
                  Apply to your first job free
                  <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                  {/* A light passing across the primary action. One moving
                      thing on the page, on the thing we want clicked. */}
                  <span
                    aria-hidden
                    className="animate-sheen pointer-events-none absolute inset-y-0 w-1/3 bg-gradient-to-r from-transparent via-white/25 to-transparent"
                  />
                </Link>
              </Button>
              <Button
                asChild
                size="lg"
                variant="ghost"
                className="glass text-white hover:bg-white/15 hover:text-white"
              >
                <a href="#how">See how it works</a>
              </Button>
            </div>
          </Reveal>

          <Reveal delay={4}>
            <ul className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm text-white/55">
              {["Your first application is free", "No card to start", "Cancel anytime"].map((t) => (
                <li key={t} className="flex items-center gap-1.5">
                  <CheckCircle2 className="h-4 w-4 text-cyan" strokeWidth={2} />
                  {t}
                </li>
              ))}
            </ul>
          </Reveal>
        </div>

        <Reveal delay={2} className="relative">
          <div ref={shot} className="will-change-transform">
            <div className="ring-gradient glass-strong animate-float-slow overflow-hidden rounded-2xl p-1.5 shadow-[0_40px_80px_-30px_rgb(0_0_0/0.65)]">
              {/* The actual product, not a stock desk. It carries the whole
                  proposition without a caption: fit scores, salaries in the
                  reader's own currency, "Apply for me", one already filed,
                  and a locked row showing what unlocking is for. */}
              <img
                src="/brand/hero-product.webp"
                alt="The HuntOps job feed: roles scored against your CV, salaries shown, one already applied for"
                width={1400}
                height={837}
                className="w-full rounded-xl"
                fetchPriority="high"
              />
            </div>

            <div className="glass-strong ring-gradient absolute -bottom-6 -left-4 hidden rounded-xl px-4 py-3 sm:block">
              <p className="text-2xl font-bold text-white">
                <Counter to={92} suffix="%" />
              </p>
              <p className="text-xs text-white/60">fit — filed for you this morning</p>
            </div>
          </div>
        </Reveal>
      </div>

      <Reveal delay={4}>
        <ol className="shell mt-24 grid gap-y-8 border-t border-white/10 pt-12 sm:grid-cols-2 lg:grid-cols-5 lg:gap-x-10">
          {ARC.map((step, i) => (
            <li key={step.label} className="group flex gap-3 lg:block">
              <span className="glass flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-cyan transition-colors group-hover:bg-white/15 lg:mb-4">
                <step.icon className="h-4.5 w-4.5" strokeWidth={2} />
              </span>
              <div>
                <p className="text-[1.02rem] font-semibold text-white">
                  <span className="font-mono text-xs text-white/40">{i + 1}. </span>
                  {step.label}
                </p>
                <p className="mt-1.5 text-[0.95rem] leading-relaxed text-white/55">{step.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </Reveal>
    </section>
  );
}
