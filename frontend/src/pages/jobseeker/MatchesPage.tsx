import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { PageHeader } from "@/components/layout/page-header";
import { MatchCard } from "@/components/matches/match-card";
import { JobDetailDialog } from "@/components/jobs/job-detail-dialog";
import { Button } from "@/components/ui/button";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { matchesApi, outreachApi, resumesApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import type { Job } from "@/lib/types";

export function MatchesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [outreachTargetId, setOutreachTargetId] = useState<string | null>(null);

  const { data: resume } = useQuery({ queryKey: ["resume", "me"], queryFn: resumesApi.me, retry: false });

  const {
    data: matches,
    isLoading,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ["matches"],
    queryFn: () => matchesApi.list(20),
    enabled: !!resume,
  });

  const outreachMutation = useMutation({
    mutationFn: (jobId: string) => {
      setOutreachTargetId(jobId);
      return outreachApi.create(jobId);
    },
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: ["outreach", "mine"] });
      if (result.status === "sent") {
        toast.success("Pitch sent from your inbox", { action: { label: "View", onClick: () => navigate("/app/outreach") } });
      } else {
        toast.success("Pitch drafted — no recruiter contact or Gmail connected yet", {
          action: { label: "View draft", onClick: () => navigate("/app/outreach") },
        });
      }
    },
    onError: (e) => {
      if (e instanceof ApiError && e.status === 403) toast.error("Autopilot Outreach needs the Elite tier", { action: { label: "Upgrade", onClick: () => navigate("/app/profile") } });
      else if (e instanceof ApiError && e.status === 402) toast.error(e.message);
      else if (e instanceof ApiError && e.status === 404) toast.error(e.message);
      else toast.error("Couldn't start outreach");
    },
    onSettled: () => setOutreachTargetId(null),
  });

  if (!resume) {
    return (
      <div>
        <PageHeader eyebrow="Fit intelligence" title="Matches" />
        <EmptyState
          icon={Sparkles}
          title="Upload a résumé first"
          description="Matching scores your résumé against open roles — there's nothing to compare yet."
          action={
            <Button onClick={() => navigate("/app/resume")} size="sm">
              Go to résumé
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div>
      <PageHeader
        eyebrow="Fit intelligence"
        title="Matches"
        description="Scored against your résumé, boosted if a role is open to where you live."
        action={
          <Button onClick={() => refetch()} disabled={isFetching} variant="outline" size="sm">
            {isFetching ? "Scoring…" : "Refresh matches"}
          </Button>
        }
      />

      {isLoading ? (
        <PageSpinner />
      ) : !matches || matches.length === 0 ? (
        <EmptyState
          icon={Sparkles}
          title="No strong matches yet"
          description="Refresh once new jobs have come in, or broaden your résumé's listed skills."
        />
      ) : (
        <div className="space-y-4">
          {matches.map((match) => (
            <MatchCard
              key={match.job.id}
              match={match}
              onViewJob={() => setSelectedJob(match.job)}
              onRequestOutreach={() => outreachMutation.mutate(match.job.id)}
              outreachPending={outreachMutation.isPending && outreachTargetId === match.job.id}
              outreachDisabled={user?.subscription_tier !== "elite"}
            />
          ))}
        </div>
      )}

      <JobDetailDialog job={selectedJob} open={!!selectedJob} onOpenChange={(v) => !v && setSelectedJob(null)} />
    </div>
  );
}
