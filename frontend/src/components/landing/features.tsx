import { Radar, Target, Ghost, Send, MessageSquare, FileText } from "lucide-react";
import { Reveal } from "@/components/landing/reveal";

const FEATURES = [
  {
    icon: Send,
    title: "We file the application",
    body: "Tap apply and a person at HuntOps fills in the form on the job board for you, under an address we set up in your name. You never open the site.",
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
    <section id="features" className="relative isolate overflow-hidden bg-bg-tint py-28">
      {/* A ground for the glass to sit on. Flat white boxes on a flat white
          page are the reason this section read as a spreadsheet. */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -left-40 top-10 h-[28rem] w-[28rem] rounded-full bg-violet-soft blur-[110px]" />
        <div className="absolute -right-32 bottom-0 h-[24rem] w-[24rem] rounded-full bg-cyan-soft blur-[110px]" />
      </div>
      <div className="mx-auto max-w-7xl px-6">
        <Reveal className="mx-auto max-w-2xl text-center">
          <span className="eyebrow">The platform</span>
          <h2 className="mt-3 text-3xl sm:text-4xl">The part everyone hates, done for you</h2>
        </Reveal>

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={(i % 3) as 0 | 1 | 2}>
              <article className="glass-light group h-full rounded-2xl p-6 transition-all duration-300 hover:-translate-y-1 hover:border-violet/40 lift hover:lift-lg">
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl bg-violet-soft text-violet transition-colors group-hover:brand-gradient group-hover:text-white">
                  <f.icon className="h-5 w-5" strokeWidth={2} />
                </span>
                <h3 className="mt-4 text-lg">{f.title}</h3>
                <p className="mt-2 text-[0.95rem] leading-relaxed text-ink-muted">{f.body}</p>
              </article>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
