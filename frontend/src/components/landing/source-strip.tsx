const SOURCES = [
  "LinkedIn alerts",
  "Indeed",
  "Greenhouse",
  "Lever",
  "RemoteOK",
  "We Work Remotely",
  "Remotive",
  "Jobicy",
  "Arbeitnow",
  "Adzuna",
];

export function SourceStrip() {
  const track = [...SOURCES, ...SOURCES];
  return (
    <section className="border-y border-border bg-bg-tint py-6">
      <p className="mb-4 text-center text-xs font-semibold uppercase tracking-widest text-ink-faint">
        Sourced continuously from
      </p>
      {/* Duplicated track + 50% translate = a seamless loop with no jump. */}
      <div className="group overflow-hidden [mask-image:linear-gradient(90deg,transparent,black_12%,black_88%,transparent)]">
        <div className="flex w-max animate-marquee items-center gap-12 group-hover:[animation-play-state:paused]">
          {track.map((s, i) => (
            <span
              key={`${s}-${i}`}
              className="whitespace-nowrap text-base font-semibold text-ink-faint"
            >
              {s}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
