import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import {
  Briefcase,
  FileText,
  Handshake,
  Flame,
  Inbox,
  Menu,
  Radio,
  LayoutDashboard,
  LogOut,
  MessageSquare,
  Newspaper,
  Plug,
  PlusCircle,
  Radar,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { cn, initials } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Wallet } from "@/components/billing/wallet";
import { Badge } from "@/components/ui/badge";
import { Logo } from "@/components/brand/logo";

interface NavItem {
  to: string;
  label: string;
  icon: typeof Briefcase;
  end?: boolean;
}

const NAV_BY_ROLE: Record<string, NavItem[]> = {
  job_seeker: [
    { to: "/app", label: "Job feed", icon: Briefcase, end: true },
    { to: "/app/matches", label: "Matches", icon: Sparkles },
    { to: "/app/autopilot", label: "Autopilot", icon: Radio },
    { to: "/app/momentum", label: "Momentum", icon: Flame },
    { to: "/app/resume", label: "Résumé", icon: FileText },
    { to: "/app/applications", label: "Applications", icon: Inbox },
    { to: "/app/outreach", label: "Hiring managers", icon: Send },
    { to: "/app/interviews", label: "Interviews", icon: MessageSquare },
    { to: "/app/negotiation", label: "Negotiation", icon: Handshake },
    { to: "/app/digest", label: "Digest", icon: Newspaper },
    { to: "/app/profile", label: "Profile", icon: Settings },
  ],
  employer: [
    { to: "/employer", label: "My jobs", icon: LayoutDashboard, end: true },
    { to: "/employer/post", label: "Post a job", icon: PlusCircle },
  ],
  admin: [
    { to: "/admin", label: "Analytics", icon: LayoutDashboard, end: true },
    { to: "/admin/mailboxes", label: "Alert mailboxes", icon: Inbox },
    { to: "/admin/concierge", label: "Applications to file", icon: Send },
    { to: "/admin/jobs/pending", label: "Pending jobs", icon: Briefcase },
    { to: "/admin/integrations", label: "Integrations", icon: Plug },
    { to: "/admin/users", label: "Users", icon: Users },
    { to: "/admin/ops", label: "Ops health", icon: Radar },
  ],
};

/**
 * The app frame.
 *
 * The sidebar was a hard `w-60` at every width. On a 390px phone that left
 * 150px for the page and 86px inside its padding — one word per line, with
 * controls running off the right edge. Below `lg` it is now a drawer behind a
 * top bar, and the page gets the whole screen.
 */
export function AppShell() {
  const { user, logout } = useAuth();
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  // Tapping a destination should take you there, not leave you looking at the
  // menu you just used.
  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!navOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setNavOpen(false);
    };
    document.addEventListener("keydown", onKey);
    // Without this the page scrolls behind the drawer, which reads as the app
    // losing your place while you are choosing where to go.
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [navOpen]);

  if (!user) return null;

  const items = NAV_BY_ROLE[user.role] ?? [];
  const isSeeker = user.role === "job_seeker";

  return (
    <div className="min-h-screen bg-bg-tint lg:flex">
      {/* Phone and tablet only: the app's own top bar. */}
      <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-border bg-white px-4 py-2.5 lg:hidden">
        <button
          type="button"
          onClick={() => setNavOpen(true)}
          aria-label="Open menu"
          aria-expanded={navOpen}
          aria-controls="app-nav"
          className="-ml-1 rounded-lg p-2 text-ink-muted transition-colors hover:bg-surface-2 hover:text-ink"
        >
          <Menu className="h-5 w-5" />
        </button>
        <Link to="/" aria-label="JobQuick AI home">
          <Logo height={22} />
        </Link>
        <div className="ml-auto flex items-center gap-1">
          {isSeeker && <Wallet variant="compact" />}
          <button
            onClick={logout}
            className="rounded-lg p-2 text-ink-faint transition-colors hover:bg-surface-2 hover:text-danger"
            aria-label="Log out"
          >
            <LogOut className="h-5 w-5" />
          </button>
        </div>
      </header>

      {navOpen && (
        <div
          className="fixed inset-0 z-40 bg-navy/50 lg:hidden"
          onClick={() => setNavOpen(false)}
          aria-hidden
        />
      )}

      <aside
        id="app-nav"
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-[17rem] max-w-[85vw] flex-col border-r border-border bg-white",
          "transition-transform duration-200 ease-out",
          // `invisible`, not only a translate: an off-screen drawer that still
          // takes tab focus sends keyboard users into a menu they cannot see.
          navOpen ? "visible translate-x-0" : "invisible -translate-x-full",
          "lg:visible lg:sticky lg:top-0 lg:z-auto lg:h-screen lg:w-60 lg:translate-x-0 lg:transition-none",
        )}
      >
        <div className="flex items-center justify-between px-5 py-5">
          <Link to="/" aria-label="JobQuick AI home">
            <Logo height={26} />
          </Link>
          <button
            type="button"
            onClick={() => setNavOpen(false)}
            aria-label="Close menu"
            className="-mr-2 rounded-lg p-2 text-ink-muted hover:bg-surface-2 hover:text-ink lg:hidden"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable: eleven destinations do not fit above the fold on a
            short phone, and the account block below has to stay reachable. */}
        <nav className="flex flex-1 flex-col gap-0.5 overflow-y-auto px-3">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2.5 text-sm transition-colors lg:py-2",
                  isActive ? "bg-violet-soft font-semibold text-violet-dark" : "text-ink-muted hover:bg-surface-2 hover:text-ink"
                )
              }
            >
              <item.icon className="h-4 w-4 shrink-0" strokeWidth={1.75} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-border p-3">
          {/* A balance nobody can act on is just a number. This one opens
              the wallet and says what it buys. */}
          {isSeeker && (
            <div className="mb-2">
              <Wallet />
            </div>
          )}
          <div className="flex items-center gap-2 rounded-lg px-2 py-1.5">
            <Avatar>
              <AvatarFallback>{initials(user.full_name)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{user.full_name}</p>
              <div className="flex items-center gap-1.5">
                {isSeeker && (
                  <Badge tone={user.subscription_tier === "elite" ? "accent" : "neutral"} className="px-1.5 py-0">
                    {user.subscription_tier}
                  </Badge>
                )}
                {user.role === "admin" && (
                  <span className="flex items-center gap-1 text-[0.65rem] text-ink-faint">
                    <ShieldCheck className="h-3 w-3" /> admin
                  </span>
                )}
              </div>
            </div>
            <button
              onClick={logout}
              className="rounded-md p-1.5 text-ink-faint hover:bg-surface-2 hover:text-danger"
              aria-label="Log out"
              title="Log out"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* min-w-0 so a wide child — a table, a long unbroken title — is made to
          fit rather than pushing the whole layout sideways. */}
      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8 lg:py-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
