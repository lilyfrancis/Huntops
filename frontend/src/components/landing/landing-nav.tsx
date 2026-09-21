import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Menu, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Logo } from "@/components/brand/logo";

const LINKS = [
  { href: "#how", label: "How it works" },
  { href: "#features", label: "Features" },
  { href: "#pricing", label: "Pricing" },
];

export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 16);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-all duration-300",
        scrolled ? "border-b border-border bg-white/85 backdrop-blur-lg" : "bg-transparent",
      )}
    >
      <div className="shell flex items-center justify-between py-4">
        <a href="#top" aria-label="HuntOps home">
          <Logo variant={scrolled ? "navy" : "white"} height={30} />
        </a>

        <nav
          className={cn(
            "hidden items-center gap-9 text-[0.95rem] font-medium transition-colors md:flex",
            scrolled ? "text-ink-muted" : "text-white/70",
          )}
        >
          {LINKS.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className={cn("transition-colors", scrolled ? "hover:text-ink" : "hover:text-white")}
            >
              {l.label}
            </a>
          ))}
        </nav>

        <div className="hidden items-center gap-2 md:flex">
          <Button
            asChild
            variant="ghost"
            size="sm"
            className={cn(!scrolled && "text-white/80 hover:bg-white/10 hover:text-white")}
          >
            <Link to="/login">Sign in</Link>
          </Button>
          <Button asChild size="sm">
            <Link to="/register">Start free</Link>
          </Button>
        </div>

        <button
          className={cn("rounded-lg p-2 md:hidden", scrolled ? "text-ink" : "text-white")}
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
        >
          {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
        </button>
      </div>

      {open && (
        <div className="border-t border-border bg-white px-5 py-4 md:hidden">
          <nav className="flex flex-col gap-1">
            {LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setOpen(false)}
                className="rounded-lg px-2 py-2.5 text-sm font-medium text-ink-muted hover:bg-surface-2 hover:text-ink"
              >
                {l.label}
              </a>
            ))}
          </nav>
          <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
            <Button asChild variant="outline" className="w-full">
              <Link to="/login">Sign in</Link>
            </Button>
            <Button asChild className="w-full">
              <Link to="/register">Start free</Link>
            </Button>
          </div>
        </div>
      )}
    </header>
  );
}
