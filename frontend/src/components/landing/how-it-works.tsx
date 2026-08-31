import { Reveal } from "@/components/landing/reveal";

const STEPS = [
  {
    step: "01",
    title: "Upload your résumé",
    body: "HuntOps parses it once and uses it to score every job that comes in, forever.",
  },
  {
    step: "02",
    title: "Every new job gets scored",
    body: "Six sources feed the pipeline daily; each listing is fit-scored against your résumé and location.",
  },
  {
    step: "03",
    title: "Connect Gmail (optional)",
    body: "HuntOps labels and reads the job-alert emails you already get, folding them straight into your feed.",
  },
  {
    step: "04",
    title: "Autopilot reaches out",
    body: "On Elite, HuntOps finds the recruiter, drafts a pitch, and sends it from your Gmail — you approve the credits, not the copy.",
  },
  {
    step: "05",
    title: "Get your daily digest",
    body: "One email each morning with the matches worth your time. Everything else stays out of your inbox.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="border-y border-border bg-surface/40 py-28">
      <div className="mx-auto max-w-3xl px-6">
        <Reveal className="text-center">
          <span className="eyebrow">How it works</span>
          <h2 className="mt-3 text-4xl">From résumé to reach-out in five steps</h2>
        </Reveal>

        <ol className="mt-16 space-y-10 border-l border-border pl-8">
          {STEPS.map((item, i) => (
            <Reveal as="li" key={item.step} delay={(i % 5) as 0 | 1 | 2 | 3 | 4} className="relative">
              <span className="absolute -left-[2.6rem] flex h-8 w-8 items-center justify-center rounded-full border border-border-strong bg-surface font-mono text-[11px] text-accent">
                {item.step}
              </span>
              <h3 className="text-xl">{item.title}</h3>
              <p className="mt-2 text-sm text-ink-muted">{item.body}</p>
            </Reveal>
          ))}
        </ol>
      </div>
    </section>
  );
}
