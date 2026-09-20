import { Reveal } from "@/components/landing/reveal";

const STEPS = [
  {
    n: "01",
    title: "Tell us what you want",
    body: "Your role, your market, your seniority, and upload your CV. Two minutes, and that is the whole setup.",
    image: "/brand/feature-interview.webp",
    alt: "A candidate reviewing a role on a video call",
  },
  {
    n: "02",
    title: "Wake up to scored matches",
    body: "Every morning, the openings worth your time — rated against your CV, ghost listings already flagged, salary shown up front.",
    image: "/brand/hero-product.webp",
    alt: "The HuntOps dashboard ranking matched roles by score",
    // A screenshot, not a photograph: cropping it to the panel's shape cuts
    // words off both edges, so this one is shown whole.
    contain: true,
  },
  {
    n: "03",
    title: "Tap apply. We file it.",
    body: "We write the cover letter, fill in the form on the job board, and send it under your name. You watch the status change from queued to filed — and never open a job site.",
    image: "/brand/feature-offer.webp",
    alt: "A candidate celebrating a call from a recruiter",
  },
];

export function HowItWorks() {
  return (
    <section id="how" className="relative isolate mx-auto max-w-7xl px-6 py-28">
      {/* A thread down the middle, so three steps read as one sequence
          rather than three unrelated cards. */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-64 hidden h-[calc(100%-20rem)] w-px -translate-x-1/2 bg-gradient-to-b from-violet/30 via-cyan/20 to-transparent lg:block"
      />
      <Reveal className="mx-auto max-w-2xl text-center">
        <span className="eyebrow">How it works</span>
        <h2 className="mt-3 text-3xl sm:text-4xl">Two minutes to set up. Then you stop applying.</h2>
        <p className="mt-4 text-lg text-ink-muted">
          Set it up once. HuntOps works every day whether you open it or not.
        </p>
      </Reveal>

      <div className="mt-16 space-y-20">
        {STEPS.map((step, i) => (
          <Reveal key={step.n}>
            <div
              className={`grid items-center gap-10 lg:grid-cols-2 ${
                i % 2 === 1 ? "lg:[&>*:first-child]:order-2" : ""
              }`}
            >
              <div>
                <span className="inline-flex h-11 w-11 items-center justify-center rounded-xl brand-gradient text-base font-bold text-white">
                  {step.n}
                </span>
                <h3 className="mt-5 text-2xl">{step.title}</h3>
                <p className="mt-3 text-lg leading-relaxed text-ink-muted">{step.body}</p>
              </div>
              <div
                className={`ring-gradient overflow-hidden rounded-2xl border border-border transition-transform duration-500 hover:scale-[1.015] lift-lg ${
                  step.contain ? "bg-surface-2 p-3" : "bg-white"
                }`}
              >
                <img
                  src={step.image}
                  alt={step.alt}
                  loading="lazy"
                  className={`aspect-[4/3] w-full ${
                    step.contain ? "rounded-xl object-contain" : "object-cover"
                  }`}
                />
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
