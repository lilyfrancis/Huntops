import { Reveal } from "@/components/landing/reveal";

const STEPS = [
  {
    n: "01",
    title: "Tell us what you want",
    body: "Pick your role, your market and your seniority when you sign up. That is the whole setup — no inbox to connect, nothing to configure.",
    image: "/brand/feature-interview.webp",
    alt: "A candidate reviewing a role on a video call",
  },
  {
    n: "02",
    title: "We find and score the work",
    body: "HuntOps pulls matching openings from six live sources plus curated alert feeds, then scores every one against your CV — skills, experience and location.",
    image: "/brand/hero-dashboard.webp",
    alt: "The HuntOps dashboard ranking matched roles by score",
  },
  {
    n: "03",
    title: "Autopilot makes the approach",
    body: "Set a score threshold and HuntOps takes it from there: it finds the hiring manager, drafts a pitch in your voice, and sends it — or holds it for your approval.",
    image: "/brand/feature-offer.webp",
    alt: "A candidate celebrating a call from a recruiter",
  },
];

export function HowItWorks() {
  return (
    <section id="how" className="mx-auto max-w-6xl px-5 py-24">
      <Reveal className="mx-auto max-w-2xl text-center">
        <span className="eyebrow">How it works</span>
        <h2 className="mt-3 text-3xl sm:text-4xl">Three steps, then it runs itself</h2>
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
