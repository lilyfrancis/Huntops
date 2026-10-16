import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { Ghost, Mail, PlayCircle, Radar, TriangleAlert } from "lucide-react";
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
  const { data: supply } = useQuery({ queryKey: ["admin", "supply"], queryFn: adminApi.supply });

  const triggerMutation = useMutation({
    mutationFn: adminApi.triggerAggregation,
    onSuccess: (summary) => {
      const inserted = Object.values(summary).reduce((sum, s) => sum + s.inserted, 0);
      toast.success(`Aggregation complete — ${inserted} new jobs`);
      queryClient.invalidateQueries({ queryKey: ["admin", "aggregation-runs"] });
    },
    onError: () => toast.error("Aggregation run failed"),
  });

  const rescanMutation = useMutation({
    mutationFn: adminApi.rescanGhosts,
    onSuccess: (summary) => {
      toast.success(`Rescanned ${summary.scanned} jobs — ${summary.likely_ghost} flagged as likely ghosts`);
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: () => toast.error("Ghost rescan failed"),
  });

  /* A pool that is almost entirely "remote, no restriction stated" is not a
     pool of globally open jobs — it is a pool whose geography was never
     derived, and the eligibility filter reads those nulls as "open to
     everybody". That looks identical to the filter not working. */
  const geographyLooksUnderived =
    !!supply &&
    supply.totals.active > 20 &&
    supply.eligibility.restricted / supply.totals.active < 0.1;

  return (
    <div className="space-y-10">
      {supply && (
        <div>
          <PageHeader
            eyebrow="Supply"
            title="Where the pool comes from"
            description="Counted from the live jobs themselves, not from what a sync reported reading — a mailbox that reads forty messages and recognises none of them still reports success."
          />

          <div className="grid gap-3 sm:grid-cols-3">
            <Card className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                From alert mailboxes
              </p>
              <p className="mt-1 font-mono text-2xl font-bold tabular-nums text-ink">
                {supply.totals.from_alert_mailboxes}
              </p>
              <p className="mt-1 text-xs text-ink-faint">
                {supply.mailboxes.active} of {supply.mailboxes.configured} mailbox(es) active
              </p>
            </Card>
            <Card className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                From job boards
              </p>
              <p className="mt-1 font-mono text-2xl font-bold tabular-nums text-ink">
                {supply.totals.from_job_boards}
              </p>
              <p className="mt-1 text-xs text-ink-faint">Six global APIs, mostly remote-first</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
                Open to anyone
              </p>
              <p className="mt-1 font-mono text-2xl font-bold tabular-nums text-ink">
                {supply.eligibility.remote_unrestricted}
              </p>
              <p className="mt-1 text-xs text-ink-faint">
                {supply.eligibility.restricted} restricted · {supply.eligibility.no_geography} with no
                geography
              </p>
            </Card>
          </div>

          {geographyLooksUnderived && (
            <p className="mt-3 flex items-start gap-2 rounded-xl border border-warning/30 bg-warning-soft px-4 py-3 text-sm text-warning">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              <span>
                Almost nothing in the pool carries a geographic restriction, so the eligibility
                filter is reading nulls as "open to everybody" and will show a Nigerian user
                US-only roles. Run{" "}
                <code className="font-mono text-xs">python -m app.scripts.rederive_job_geo</code> on
                the API container.
              </span>
            </p>
          )}

          <div className="mt-4 grid gap-4 md:grid-cols-2">
            <Card className="p-4">
              <p className="mb-3 flex items-center gap-1.5 text-sm font-semibold text-ink">
                <Mail className="h-3.5 w-3.5" /> By source
              </p>
              <ul className="space-y-1.5">
                {supply.by_source.map((row) => (
                  <li key={row.name} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate text-ink-muted">{row.name}</span>
                    <span className="shrink-0 font-mono tabular-nums text-ink">{row.active}</span>
                  </li>
                ))}
              </ul>
            </Card>
            <Card className="p-4">
              <p className="mb-3 text-sm font-semibold text-ink">By market</p>
              <ul className="space-y-1.5">
                {supply.by_market.map((row) => (
                  <li key={row.name} className="flex items-center justify-between gap-3 text-sm">
                    <span className="truncate text-ink-muted">{row.name}</span>
                    <span className="shrink-0 font-mono tabular-nums text-ink">{row.active}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-xs text-ink-faint">
                "(none)" is the global boards, which belong to no market by design.
              </p>
            </Card>
          </div>
        </div>
      )}

      <div>
        <PageHeader
          eyebrow="Ingestion"
          title="Aggregation runs"
          description="Each of the six job sources runs independently — one failing never blocks the rest."
          action={
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => rescanMutation.mutate()}
                disabled={rescanMutation.isPending}
              >
                <Ghost className="h-3.5 w-3.5" /> {rescanMutation.isPending ? "Scanning…" : "Rescan ghosts"}
              </Button>
              <Button size="sm" onClick={() => triggerMutation.mutate()} disabled={triggerMutation.isPending}>
                <PlayCircle className="h-3.5 w-3.5" /> {triggerMutation.isPending ? "Running…" : "Run now"}
              </Button>
            </div>
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
        <PageHeader
          eyebrow="Email bridge"
          title="Mailbox sync runs"
          description="One row per alert-mailbox sync attempt. A mailbox that stops syncing is a market whose feed quietly stops filling."
        />
        {emailLoading ? (
          <PageSpinner />
        ) : !emailRuns || emailRuns.length === 0 ? (
          <EmptyState
            icon={Radar}
            title="No syncs yet"
            description="Runs once a mailbox is connected and the daily 07:10 UTC job fires."
          />
        ) : (
          <div className="space-y-2">
            {emailRuns.map((run) => (
              <Card key={run.id} className="p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex min-w-0 items-center gap-2">
                    <Badge tone={run.status === "success" ? "good" : "danger"}>{run.status}</Badge>
                    {/* Rows predating central mailboxes carry a user id and no
                        name — kept as history rather than deleted with the feature. */}
                    <span className="truncate text-sm text-ink">{run.mailbox ?? "Legacy per-user sync"}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-ink-muted">
                    <span>{run.fetched_count} fetched</span>
                    <span>{run.extracted_count} extracted</span>
                    <span>{run.inserted_count} inserted</span>
                    <span className="font-mono text-ink-faint">
                      {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
                    </span>
                  </div>
                </div>
                {run.error && <p className="mt-2 break-words text-sm text-danger">{run.error}</p>}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
