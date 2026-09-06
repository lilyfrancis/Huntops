import { Radar, Target, Ghost, Send, MessageSquare, Handshake } from "lucide-react";
import { Reveal } from "@/components/landing/reveal";

const FEATURES = [
  {
    icon: Radar,
    title: "Real job aggregation",
    body: "Six live sources plus curated alert feeds, deduped and refreshed daily. Not a stale scrape from last week.",
  },
  {
    icon: Target,
    title: "AI fit scoring",
    body: "Every opening scored against your CV — skills, experience and location — so the best work rises to the top.",
  },
  {
    icon: Ghost,
    title: "Ghost-job detector",
    body: "Flags listings that aren't a real, fillable seat, and tells you exactly why it thinks so.",
  },
  {
    icon: Send,
    title: "Autopilot Outreach",
    body: "Finds the hiring manager, drafts a pitch in your voice, and sends it from your account. No copy-paste.",
  },
  {
    icon: MessageSquare,
    title: "Mock interviews",
    body: "Practise the real screen for the role you're chasing, with every answer scored and rewritten stronger.",
  },
  {
    icon: Handshake,
    title: "Negotiation coach",
    body: "See where your offer sits against real listings, and get the exact words to counter with.",
  },
];

export function Features() {
  return (
    <section id="features" className="bg-bg-tint py-24">
      <div className="mx-auto max-w-6xl px-5">
        <Reveal className="mx-auto max-w-2xl text-center">
          <span className="eyebrow">The platform</span>
          <h2 className="mt-3 text-3xl sm:text-4xl">Everything the hunt needs, in one place</h2>
        </Reveal>

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={(i % 3) as 0 | 1 | 2}>
              <article className="group h-full rounded-2xl border border-border bg-white p-6 transition-all hover:border-violet/40 lift">
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
