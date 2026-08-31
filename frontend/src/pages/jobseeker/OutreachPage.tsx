import { useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Send } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { outreachApi, jobsApi } from "@/lib/api";
import type { Outreach, OutreachStatus } from "@/lib/types";

const STATUS_TONE: Record<OutreachStatus, "good" | "accent" | "danger"> = {
  sent: "good",
  draft_no_contact: "accent",
  failed: "danger",
};

const STATUS_LABEL: Record<OutreachStatus, string> = {
  sent: "Sent",
  draft_no_contact: "Draft",
  failed: "Send failed",
};

export function OutreachPage() {
  const [selected, setSelected] = useState<Outreach | null>(null);

  const { data: outreach, isLoading } = useQuery({ queryKey: ["outreach", "mine"], queryFn: outreachApi.mine });

  const jobQueries = useQueries({
    queries: (outreach ?? []).map((o) => ({ queryKey: ["jobs", o.job_id], queryFn: () => jobsApi.get(o.job_id) })),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Autopilot"
        title="Outreach"
        description="Every pitch drafted or sent on your behalf, with the recruiter's own words never touched."
      />

      {isLoading ? (
        <PageSpinner />
      ) : !outreach || outreach.length === 0 ? (
        <EmptyState
          icon={Send}
          title="No outreach yet"
          description="Request Autopilot Outreach from a match to see it show up here."
        />
      ) : (
        <div className="space-y-3">
          {outreach.map((o, i) => {
            const job = jobQueries[i]?.data;
            return (
              <Card
                key={o.id}
                className="flex cursor-pointer items-center justify-between gap-4 p-4 hover:border-border-strong"
                onClick={() => setSelected(o)}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-ink">{job?.title ?? "Loading…"}</p>
                  <p className="truncate text-xs text-ink-muted">{o.email_subject}</p>
                </div>
                <div className="flex shrink-0 items-center gap-3">
                  <span className="font-mono text-xs text-ink-faint">
                    {formatDistanceToNow(new Date(o.created_at), { addSuffix: true })}
                  </span>
                  <Badge tone={STATUS_TONE[o.status]}>{STATUS_LABEL[o.status]}</Badge>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      <Dialog open={!!selected} onOpenChange={(v) => !v && setSelected(null)}>
        <DialogContent className="max-w-xl">
          {selected && (
            <>
              <DialogTitle>{selected.email_subject ?? "Outreach"}</DialogTitle>
              <DialogDescription>
                <Badge tone={STATUS_TONE[selected.status]}>{STATUS_LABEL[selected.status]}</Badge>
              </DialogDescription>

              <div className="max-h-80 space-y-4 overflow-y-auto">
                {selected.email_body && (
                  <div>
                    <p className="mb-1.5 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">Email</p>
                    <p className="whitespace-pre-wrap rounded-lg border border-border bg-surface-2 p-3 text-sm text-ink-muted">
                      {selected.email_body}
                    </p>
                  </div>
                )}
                {selected.linkedin_msg && (
                  <div>
                    <p className="mb-1.5 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">
                      LinkedIn note
                    </p>
                    <p className="whitespace-pre-wrap rounded-lg border border-border bg-surface-2 p-3 text-sm text-ink-muted">
                      {selected.linkedin_msg}
                    </p>
                  </div>
                )}
                {selected.cv_bullets.length > 0 && (
                  <div>
                    <p className="mb-1.5 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">
                      Tailored CV bullets
                    </p>
                    <ul className="list-inside list-disc space-y-1 text-sm text-ink-muted">
                      {selected.cv_bullets.map((bullet, i) => (
                        <li key={i}>{bullet}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
