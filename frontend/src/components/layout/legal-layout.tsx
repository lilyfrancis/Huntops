import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Logo } from "@/components/brand/logo";

/**
 * The frame for the privacy policy and terms.
 *
 * These are the two pages Google, Paystack and app stores all fetch before
 * they will trust the product, so they have to load fast, render without
 * JavaScript-heavy chrome, and be reachable without an account.
 */
export function LegalLayout({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <div className="min-h-screen bg-bg">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-5 py-4">
          <Link to="/" aria-label="HuntOps home">
            <Logo height={28} />
          </Link>
          <Link to="/" className="text-sm font-medium text-ink-muted transition-colors hover:text-ink">
            Back to site
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-3xl px-5 py-12">
        <h1 className="text-3xl text-ink">{title}</h1>
        <p className="mt-2 font-mono text-xs uppercase tracking-widest text-ink-faint">
          Last updated {updated}
        </p>

        <div className="legal mt-10">{children}</div>
      </main>

      <footer className="border-t border-border py-6">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center justify-between gap-3 px-5 text-sm text-ink-muted">
          <span>© {new Date().getFullYear()} HuntOps</span>
          <div className="flex gap-5">
            <Link to="/privacy" className="transition-colors hover:text-ink">Privacy</Link>
            <Link to="/terms" className="transition-colors hover:text-ink">Terms</Link>
            <a href="mailto:support@huntops.site" className="transition-colors hover:text-ink">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  );
}
