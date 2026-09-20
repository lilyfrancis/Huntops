import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, Sparkles } from "lucide-react";
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
import type { Job, MatchRun } from "@/lib/types";

/** Why there is nothing here, in the words that fit the actual reason.
 *
 * Nothing to score and nothing good enough are different problems with
 * different fixes — widen your filters, or the roles coming in genuinely do
 * not suit you — and one sentence for both sent people to change the wrong
 * thing.
 */
function emptyCopy(run: MatchRun | undefined): { title: string; description: string } {
  if (run && run.candidates_scored === 0) {
    return {
      title: "No jobs to score yet",
      description:
        "Nothing in the pool matches the markets and lanes you picked. Widen them in Autopilot, or wait for the next alert sync.",
    };
  }
  if (run) {
    return {
      title: "No strong matches yet",
      description: `Scored ${run.candidates_scored} role${run.candidates_scored === 1 ? "" : "s"}, none above ${run.threshold}. Widen your filters, or add skills to your résumé.`,
    };
  }
  return {
    title: "No strong matches yet",
    description: "Refresh once new jobs have come in, or broaden your résumé's listed skills.",
  };
}

export function MatchesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [outreachTargetId, setOutreachTargetId] = useState<string | null>(null);

  const { data: resume } = useQuery({ queryKey: ["resume", "me"], queryFn: resumesApi.me, retry: false });

  const {
    data: run,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ["matches"],
    queryFn: () => matchesApi.list(20),
    enabled: !!resume,
    // Scoring is an AI call behind a 20/hour limit. Retrying a 429 or a
    // provider failure spends the remaining budget to fail three more times.
    retry: false,
  });
  const matches = run?.matches;

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
      ) : error ? (
        // Scoring failing and scoring finding nothing are different facts,
        // and both used to render as "No strong matches yet" — so a rate
        // limit or a provider outage looked like an honest empty result and
        // sent people off to rewrite a résumé that was never the problem.
        <EmptyState
          icon={AlertTriangle}
          title="Scoring didn't run"
          description={error instanceof ApiError ? error.message : "Something went wrong while scoring."}
          action={
            <Button onClick={() => refetch()} size="sm" variant="outline">
              Try again
            </Button>
          }
        />
      ) : !matches || matches.length === 0 ? (
        <EmptyState icon={Sparkles} {...emptyCopy(run)} />
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
