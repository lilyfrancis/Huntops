import { Radar, Target, Ghost, Send, MessageSquare, FileText } from "lucide-react";
import { Reveal } from "@/components/landing/reveal";

const FEATURES = [
  {
    icon: Send,
    title: "We file the application",
    body: "Tap apply and a person at JobQuick AI fills in the form on the job board for you, under an address we set up in your name. You never open the site.",
  },
  {
    icon: FileText,
    title: "A cover letter per job",
    body: "Written against that role's actual requirements, with your CV bullets rewritten to match. Read it, change anything, send it.",
  },
  {
    icon: Target,
    title: "Scored against your CV",
    body: "Every opening rated on skills, experience and location, with the reason in plain words — so you spend your time on the ten worth having.",
  },
  {
    icon: Radar,
    title: "Jobs the boards don't show you",
    body: "Sourced from live alert feeds across Nigeria, the UK, the USA, Canada and the UAE, deduped daily. Not a stale scrape from last week.",
  },
  {
    icon: Ghost,
    title: "Ghost listings flagged",
    body: "Postings that aren't a real, fillable seat get marked before you spend anything on them, with the reason shown.",
  },
  {
    icon: MessageSquare,
    title: "Straight to the hiring manager",
    body: "We find whoever is actually hiring and write to them for you — the thing that works when an application form does not.",
  },
];

export function Features() {
  return (
    <section id="features" className="relative isolate overflow-hidden bg-bg-tint py-28 lg:py-36">
      {/* A ground for the glass to sit on. Flat white boxes on a flat white
          page are the reason this section read as a spreadsheet. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -left-40 top-10 h-[28rem] w-[28rem] rounded-full bg-violet-soft blur-[110px]" />
        <div className="absolute -right-32 bottom-0 h-[24rem] w-[24rem] rounded-full bg-cyan-soft blur-[110px]" />
      </div>
      <div className="shell">
        <Reveal className="mx-auto max-w-3xl text-center">
          <span className="eyebrow t-eyebrow-lg">The platform</span>
          <h2 className="t-h2 mt-4">The part everyone hates, done for you</h2>
          <p className="t-lead mx-auto mt-5 max-w-2xl text-ink-muted">
            Six jobs you are doing by hand tonight. Every one of them runs without you
            from the moment you finish setup.
          </p>
        </Reveal>

        <div className="mt-16 grid gap-6 sm:grid-cols-2 lg:grid-cols-3 lg:gap-7">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={(i % 3) as 0 | 1 | 2}>
              <article className="glass-light group h-full rounded-2xl p-7 transition-all duration-300 hover:-translate-y-1.5 hover:border-violet/40 lift hover:lift-lg lg:p-9">
                <span className="inline-flex h-13 w-13 items-center justify-center rounded-xl bg-violet-soft text-violet transition-colors group-hover:brand-gradient group-hover:text-white">
                  <f.icon className="h-6 w-6" strokeWidth={2} />
                </span>
                <h3 className="t-h3 mt-5">{f.title}</h3>
                <p className="t-body mt-3 text-ink-muted">{f.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
