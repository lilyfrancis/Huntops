import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, ChevronLeft, ChevronRight, Sparkles } from "lucide-react";
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

/* Matches are a stable ranking, not a stream: nothing is re-scored once it
   has a score, so the top of the list is the same every visit by design.
   Without paging that reads as the page being broken — which is exactly how
   it was reported. */
const PAGE_SIZE = 20;

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

/** What is left to look at, and what has already been ruled out.
 *
 * Nothing scored yet and nothing good enough are different facts with
 * opposite fixes — press Refresh, or widen the filters — and a bare count of
 * survivors cannot tell them apart.
 */
function ScoringProgress({
  run,
  onRefresh,
  busy,
}: {
  run: MatchRun | undefined;
  onRefresh: () => void;
  busy: boolean;
}) {
  if (!run || run.unscored_remaining === 0) return null;
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-surface-2 px-4 py-3">
      <p className="text-sm text-ink-muted">
        <span className="font-semibold text-ink">{run.unscored_remaining}</span> more job
        {run.unscored_remaining === 1 ? "" : "s"} match your filters and have not been scored yet
        {run.below_threshold > 0 && <> — {run.below_threshold} were scored and came in under {run.threshold}</>}
        . Each refresh scores the next batch.
      </p>
      <Button size="sm" variant="outline" onClick={onRefresh} disabled={busy}>
        {busy ? "Scoring…" : "Score more"}
      </Button>
    </div>
  );
}

export function MatchesPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [outreachTargetId, setOutreachTargetId] = useState<string | null>(null);
  const [page, setPage] = useState(0);

  const { data: resume } = useQuery({ queryKey: ["resume", "me"], queryFn: resumesApi.me, retry: false });

  const {
    data: run,
    isLoading,
    isFetching,
    error,
    refetch,
  } = useQuery({
    queryKey: ["matches", page],
    queryFn: () => matchesApi.list(PAGE_SIZE, page * PAGE_SIZE),
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
          <Button
            onClick={() => (page === 0 ? refetch() : setPage(0))}
            disabled={isFetching}
            variant="outline"
            size="sm"
          >
            {/* Back to page one, because scoring only runs there — refreshing
                from page three would spend nothing and change nothing. */}
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
        <>
          <EmptyState icon={Sparkles} {...emptyCopy(run)} />
          <ScoringProgress run={run} onRefresh={() => refetch()} busy={isFetching} />
        </>
      ) : (
        <>
          {/* Says out loud that this is the top of a longer ranking. A list
              that is identical every visit reads as nothing having happened,
              and the count is the cheapest way to show that it did. */}
          <p className="mb-2 text-sm text-ink-muted">
            Showing <span className="font-semibold text-ink">{page * PAGE_SIZE + 1}–
            {page * PAGE_SIZE + matches.length}</span> of {run?.total ?? matches.length}, best fit
            first. Scored once and kept — a job you have already been scored against will not
            change place.
          </p>

          {/* "1 of 1" is true and useless on its own. Three hundred jobs can
              match the filters and be waiting unscored, which looks identical
              to there being nothing for you — and the two have opposite
              fixes: press Refresh, or widen the filters. */}
          <ScoringProgress run={run} onRefresh={() => (page === 0 ? refetch() : setPage(0))} busy={isFetching} />

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

          {(page > 0 || (run?.total ?? 0) > (page + 1) * PAGE_SIZE) && (
            <div className="mt-6 flex items-center justify-between gap-3 border-t border-border pt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0 || isFetching}
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Previous
              </Button>
              <span className="font-mono text-xs tabular-nums text-ink-faint">Page {page + 1}</span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => p + 1)}
                disabled={(run?.total ?? 0) <= (page + 1) * PAGE_SIZE || isFetching}
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </>
      )}

      <JobDetailDialog job={selectedJob} open={!!selectedJob} onOpenChange={(v) => !v && setSelectedJob(null)} />
    </div>
  );
}
