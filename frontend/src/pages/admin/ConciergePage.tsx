import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { CheckCircle2, ExternalLink, Send, XCircle } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageSpinner } from "@/components/ui/spinner";
import { adminApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { ConciergeQueueItem, ConciergeStatus } from "@/lib/types";

const TABS: { value: ConciergeStatus | "all"; label: string }[] = [
  { value: "queued", label: "To do" },
  { value: "submitted", label: "Filed" },
  { value: "blocked", label: "Blocked" },
  { value: "all", label: "Everything" },
];

export function ConciergePage() {
  const [tab, setTab] = useState<ConciergeStatus | "all">("queued");
  const { data: rows, isLoading } = useQuery({
    queryKey: ["admin", "concierge", tab],
    queryFn: () => adminApi.conciergeQueue(tab),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Concierge"
        title="Applications to file"
        description="Jobs users asked us to apply to on their behalf. Apply under their HuntOps address, then mark it filed."
      />

      <div className="mb-4 flex flex-wrap gap-2">
        {TABS.map((t) => (
          <Button
            key={t.value}
            size="sm"
            variant={tab === t.value ? "solid" : "outline"}
            onClick={() => setTab(t.value)}
          >
            {t.label}
          </Button>
        ))}
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : !rows || rows.length === 0 ? (
        <EmptyState
          icon={CheckCircle2}
          title={tab === "queued" ? "Nothing waiting" : "Nothing here"}
          description={
            tab === "queued"
              ? "Every request has been dealt with."
              : "No applications in this state."
          }
        />
      ) : (
        <div className="space-y-3">
          {rows.map((row) => (
            <QueueRow key={row.id} row={row} />
          ))}
        </div>
      )}
    </div>
  );
}

function QueueRow({ row }: { row: ConciergeQueueItem }) {
  const queryClient = useQueryClient();
  const [email, setEmail] = useState(row.concierge_email ?? row.suggested_concierge_email);
  const [note, setNote] = useState(row.concierge_note ?? "");
  const [open, setOpen] = useState(false);

  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "concierge"] });

  const mark = useMutation({
    mutationFn: (status: ConciergeStatus) =>
      adminApi.markConcierge(row.id, {
        concierge_status: status,
        note: note.trim() || undefined,
        concierge_email: email.trim() || undefined,
      }),
    onSuccess: (_r, status) => {
      toast.success(status === "submitted" ? "Marked as filed" : "Marked as blocked");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't update"),
  });

  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="mb-1 flex flex-wrap items-center gap-2">
            <Badge tone="accent">{row.candidate_name}</Badge>
            {row.concierge_email ? (
              <Badge tone="neutral">{row.concierge_email}</Badge>
            ) : (
              <Badge tone="warning">no address yet</Badge>
            )}
          </div>
          <p className="truncate text-base font-semibold text-ink">{row.job_title}</p>
          <p className="truncate text-sm text-ink-muted">
            {row.company_name ?? "Company withheld"} · {row.job_location}
          </p>
        </div>
        <span className="whitespace-nowrap font-mono text-xs text-ink-faint">
          asked {formatDistanceToNow(new Date(row.created_at), { addSuffix: true })}
        </span>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {row.source_url && (
          <Button size="sm" variant="outline" asChild>
            <a href={row.source_url} target="_blank" rel="noreferrer noopener">
              Open listing <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </Button>
        )}
        <Button size="sm" variant="ghost" onClick={() => setOpen(!open)}>
          {open ? "Hide details" : "Letter & bullets"}
        </Button>
      </div>

      {open && (
        <div className="mt-3 space-y-3 rounded-lg border border-border bg-surface-2 p-3">
          <div>
            <Label htmlFor={`email-${row.id}`}>Apply under</Label>
            <Input
              id={`email-${row.id}`}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="e.g. jennifer@huntops.site"
            />
            <p className="mt-1 text-xs text-ink-faint">
              {row.concierge_email
                ? "Already used for this person — keep it consistent so replies land in one place."
                : "Suggested from their first name. Create the mailbox in Hostinger, then record what you actually used."}
            </p>
          </div>

          {row.cover_letter ? (
            <div>
              <p className="mb-1 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">Cover letter</p>
              <p className="whitespace-pre-wrap rounded-lg border border-border bg-white p-3 text-sm text-ink-muted">
                {row.cover_letter}
              </p>
            </div>
          ) : (
            <p className="text-xs text-ink-faint">No tailored letter — the user did not generate one.</p>
          )}

          {row.tailored_bullets.length > 0 && (
            <div>
              <p className="mb-1 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">Résumé bullets</p>
              <ul className="list-inside list-disc space-y-1 text-sm text-ink-muted">
                {row.tailored_bullets.map((b, i) => (
                  <li key={i}>{b}</li>
                ))}
              </ul>
            </div>
          )}

          <div>
            <Label htmlFor={`note-${row.id}`}>Note to the user</Label>
            <Input
              id={`note-${row.id}`}
              value={note}
              onChange={(e) => setNote(e.target.value)}
              placeholder="e.g. Listing was taken down"
            />
            <p className="mt-1 text-xs text-ink-faint">They see this, so write it for them.</p>
          </div>

          <div className="flex flex-wrap gap-2">
            <Button size="sm" onClick={() => mark.mutate("submitted")} disabled={mark.isPending}>
              <Send className="h-3.5 w-3.5" /> Mark filed
            </Button>
            <Button size="sm" variant="danger" onClick={() => mark.mutate("blocked")} disabled={mark.isPending}>
              <XCircle className="h-3.5 w-3.5" /> Couldn't file
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}
