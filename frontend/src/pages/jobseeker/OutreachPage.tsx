import { useEffect, useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";
import { formatDistanceToNow } from "date-fns";
import { Send } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { outreachApi, jobsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
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

/** What still has to happen before this pitch reaches anyone.
 *
 * A draft with no recipient looked exactly like one ready to go, and the
 * difference is whether it can leave at all. Apollo often finds no email —
 * the draft is the expensive part, not the address — so the row says which
 * of the two it is.
 */
function subline(o: Outreach): string {
  if (o.status === "sent") return o.recipient_email ? `sent to ${o.recipient_email}` : "sent";
  if (o.status === "failed") return "send failed — open to retry";
  return o.recipient_email ? `ready to send to ${o.recipient_email}` : "needs a recipient";
}

export function OutreachPage() {
  const [selected, setSelected] = useState<Outreach | null>(null);
  const queryClient = useQueryClient();

  const { data: outreach, isLoading } = useQuery({ queryKey: ["outreach", "mine"], queryFn: outreachApi.mine });

  const jobQueries = useQueries({
    queries: (outreach ?? []).map((o) => ({ queryKey: ["jobs", o.job_id], queryFn: () => jobsApi.get(o.job_id) })),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Direct contact"
        title="Messages to hiring managers"
        description="We find whoever is hiring and write to them for you. Edit anything before it goes, and add an address where we could not find one."
      />

      {isLoading ? (
        <PageSpinner />
      ) : !outreach || outreach.length === 0 ? (
        <EmptyState
          icon={Send}
          title="No outreach yet"
          description="Pick a job and choose “Message the hiring manager” to see it here."
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
                  <p className="line-clamp-2 text-sm font-medium text-ink sm:truncate">{job?.title ?? "Loading…"}</p>
                  <p className="truncate text-xs text-ink-muted">{o.email_subject}</p>
                  <p className="truncate text-xs text-ink-faint">{subline(o)}</p>
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
            <DraftEditor
              key={selected.id}
              outreach={selected}
              onSent={(updated) => {
                setSelected(updated);
                queryClient.invalidateQueries({ queryKey: ["outreach", "mine"] });
              }}
            />
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DraftEditor({ outreach, onSent }: { outreach: Outreach; onSent: (o: Outreach) => void }) {
  const [subject, setSubject] = useState(outreach.email_subject ?? "");
  const [body, setBody] = useState(outreach.email_body ?? "");
  const [to, setTo] = useState(outreach.recipient_email ?? "");

  // A send rewrites the row, and the dialog stays open on the result.
  useEffect(() => {
    setSubject(outreach.email_subject ?? "");
    setBody(outreach.email_body ?? "");
    setTo(outreach.recipient_email ?? "");
  }, [outreach]);

  const alreadySent = outreach.status === "sent";

  const sendMutation = useMutation({
    mutationFn: () =>
      outreachApi.send(outreach.id, {
        to_email: to.trim() || undefined,
        // Only sent when actually changed, so an untouched draft goes exactly
        // as drafted rather than as a round-trip through a textarea.
        subject: subject !== (outreach.email_subject ?? "") ? subject : undefined,
        body: body !== (outreach.email_body ?? "") ? body : undefined,
      }),
    onSuccess: (updated) => {
      toast.success(`Sent to ${updated.recipient_email ?? to.trim()}`);
      onSent(updated);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not send"),
  });

  return (
    <>
      <DialogTitle>{outreach.email_subject ?? "Outreach"}</DialogTitle>
      <DialogDescription asChild>
        <div className="flex items-center gap-2">
          <Badge tone={STATUS_TONE[outreach.status]}>{STATUS_LABEL[outreach.status]}</Badge>
          <span className="text-xs text-ink-faint">{subline(outreach)}</span>
        </div>
      </DialogDescription>

      <div className="max-h-[26rem] space-y-4 overflow-y-auto">
        {alreadySent ? (
          <div>
            <p className="mb-1.5 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">Email</p>
            <p className="whitespace-pre-wrap rounded-lg border border-border bg-surface-2 p-3 text-sm text-ink-muted">
              {outreach.email_body}
            </p>
          </div>
        ) : (
          <>
            <div>
              <Label htmlFor="to">To</Label>
              <Input
                id="to"
                type="email"
                value={to}
                onChange={(e) => setTo(e.target.value)}
                placeholder="e.g. dana@company.com"
              />
              {!outreach.recipient_email && (
                <p className="mt-1 text-xs text-ink-faint">
                  We could not find an email for this role. The hiring manager is usually findable on
                  LinkedIn — the draft is already written and paid for.
                </p>
              )}
            </div>
            <div>
              <Label htmlFor="subject">Subject</Label>
              <Input id="subject" value={subject} onChange={(e) => setSubject(e.target.value)} />
            </div>
            <div>
              <Label htmlFor="body">Message</Label>
              <Textarea id="body" rows={10} value={body} onChange={(e) => setBody(e.target.value)} />
            </div>
          </>
        )}

        {outreach.linkedin_msg && (
          <div>
            <p className="mb-1.5 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">LinkedIn note</p>
            <p className="whitespace-pre-wrap rounded-lg border border-border bg-surface-2 p-3 text-sm text-ink-muted">
              {outreach.linkedin_msg}
            </p>
          </div>
        )}
        {outreach.cv_bullets.length > 0 && (
          <div>
            <p className="mb-1.5 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">
              Tailored CV bullets
            </p>
            <ul className="list-inside list-disc space-y-1 text-sm text-ink-muted">
              {outreach.cv_bullets.map((bullet, i) => (
                <li key={i}>{bullet}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {!alreadySent && (
        <div className="flex items-center justify-end gap-3 border-t border-border pt-4">
          <p className="mr-auto text-xs text-ink-faint">Sending costs no credits — the draft was already charged.</p>
          <Button
            onClick={() => sendMutation.mutate()}
            disabled={sendMutation.isPending || !to.trim() || !subject.trim() || !body.trim()}
          >
            <Send className="h-3.5 w-3.5" />
            {sendMutation.isPending ? "Sending…" : outreach.status === "failed" ? "Retry send" : "Send"}
          </Button>
        </div>
      )}
    </>
  );
}
