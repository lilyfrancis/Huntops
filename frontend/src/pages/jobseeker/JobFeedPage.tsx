import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Briefcase, SlidersHorizontal } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { FeedCard } from "@/components/jobs/feed-card";
import { JobDetailDialog } from "@/components/jobs/job-detail-dialog";
import { Button } from "@/components/ui/button";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { applicationsApi, jobsApi, outreachApi, preferencesApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { humanize } from "@/lib/labels";
import type { Job } from "@/lib/types";

export function JobFeedPage() {
  const queryClient = useQueryClient();
  const [ignorePreferences, setIgnorePreferences] = useState(false);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const { data: prefs } = useQuery({ queryKey: ["preferences"], queryFn: preferencesApi.get });
  const { data: feed, isLoading } = useQuery({
    queryKey: ["jobs", "feed", { ignorePreferences }],
    queryFn: () => jobsApi.feed({ ignore_preferences: ignorePreferences || undefined, limit: 50 }),
  });

  const refreshFeed = () => queryClient.invalidateQueries({ queryKey: ["jobs", "feed"] });

  const applyMutation = useMutation({
    mutationFn: (jobId: string) => applicationsApi.apply(jobId),
    onSuccess: () => {
      toast.success("Application submitted");
      refreshFeed();
      queryClient.invalidateQueries({ queryKey: ["applications"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't apply"),
  });

  const outreachMutation = useMutation({
    mutationFn: (jobId: string) => outreachApi.create(jobId),
    onSuccess: (result) => {
      toast.success(
        result.status === "sent"
          ? "Contact found and your pitch was sent"
          : "Draft ready — no contact email found, so it wasn't sent"
      );
      refreshFeed();
      queryClient.invalidateQueries({ queryKey: ["outreach"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start outreach"),
  });

  const filterSummary = [
    ...(prefs?.target_markets ?? []),
    ...(prefs?.locations ?? []),
    ...(prefs?.lanes ?? []).map(humanize),
  ];
  const hasFilters = filterSummary.length > 0;

  return (
    <div>
      <PageHeader
        eyebrow="Your feed"
        title="Job feed"
        description="Drawn from the markets you picked — our alert mailboxes plus six live job-board sources."
        action={
          <Button variant="outline" size="sm" asChild>
            <Link to="/app/autopilot">
              <SlidersHorizontal className="h-3.5 w-3.5" /> Preferences
            </Link>
          </Button>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-2">
        <span className="text-sm text-ink-muted">
          {hasFilters && !ignorePreferences ? (
            <>
              Showing <span className="font-semibold text-ink">{filterSummary.join(", ")}</span>
            </>
          ) : (
            "Showing everything in the pool"
          )}
        </span>
        {hasFilters && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIgnorePreferences((v) => !v)}
            aria-pressed={ignorePreferences}
          >
            {ignorePreferences ? "Back to my preferences" : "Show everything"}
          </Button>
        )}
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : !feed || feed.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title={hasFilters ? "Nothing matches your preferences yet" : "No jobs in the pool yet"}
          description={
            hasFilters
              ? "Widen your markets or job families, or check back after the next mailbox sync."
              : "New listings arrive each morning from the alert mailboxes and the aggregation run."
          }
          action={
            hasFilters ? (
              <Button size="sm" variant="outline" onClick={() => setIgnorePreferences(true)}>
                Show everything
              </Button>
            ) : undefined
          }
        />
      ) : (
        <div className="space-y-3">
          {feed.map((item) => (
            <FeedCard
              key={item.job.id}
              item={item}
              onOpen={() => setSelectedJob(item.job)}
              onApply={() => applyMutation.mutate(item.job.id)}
              onOutreach={() => outreachMutation.mutate(item.job.id)}
              isApplying={applyMutation.isPending && applyMutation.variables === item.job.id}
              isDrafting={outreachMutation.isPending && outreachMutation.variables === item.job.id}
            />
          ))}
        </div>
      )}

      <JobDetailDialog job={selectedJob} open={!!selectedJob} onOpenChange={(v) => !v && setSelectedJob(null)} />
    </div>
  );
}
