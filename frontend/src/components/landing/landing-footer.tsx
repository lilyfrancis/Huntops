import { Link } from "react-router-dom";
import { Logo } from "@/components/brand/logo";

export function LandingFooter() {
  return (
    <footer className="border-t border-border bg-bg-tint">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 px-5 py-10 sm:flex-row">
        <div className="flex flex-col items-center gap-2 sm:items-start">
          <Logo height={26} />
          <p className="text-sm text-ink-muted">Built for people who'd rather be hunted for.</p>
        </div>
        <div className="flex items-center gap-6 text-sm font-medium text-ink-muted">
          <a href="#how" className="transition-colors hover:text-ink">How it works</a>
          <a href="#pricing" className="transition-colors hover:text-ink">Pricing</a>
          <Link to="/login" className="transition-colors hover:text-ink">Sign in</Link>
        </div>
      </div>
      <div className="border-t border-border py-4">
        <p className="text-center text-xs text-ink-faint">
          © {new Date().getFullYear()} HuntOps. All rights reserved.
        </p>
      </div>
    </footer>
  );
}
