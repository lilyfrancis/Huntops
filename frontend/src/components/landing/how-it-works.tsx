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
    image: "/brand/hero-dashboard.webp",
    alt: "The HuntOps dashboard ranking matched roles by score",
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
    <section id="how" className="mx-auto max-w-6xl px-5 py-24">
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
              <div className="overflow-hidden rounded-2xl border border-border bg-white lift-lg">
                <img
                  src={step.image}
                  alt={step.alt}
                  loading="lazy"
                  className="aspect-[4/3] w-full object-cover"
                />
              </div>
            </div>
          </Reveal>
        ))}
      </div>
    </section>
  );
}
