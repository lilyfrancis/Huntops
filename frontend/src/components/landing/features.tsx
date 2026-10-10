import { Radar, Target, Ghost, Send, MessageSquare, FileText } from "lucide-react";
import { Reveal } from "@/components/landing/reveal";

const FEATURES = [
  {
    icon: Send,
    title: "Your Job Applications, Automated",
    body: "Stop wasting hours filling out job applications. JobQuick AI finds matching opportunities and automatically submits applications with a CV tailored to each role, while you focus on what matters.",
  },
  {
    icon: FileText,
    title: "Every Job Deserves a Winning CV",
    body: "No more generic applications. HuntOps tailors your CV and writes a compelling cover letter for each job, highlighting the skills and experience employers are looking for.",
  },
  {
    icon: Target,
    title: "Stop Applying Blindly",
    body: "Know your chances before you apply. HuntOps scores every opportunity against your skills, experience, and preferred location, helping you focus on jobs that truly fit your profile.",
  },
  {
    icon: Radar,
    title: "Jobs the boards don't show you",
    body: "Discover fresh, relevant opportunities across Nigeria, the UK, USA, Canada, and UAE without spending hours searching multiple job boards.",
  },
  {
    icon: Ghost,
    title: "Ghost listings flagged",
    body: "Postings that aren't a real, fillable seat get marked before you spend anything on them, with the reason shown.",
  },
  {
    icon: MessageSquare,
    title: "Straight to the hiring manager",
    body: "Go beyond the Apply button. JobQuick AI finds relevant recruiters and sends personalised pitches highlighting why you're the right candidate for the job.",
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
  <span className="eyebrow t-eyebrow-lg">
    YOUR AI JOB SEARCH AGENT
  </span>

  <h2 className="t-h2 mt-4">
    Stop Chasing Jobs. Let Opportunities Find You.
  </h2>

  <p className="t-lead mx-auto mt-5 max-w-2xl text-ink-muted">
    Imagine waking up to job applications already submitted.
    JobQuick AI finds matching roles, tailors your CV, applies on your
    behalf, and connects you directly with recruiters.
    You focus on getting hired.
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
