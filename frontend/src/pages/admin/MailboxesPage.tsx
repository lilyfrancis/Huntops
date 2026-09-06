import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { Inbox, Plus, RefreshCw, Trash2, TriangleAlert } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { ChipGroup } from "@/components/ui/chip-group";
import { humanize } from "@/lib/labels";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { adminApi, preferencesApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { AlertMailbox, JobLane } from "@/lib/types";

function ConnectDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const [market, setMarket] = useState("");
  const [label, setLabel] = useState("");
  const [lanes, setLanes] = useState<string[]>([]);

  const { data: options } = useQuery({ queryKey: ["preference-options"], queryFn: preferencesApi.options });

  const connectMutation = useMutation({
    mutationFn: () =>
      adminApi.connectMailbox({
        market: market.trim(),
        label: label.trim() || undefined,
        lanes: lanes as JobLane[],
      }),
    onSuccess: (result) => {
      window.location.href = result.authorization_url;
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start the connection"),
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogTitle>Connect an alert mailbox</DialogTitle>

        <div className="mt-4 space-y-5">
          <p className="text-sm text-ink-muted">
            Sign in as the Google account that receives this market's job alerts. HuntOps creates its own label and
            routing filters there automatically, and only ever reads what those filters catch.
          </p>

          <div className="space-y-1.5">
            <Label htmlFor="market">Market</Label>
            <Input
              id="market"
              placeholder="Canada"
              value={market}
              onChange={(e) => setMarket(e.target.value)}
            />
            <p className="text-xs text-ink-faint">
              Every job from this mailbox is tagged with it, and this is what users pick at signup.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="label">Label (optional)</Label>
            <Input
              id="label"
              placeholder="Canada — LinkedIn + Indeed"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label>Job families this mailbox covers (optional)</Label>
            <ChipGroup
              aria-label="Mailbox job families"
              options={(options?.lanes ?? []).map((l) => ({ value: l, label: humanize(l) }))}
              value={lanes}
              onChange={setLanes}
            />
            <p className="text-xs text-ink-faint">
              Used only when a job's own title gives nothing away — the listing always wins when it does.
            </p>
          </div>

          <Button
            className="w-full"
            onClick={() => connectMutation.mutate()}
            disabled={!market.trim() || connectMutation.isPending}
          >
            {connectMutation.isPending ? "Redirecting to Google…" : "Continue to Google"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

function statusLabel(mailbox: AlertMailbox): string {
  if (!mailbox.is_active) return "Paused";
  return mailbox.last_error ? "Failing" : "Active";
}

function statusTone(mailbox: AlertMailbox): "good" | "danger" | "neutral" {
  if (!mailbox.is_active) return "neutral";
  return mailbox.last_error ? "danger" : "good";
}

function MailboxRow({ mailbox }: { mailbox: AlertMailbox }) {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "mailboxes"] });

  const syncMutation = useMutation({
    mutationFn: () => adminApi.syncMailbox(mailbox.id),
    onSuccess: (result) => {
      if (result.status === "success") {
        toast.success(`${result.mailbox}: ${result.inserted} new job${result.inserted === 1 ? "" : "s"}`);
      } else {
        toast.error(`${result.mailbox}: ${result.error}`);
      }
      invalidate();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Sync failed"),
  });

  const toggleMutation = useMutation({
    mutationFn: () => adminApi.updateMailbox(mailbox.id, { is_active: !mailbox.is_active }),
    onSuccess: invalidate,
  });

  const deleteMutation = useMutation({
    mutationFn: () => adminApi.deleteMailbox(mailbox.id),
    onSuccess: () => {
      toast.success("Mailbox disconnected — the jobs it found stay in the pool");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't disconnect"),
  });

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <Badge tone="accent">{mailbox.market}</Badge>
            {/* A mailbox with a live auth error is not "Active", whatever its
                is_active flag says — a green badge over a revoked token is
                exactly how a market's feed dies unnoticed. */}
            <Badge tone={statusTone(mailbox)}>{statusLabel(mailbox)}</Badge>
            {mailbox.lanes.map((lane) => (
              <Badge key={lane} tone="neutral">
                {humanize(lane)}
              </Badge>
            ))}
          </div>
          <h3 className="truncate text-base font-semibold text-ink">{mailbox.label}</h3>
          <p className="truncate text-sm text-ink-muted">{mailbox.email_address}</p>
          <p className="mt-1 font-mono text-xs text-ink-faint">
            {mailbox.last_synced_at
              ? `Last synced ${formatDistanceToNow(new Date(mailbox.last_synced_at), { addSuffix: true })}`
              : "Never synced — runs daily at 07:10 UTC"}
          </p>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
            <RefreshCw className="h-3.5 w-3.5" />
            {syncMutation.isPending ? "Syncing…" : "Sync"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => toggleMutation.mutate()}>
            {mailbox.is_active ? "Pause" : "Resume"}
          </Button>
          <Button
            size="sm"
            variant="danger"
            onClick={() => deleteMutation.mutate()}
            disabled={deleteMutation.isPending}
            aria-label={`Disconnect ${mailbox.email_address}`}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {mailbox.last_error && (
        <p className="mt-3 flex items-start gap-2 rounded-lg border border-danger/25 bg-danger-soft px-3 py-2 text-sm text-danger">
          <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span className="min-w-0 break-words">{mailbox.last_error}</span>
        </p>
      )}
    </Card>
  );
}

export function MailboxesPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [connectOpen, setConnectOpen] = useState(false);

  const { data: mailboxes, isLoading } = useQuery({
    queryKey: ["admin", "mailboxes"],
    queryFn: adminApi.mailboxes,
  });

  useEffect(() => {
    const result = searchParams.get("mailbox");
    if (result === "connected") {
      toast.success("Mailbox connected — filters and label created in that inbox");
      queryClient.invalidateQueries({ queryKey: ["admin", "mailboxes"] });
    } else if (result === "error") {
      toast.error(searchParams.get("message") ?? "Couldn't connect that mailbox");
    }
    if (result) {
      searchParams.delete("mailbox");
      searchParams.delete("message");
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const syncAllMutation = useMutation({
    mutationFn: adminApi.syncAllMailboxes,
    onSuccess: (results) => {
      const inserted = results.reduce((sum, r) => sum + r.inserted, 0);
      const failed = results.filter((r) => r.status !== "success").length;
      toast[failed ? "warning" : "success"](
        `${inserted} new job${inserted === 1 ? "" : "s"} across ${results.length} mailbox${results.length === 1 ? "" : "es"}` +
          (failed ? ` — ${failed} failed` : "")
      );
      queryClient.invalidateQueries({ queryKey: ["admin", "mailboxes"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Sync failed"),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Supply"
        title="Alert mailboxes"
        description="Every user's feed is drawn from these. One mailbox per market, subscribed to that country's job alerts."
        action={
          <div className="flex items-center gap-2">
            {(mailboxes?.length ?? 0) > 0 && (
              <Button
                size="sm"
                variant="outline"
                onClick={() => syncAllMutation.mutate()}
                disabled={syncAllMutation.isPending}
              >
                <RefreshCw className="h-3.5 w-3.5" />
                {syncAllMutation.isPending ? "Syncing…" : "Sync all"}
              </Button>
            )}
            <Button size="sm" onClick={() => setConnectOpen(true)}>
              <Plus className="h-3.5 w-3.5" /> Connect mailbox
            </Button>
          </div>
        }
      />

      {isLoading ? (
        <PageSpinner />
      ) : !mailboxes || mailboxes.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No mailboxes yet</CardTitle>
            <CardDescription>
              Until one is connected, the feed only carries what the six public job-board sources return — nothing
              country-specific, and no market for users to pick at signup.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={Inbox}
              title="Connect your first market"
              description="Use a Google account already subscribed to that country's LinkedIn, Indeed or Glassdoor alerts."
              action={
                <Button size="sm" onClick={() => setConnectOpen(true)}>
                  <Plus className="h-3.5 w-3.5" /> Connect mailbox
                </Button>
              }
            />
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {mailboxes.map((mailbox) => (
            <MailboxRow key={mailbox.id} mailbox={mailbox} />
          ))}
        </div>
      )}

      <ConnectDialog open={connectOpen} onOpenChange={setConnectOpen} />
    </div>
  );
}
