import type { ReactNode } from "react";
import { Link } from "react-router-dom";

export function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-screen lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden bg-surface p-10 lg:flex">
        <div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            backgroundImage:
              "repeating-radial-gradient(circle at 50% 45%, transparent 0 60px, rgba(50,66,85,0.4) 61px 62px, transparent 63px 140px)",
          }}
        />
        <Link to="/" className="relative font-mono text-sm font-semibold tracking-wide text-ink">
          HUNTOPS
        </Link>
        <div className="relative max-w-sm">
          <p className="eyebrow mb-3">The job search copilot</p>
          <h1 className="text-3xl leading-tight text-ink">
            Finds real openings.
            <br />
            Scores your fit.
            <br />
            Emails the recruiter.
          </h1>
        </div>
        <p className="relative font-mono text-xs text-ink-faint">© 2026 HuntOps</p>
      </div>

      <div className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-sm">{children}</div>
      </div>
    </div>
  );
}
