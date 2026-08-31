import { useQueries, useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Inbox } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { applicationsApi, jobsApi } from "@/lib/api";
import type { ApplicationStatus } from "@/lib/types";

const STATUS_TONE: Record<ApplicationStatus, "neutral" | "good" | "accent" | "danger" | "warning"> = {
  pending: "neutral",
  reviewed: "accent",
  interviewing: "warning",
  offered: "good",
  rejected: "danger",
  withdrawn: "neutral",
};

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
      <PageHeader eyebrow="Pipeline" title="Applications" description="Every job you've applied to, in one place." />

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
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  {app.ai_match_score != null && (
                    <span className="font-mono text-xs text-ink-faint">fit {Math.round(app.ai_match_score)}</span>
                  )}
                  <span className="font-mono text-xs text-ink-faint">
                    {formatDistanceToNow(new Date(app.created_at), { addSuffix: true })}
                  </span>
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
