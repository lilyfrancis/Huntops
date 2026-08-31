const SOURCES = [
  "LinkedIn alerts",
  "Indeed",
  "Greenhouse",
  "Lever",
  "RemoteOK",
  "Direct postings",
  "Your Gmail inbox",
];

export function SourceStrip() {
  const track = [...SOURCES, ...SOURCES];
  return (
    <div className="border-y border-border bg-surface/60 py-4">
      <div className="group overflow-hidden">
        <div className="flex w-max animate-marquee items-center gap-10 group-hover:[animation-play-state:paused]">
          {track.map((source, i) => (
            <span
              key={`${source}-${i}`}
              className="whitespace-nowrap font-mono text-xs uppercase tracking-widest text-ink-faint"
            >
              {source}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
