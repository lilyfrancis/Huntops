import { useQueries, useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Inbox } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { applicationsApi, jobsApi } from "@/lib/api";
import type { Application, ApplicationStatus, ConciergeStatus } from "@/lib/types";

const STATUS_TONE: Record<ApplicationStatus, "neutral" | "good" | "accent" | "danger" | "warning"> = {
  pending: "neutral",
  reviewed: "accent",
  interviewing: "warning",
  offered: "good",
  rejected: "danger",
  withdrawn: "neutral",
};

const CONCIERGE_TONE: Record<ConciergeStatus, "neutral" | "good" | "danger"> = {
  queued: "neutral",
  submitted: "good",
  blocked: "danger",
};

/** What is true right now, in the user's terms.
 *
 * "Applied" is not said until somebody has actually filed it. The whole
 * feature rests on the user trusting that word, and a queue that claims to
 * be a submission is the one thing that would break it.
 */
function conciergeLine(app: Application): string | null {
  if (!app.is_concierge) return null;
  switch (app.concierge_status) {
    case "submitted":
      return app.submitted_at
        ? `Filed for you ${formatDistanceToNow(new Date(app.submitted_at), { addSuffix: true })}`
        : "Filed for you";
    case "blocked":
      return "We could not file this one";
    default:
      return "Queued — we file this one for you";
  }
}

export function ApplicationsPage() {
  const { data: applications, isLoading } = useQuery({
    queryKey: ["applications", "mine"],
    queryFn: applicationsApi.mine,
  });

  const jobQueries = useQueries({
    queries: (applications ?? []).map((app) => ({
      queryKey: ["jobs", app.job_id],
      queryFn: () => jobsApi.get(app.job_id),
    })),
  });

  return (
    <div>
      <PageHeader eyebrow="Pipeline" title="Applications" description="Every job you've applied to, and how far each one has got." />

      {isLoading ? (
        <PageSpinner />
      ) : !applications || applications.length === 0 ? (
        <EmptyState icon={Inbox} title="No applications yet" description="Apply to a job from the feed or your matches to see it tracked here." />
      ) : (
        <div className="space-y-3">
          {applications.map((app, i) => {
            const job = jobQueries[i]?.data;
            return (
              <Card key={app.id} className="flex items-center justify-between gap-4 p-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{job?.title ?? "Loading…"}</p>
                  <p className="text-xs text-ink-muted">{job?.company_name ?? " "}</p>
                  {conciergeLine(app) && (
                    <p className="mt-0.5 text-xs text-ink-faint">{conciergeLine(app)}</p>
                  )}
                  {app.concierge_note && (
                    <p className="mt-0.5 text-xs text-ink-muted">{app.concierge_note}</p>
                  )}
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {app.ai_match_score != null && (
                    <span className="font-mono text-xs text-ink-faint">fit {Math.round(app.ai_match_score)}</span>
                  )}
                  <span className="font-mono text-xs text-ink-faint">
                    {formatDistanceToNow(new Date(app.created_at), { addSuffix: true })}
                  </span>
                  {app.is_concierge && app.concierge_status && (
                    <Badge tone={CONCIERGE_TONE[app.concierge_status]}>{app.concierge_status}</Badge>
                  )}
                  <Badge tone={STATUS_TONE[app.status]}>{app.status}</Badge>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
