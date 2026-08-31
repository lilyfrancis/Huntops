import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { PlayCircle, Radar } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { adminApi } from "@/lib/api";

export function OpsHealthPage() {
  const queryClient = useQueryClient();

  const { data: runs, isLoading: runsLoading } = useQuery({
    queryKey: ["admin", "aggregation-runs"],
    queryFn: adminApi.aggregationRuns,
  });
  const { data: emailRuns, isLoading: emailLoading } = useQuery({
    queryKey: ["admin", "email-sync-runs"],
    queryFn: adminApi.emailSyncRuns,
  });

  const triggerMutation = useMutation({
    mutationFn: adminApi.triggerAggregation,
    onSuccess: (summary) => {
      const inserted = Object.values(summary).reduce((sum, s) => sum + s.inserted, 0);
      toast.success(`Aggregation complete — ${inserted} new jobs`);
      queryClient.invalidateQueries({ queryKey: ["admin", "aggregation-runs"] });
    },
    onError: () => toast.error("Aggregation run failed"),
  });

  return (
    <div className="space-y-10">
      <div>
        <PageHeader
          eyebrow="Ingestion"
          title="Aggregation runs"
          description="Each of the six job sources runs independently — one failing never blocks the rest."
          action={
            <Button size="sm" onClick={() => triggerMutation.mutate()} disabled={triggerMutation.isPending}>
              <PlayCircle className="h-3.5 w-3.5" /> {triggerMutation.isPending ? "Running…" : "Run now"}
            </Button>
          }
        />
        {runsLoading ? (
          <PageSpinner />
        ) : !runs || runs.length === 0 ? (
          <EmptyState icon={Radar} title="No runs yet" description="Trigger one manually, or wait for the daily 07:00 UTC schedule." />
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <Card key={run.id} className="flex items-center justify-between gap-4 p-3.5">
                <div className="flex items-center gap-3">
                  <Badge tone={run.status === "success" ? "good" : "danger"}>{run.status}</Badge>
                  <span className="font-mono text-sm text-ink">{run.source}</span>
                </div>
                <div className="flex items-center gap-4 text-xs text-ink-muted">
                  <span>{run.fetched_count} fetched</span>
                  <span>{run.inserted_count} inserted</span>
                  <span className="font-mono text-ink-faint">
                    {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>

      <div>
        <PageHeader eyebrow="Email bridge" title="Email sync runs" description="Per-user Gmail sync attempts, aggregated for ops visibility." />
        {emailLoading ? (
          <PageSpinner />
        ) : !emailRuns || emailRuns.length === 0 ? (
          <EmptyState icon={Radar} title="No syncs yet" description="Runs once a user connects Gmail and the daily 07:10 UTC job fires." />
        ) : (
          <div className="space-y-2">
            {emailRuns.map((run) => (
              <Card key={run.id} className="flex items-center justify-between gap-4 p-3.5">
                <Badge tone={run.status === "success" ? "good" : "danger"}>{run.status}</Badge>
                <div className="flex items-center gap-4 text-xs text-ink-muted">
                  <span>{run.fetched_count} fetched</span>
                  <span>{run.extracted_count} extracted</span>
                  <span>{run.inserted_count} inserted</span>
                  <span className="font-mono text-ink-faint">
                    {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
                  </span>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
