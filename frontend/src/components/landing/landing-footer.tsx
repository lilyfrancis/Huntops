import { Link } from "react-router-dom";

export function LandingFooter() {
  return (
    <footer className="border-t border-border py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 sm:flex-row">
        <div className="flex items-center gap-2 font-display text-sm tracking-wide text-ink-muted">
          HUNTOPS
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-accent" />
        </div>
        <p className="font-mono text-[11px] uppercase tracking-widest text-ink-faint">
          Built for people who'd rather be hunted for.
        </p>
        <div className="flex items-center gap-5 font-mono text-xs uppercase tracking-widest text-ink-muted">
          <Link to="/login" className="transition-colors hover:text-ink">
            Sign in
          </Link>
          <Link to="/register" className="transition-colors hover:text-ink">
            Register
          </Link>
        </div>
      </div>
    </footer>
  );
}
