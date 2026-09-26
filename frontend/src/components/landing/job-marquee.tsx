import { Building2, MapPin, Radio } from "lucide-react";

/*
  The feed, moving.

  This replaced a row of scrolling source names, which asked the reader to be
  impressed by logos of job boards they have never heard of. A moving wall of
  actual roles does the same job better: it shows what the product produces,
  at a glance, in the reader's own currencies and cities.

  These are illustrative, and the caption says so. Putting live listings here
  would mean publishing the company names the product charges to unlock, which
  is the one thing the whole locking model exists to prevent.
*/
interface Role {
  title: string;
  company: string;
  location: string;
  salary: string;
  score: number;
  remote?: boolean;
}

const ROW_ONE: Role[] = [
  { title: "Head of Growth", company: "Payments scale-up", location: "Lagos, NG", salary: "₦18M – ₦24M", score: 94, remote: true },
  { title: "Senior Product Manager", company: "Fintech", location: "London, UK", salary: "£85k – £105k", score: 91 },
  { title: "Data Analyst", company: "Logistics", location: "Toronto, CA", salary: "C$92k – C$110k", score: 88, remote: true },
  { title: "Customer Success Lead", company: "B2B SaaS", location: "Dubai, AE", salary: "AED 28k – 34k / mo", score: 86 },
  { title: "Backend Engineer, Go", company: "Marketplace", location: "Remote, EMEA", salary: "$120k – $150k", score: 84, remote: true },
  { title: "Lifecycle Marketing Manager", company: "Neobank", location: "Abuja, NG", salary: "₦11M – ₦15M", score: 82 },
];

const ROW_TWO: Role[] = [
  { title: "Finance Business Partner", company: "Healthtech", location: "Manchester, UK", salary: "£62k – £74k", score: 90 },
  { title: "Solutions Architect", company: "Cloud vendor", location: "Austin, US", salary: "$155k – $180k", score: 89, remote: true },
  { title: "People Operations Manager", company: "Series B startup", location: "Vancouver, CA", salary: "C$105k – C$125k", score: 87 },
  { title: "Growth Marketing Lead", company: "Payments", location: "Nairobi, KE", salary: "$48k – $62k", score: 85, remote: true },
  { title: "Senior QA Engineer", company: "Insurtech", location: "Abu Dhabi, AE", salary: "AED 25k – 31k / mo", score: 83 },
  { title: "Partnerships Manager", company: "Mobility", location: "Leeds, UK", salary: "£55k – £68k", score: 81 },
];

function RoleCard({ role }: { role: Role }) {
  return (
    <article className="glass-light lift w-[19rem] shrink-0 rounded-2xl p-5 transition-transform duration-300 hover:-translate-y-1 sm:w-[21rem]">
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="rounded-md bg-surface-3 px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-ink-faint">
            {role.location.split(", ")[1]}
          </span>
          {role.remote && (
            <span className="flex items-center gap-1 rounded-md bg-cyan-soft px-2 py-0.5 text-[0.65rem] font-semibold uppercase tracking-wide text-cyan-ink">
              <Radio className="h-2.5 w-2.5" /> Remote
            </span>
          )}
        </div>
        <span className="shrink-0 rounded-lg bg-good-soft px-2 py-1 font-mono text-sm font-bold text-good">
          {role.score}
        </span>
      </div>

      <h3 className="mt-3 line-clamp-1 text-[1.05rem] font-semibold text-ink">{role.title}</h3>

      <div className="mt-2 space-y-1 text-sm text-ink-muted">
        <p className="flex items-center gap-1.5">
          <Building2 className="h-3.5 w-3.5 shrink-0" /> {role.company}
        </p>
        <p className="flex items-center gap-1.5">
          <MapPin className="h-3.5 w-3.5 shrink-0" /> {role.location}
        </p>
      </div>

      <p className="mt-3 font-mono text-sm font-semibold text-good">{role.salary}</p>
    </article>
  );
}

function Row({ roles, reverse }: { roles: Role[]; reverse?: boolean }) {
  // Duplicated track + a 50% translate = a seamless loop with no jump at the
  // seam. Both copies are aria-hidden-free on purpose: the cards are read
  // once by a screen reader in source order, which is what they are.
  const track = [...roles, ...roles];
  return (
    <div className="group marquee-mask overflow-hidden">
      <div
        className={`flex w-max gap-5 group-hover:[animation-play-state:paused] ${
          reverse ? "animate-marquee-reverse" : "animate-marquee-slow"
        }`}
      >
        {track.map((role, i) => (
          <RoleCard key={`${role.title}-${i}`} role={role} />
        ))}
      </div>
    </div>
  );
}

const SOURCES = [
  "LinkedIn alerts", "Indeed", "Greenhouse", "Lever", "RemoteOK",
  "We Work Remotely", "Remotive", "Jobicy", "Arbeitnow", "Adzuna",
];

export function JobMarquee() {
  return (
    <section className="relative isolate overflow-hidden bg-bg-tint py-20 lg:py-24">
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div className="absolute -left-40 top-0 h-[26rem] w-[26rem] rounded-full bg-violet-soft blur-[120px]" />
        <div className="absolute -right-32 bottom-0 h-[24rem] w-[24rem] rounded-full bg-cyan-soft blur-[120px]" />
      </div>

      <div className="shell">
        <div className="mx-auto max-w-3xl text-center">
          <span className="eyebrow t-eyebrow-lg">The feed</span>
          <h2 className="t-h2 mt-4">Roles land here every morning</h2>
          <p className="t-lead mx-auto mt-5 max-w-2xl text-ink-muted">
            Scored against your CV, ghost listings flagged, salary shown up front. Yours is
            filtered to your market, your level and the work you actually do.
          </p>
        </div>
      </div>

      <div className="mt-12 space-y-5">
        <Row roles={ROW_ONE} />
        <Row roles={ROW_TWO} reverse />
      </div>

      <div className="shell mt-12">
        <p className="text-center text-xs font-semibold uppercase tracking-widest text-ink-faint">
          Sourced continuously from
        </p>
        <p className="mx-auto mt-3 max-w-4xl text-center text-sm text-ink-muted">
          {SOURCES.join(" · ")}
        </p>
        <p className="mx-auto mt-6 max-w-2xl text-center text-xs text-ink-faint">
          Cards above are examples of the shape of the feed, not live listings.
        </p>
      </div>
    </section>
  );
}
