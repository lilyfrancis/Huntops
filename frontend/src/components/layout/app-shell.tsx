import { Link, NavLink, Outlet } from "react-router-dom";
import {
  Briefcase,
  FileText,
  Handshake,
  Flame,
  Inbox,
  LayoutDashboard,
  LogOut,
  Mail,
  MessageSquare,
  Newspaper,
  PlusCircle,
  Radar,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { useAuth } from "@/hooks/use-auth";
import { cn, initials } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

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
    { to: "/app/momentum", label: "Momentum", icon: Flame },
    { to: "/app/resume", label: "Résumé", icon: FileText },
    { to: "/app/applications", label: "Applications", icon: Inbox },
    { to: "/app/outreach", label: "Outreach", icon: Send },
    { to: "/app/interviews", label: "Interviews", icon: MessageSquare },
    { to: "/app/negotiation", label: "Negotiation", icon: Handshake },
    { to: "/app/digest", label: "Digest", icon: Newspaper },
    { to: "/app/integrations", label: "Gmail", icon: Mail },
    { to: "/app/profile", label: "Profile", icon: Settings },
  ],
  employer: [
    { to: "/employer", label: "My jobs", icon: LayoutDashboard, end: true },
    { to: "/employer/post", label: "Post a job", icon: PlusCircle },
  ],
  admin: [
    { to: "/admin", label: "Analytics", icon: LayoutDashboard, end: true },
    { to: "/admin/jobs/pending", label: "Pending jobs", icon: Briefcase },
    { to: "/admin/users", label: "Users", icon: Users },
    { to: "/admin/ops", label: "Ops health", icon: Radar },
  ],
};

export function AppShell() {
  const { user, logout } = useAuth();
  if (!user) return null;

  const items = NAV_BY_ROLE[user.role] ?? [];

  return (
    <div className="flex min-h-screen bg-bg">
      <aside className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
        <Link to="/" className="flex items-center gap-2 px-5 py-5 font-mono text-sm font-semibold tracking-wide text-ink">
          HUNTOPS
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
        </Link>

        <nav className="flex flex-1 flex-col gap-0.5 px-3">
          {items.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors",
                  isActive ? "bg-surface-2 text-accent-strong" : "text-ink-muted hover:bg-surface-2 hover:text-ink"
                )
              }
            >
              <item.icon className="h-4 w-4" strokeWidth={1.75} />
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-border p-3">
          {user.role === "job_seeker" && (
            <div className="mb-2 flex items-center justify-between rounded-lg bg-surface-2 px-3 py-2">
              <span className="font-mono text-[0.65rem] uppercase tracking-wide text-ink-faint">Credits</span>
              <span className="font-mono text-sm font-semibold text-accent-strong">{user.ai_credits}</span>
            </div>
          )}
          <div className="flex items-center gap-2 rounded-lg px-2 py-1.5">
            <Avatar>
              <AvatarFallback>{initials(user.full_name)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-ink">{user.full_name}</p>
              <div className="flex items-center gap-1.5">
                {user.role === "job_seeker" && (
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

      <main className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl px-8 py-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
