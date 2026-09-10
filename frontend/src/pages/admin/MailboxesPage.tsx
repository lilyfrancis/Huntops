import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { Check, Inbox, Plus, RefreshCw, Trash2, TriangleAlert, Wifi } from "lucide-react";
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
import { cn } from "@/lib/utils";
import type { AlertMailbox, JobLane } from "@/lib/types";

/* Saves the operator looking up settings for the hosts they're most likely
   to use. Not exhaustive, and the fields stay editable. */
const HOST_PRESETS: { label: string; host: string; port: number }[] = [
  // Hostinger sells two different mail products and they have different IMAP
  // hosts. hPanel → Emails → Configuration settings shows which one an
  // account is on; guessing wrong just fails the connection test.
  { label: "Hostinger Email", host: "imap.hostinger.com", port: 993 },
  { label: "Hostinger (Titan)", host: "imap.titan.email", port: 993 },
  { label: "Zoho", host: "imap.zoho.com", port: 993 },
  // The region is part of the hostname and must match where the WorkMail
  // organisation was created — not where the app is hosted. Edit it below.
  { label: "Amazon WorkMail", host: "imap.mail.eu-west-1.awsapps.com", port: 993 },
  { label: "Gmail / Workspace", host: "imap.gmail.com", port: 993 },
  { label: "Outlook / Microsoft 365", host: "outlook.office365.com", port: 993 },
  { label: "Fastmail", host: "imap.fastmail.com", port: 993 },
];

interface FormState {
  email_address: string;
  market: string;
  label: string;
  imap_host: string;
  imap_port: string;
  imap_username: string;
  imap_password: string;
  imap_folder: string;
  lanes: string[];
}

const EMPTY_FORM: FormState = {
  email_address: "",
  market: "",
  label: "",
  imap_host: "",
  imap_port: "993",
  imap_username: "",
  imap_password: "",
  imap_folder: "INBOX",
  lanes: [],
};

function AddDialog({
  open,
  onOpenChange,
  existing,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  existing: AlertMailbox | null;
}) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<FormState>(
    existing
      ? {
          email_address: existing.email_address,
          market: existing.market,
          label: existing.label,
          imap_host: existing.imap_host,
          imap_port: String(existing.imap_port),
          imap_username: existing.imap_username,
          imap_password: "",
          imap_folder: existing.imap_folder,
          lanes: existing.lanes,
        }
      : EMPTY_FORM
  );

  const { data: options } = useQuery({ queryKey: ["preference-options"], queryFn: preferencesApi.options });
  const set = (patch: Partial<FormState>) => setForm((f) => ({ ...f, ...patch }));

  const saveMutation = useMutation({
    mutationFn: () =>
      adminApi.upsertMailbox({
        email_address: form.email_address.trim(),
        market: form.market.trim(),
        imap_host: form.imap_host.trim(),
        imap_port: Number(form.imap_port) || 993,
        imap_username: form.imap_username.trim() || undefined,
        imap_password: form.imap_password || undefined,
        imap_folder: form.imap_folder.trim() || "INBOX",
        label: form.label.trim() || undefined,
        lanes: form.lanes as JobLane[],
      }),
    onSuccess: async (mailbox) => {
      queryClient.invalidateQueries({ queryKey: ["admin", "mailboxes"] });
      onOpenChange(false);

      /* Test straight after saving rather than making it a separate step:
         a wrong password found now is a fix, found tomorrow it's an empty feed. */
      try {
        const result = await adminApi.testMailbox(mailbox.id);
        if (result.ok) toast.success(`${mailbox.email_address} connected`);
        else toast.error(result.detail, { duration: 12000 });
      } catch {
        toast.success("Mailbox saved — use Test to check the connection");
      }
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't save the mailbox"),
  });

  const canSave =
    form.email_address.trim() &&
    form.market.trim() &&
    form.imap_host.trim() &&
    (existing || form.imap_password);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] max-w-lg flex-col overflow-hidden">
        <DialogTitle>{existing ? "Edit mailbox" : "Add an alert mailbox"}</DialogTitle>

        <div className="-mx-6 mt-4 flex-1 space-y-5 overflow-y-auto px-6">
          <p className="text-sm text-ink-muted">
            A mailbox you own that receives this market's job alerts. HuntOps reads it over IMAP —
            no OAuth, no consent screen, and it works with any provider.
          </p>
          {/* Asked more than once: a send-only relay looks like "our email
              provider" and gets tried here, where it cannot work. */}
          <p className="rounded-lg border border-border bg-surface-2 px-3 py-2 text-xs text-ink-muted">
            This must be somewhere you can <strong className="font-semibold text-ink">log in and read
            mail</strong>. A send-only relay — Amazon SES, SendGrid, Postmark — cannot be used here:
            those deliver outbound mail, they do not store an inbox. Use one for the digest and
            outreach instead, via <code className="font-mono">SMTP_*</code>.
          </p>

          <div className="space-y-1.5">
            <Label htmlFor="email_address">Mailbox address</Label>
            <Input
              id="email_address"
              type="email"
              placeholder="e.g. alerts-canada@huntops.site"
              value={form.email_address}
              disabled={!!existing}
              onChange={(e) =>
                set({
                  email_address: e.target.value,
                  // Most hosts log in with the full address; still editable below.
                  imap_username: form.imap_username || "",
                })
              }
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="market">Market</Label>
            <Input
              id="market"
              placeholder="e.g. Canada"
              value={form.market}
              onChange={(e) => set({ market: e.target.value })}
            />
            <p className="text-xs text-ink-faint">
              Every job from this mailbox is tagged with it, and this is exactly what users pick at
              signup — so keep the spelling consistent.
            </p>
          </div>

          <div className="space-y-2">
            <Label>Mail host</Label>
            <div className="flex flex-wrap gap-1.5">
              {HOST_PRESETS.map((preset) => (
                <button
                  key={preset.host}
                  type="button"
                  onClick={() => set({ imap_host: preset.host, imap_port: String(preset.port) })}
                  className={cn(
                    "rounded-full border px-2.5 py-1 text-xs font-medium transition-colors",
                    form.imap_host === preset.host
                      ? "border-violet bg-violet-soft text-violet-dark"
                      : "border-border-strong bg-surface text-ink-muted hover:border-ink-faint hover:text-ink"
                  )}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="grid grid-cols-[1fr_5rem] gap-2">
              <Input
                aria-label="IMAP host"
                placeholder="e.g. imap.example.com"
                value={form.imap_host}
                onChange={(e) => set({ imap_host: e.target.value })}
              />
              <Input
                aria-label="IMAP port"
                inputMode="numeric"
                value={form.imap_port}
                onChange={(e) => set({ imap_port: e.target.value })}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="imap_username">Username</Label>
            <Input
              id="imap_username"
              placeholder={form.email_address ? `e.g. ${form.email_address}` : "usually the full address"}
              value={form.imap_username}
              onChange={(e) => set({ imap_username: e.target.value })}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="imap_password">{existing ? "New password (leave blank to keep)" : "Password"}</Label>
            <Input
              id="imap_password"
              type="password"
              autoComplete="new-password"
              value={form.imap_password}
              onChange={(e) => set({ imap_password: e.target.value })}
            />
            <p className="text-xs text-ink-faint">
              If the mailbox has two-factor authentication, this must be an{" "}
              <strong className="font-semibold text-ink-muted">app password</strong>, not the
              account password. Stored encrypted and never shown again.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="imap_folder">Folder</Label>
            <Input
              id="imap_folder"
              value={form.imap_folder}
              onChange={(e) => set({ imap_folder: e.target.value })}
            />
            <p className="text-xs text-ink-faint">
              Leave as INBOX unless you filter alerts into a folder of their own.
            </p>
          </div>

          <div className="space-y-2">
            <Label>Job families this mailbox covers (optional)</Label>
            <ChipGroup
              aria-label="Mailbox job families"
              options={(options?.lanes ?? []).map((l) => ({ value: l, label: humanize(l) }))}
              value={form.lanes}
              onChange={(lanes) => set({ lanes })}
            />
            <p className="text-xs text-ink-faint">
              Used only when a job's own title gives nothing away — the listing always wins when it
              does.
            </p>
          </div>

        </div>

        <div className="-mx-6 -mb-6 mt-4 border-t border-border bg-surface px-6 py-4">
          <Button
            className="w-full"
            onClick={() => saveMutation.mutate()}
            disabled={!canSave || saveMutation.isPending}
          >
            {saveMutation.isPending ? "Saving and testing…" : existing ? "Save changes" : "Add and test"}
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

function MailboxRow({ mailbox, onEdit }: { mailbox: AlertMailbox; onEdit: () => void }) {
  const queryClient = useQueryClient();
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "mailboxes"] });

  const testMutation = useMutation({
    mutationFn: () => adminApi.testMailbox(mailbox.id),
    onSuccess: (result) =>
      result.ok ? toast.success(result.detail) : toast.error(result.detail, { duration: 12000 }),
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Test failed"),
  });

  const syncMutation = useMutation({
    mutationFn: () => adminApi.syncMailbox(mailbox.id),
    onSuccess: (result) => {
      if (result.status === "success") {
        toast.success(`${result.mailbox}: ${result.inserted} new job${result.inserted === 1 ? "" : "s"}`);
      } else {
        toast.error(`${result.mailbox}: ${result.error}`, { duration: 12000 });
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
      toast.success("Mailbox removed — the jobs it found stay in the pool");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't remove it"),
  });

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <button type="button" onClick={onEdit} className="min-w-0 text-left">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            <Badge tone="accent">{mailbox.market}</Badge>
            {/* A mailbox with a live error is not "Active", whatever its
                is_active flag says — a green badge over a failed login is
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
          <p className="mt-1 truncate font-mono text-xs text-ink-faint">
            {mailbox.imap_host}:{mailbox.imap_port} · {mailbox.imap_folder} ·{" "}
            {mailbox.last_synced_at
              ? `synced ${formatDistanceToNow(new Date(mailbox.last_synced_at), { addSuffix: true })}`
              : "never synced — runs daily at 07:10 UTC"}
          </p>
        </button>

        <div className="flex shrink-0 flex-wrap items-center gap-2">
          <Button size="sm" variant="ghost" onClick={() => testMutation.mutate()} disabled={testMutation.isPending}>
            <Wifi className="h-3.5 w-3.5" />
            {testMutation.isPending ? "Testing…" : "Test"}
          </Button>
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
            aria-label={`Remove ${mailbox.email_address}`}
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
  const [dialog, setDialog] = useState<{ open: boolean; editing: AlertMailbox | null }>({
    open: false,
    editing: null,
  });

  const { data: mailboxes, isLoading } = useQuery({
    queryKey: ["admin", "mailboxes"],
    queryFn: adminApi.mailboxes,
  });

  const syncAllMutation = useMutation({
    mutationFn: adminApi.syncAllMailboxes,
    onSuccess: (results) => {
      const inserted = results.reduce((sum, r) => sum + r.inserted, 0);
      const failed = results.filter((r) => r.status !== "success").length;
      const message =
        `${inserted} new job${inserted === 1 ? "" : "s"} across ${results.length} mailbox` +
        `${results.length === 1 ? "" : "es"}${failed ? ` — ${failed} failed` : ""}`;
      failed ? toast.warning(message) : toast.success(message);
      queryClient.invalidateQueries({ queryKey: ["admin", "mailboxes"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Sync failed"),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Supply"
        title="Alert mailboxes"
        description="Every user's feed is drawn from these. One mailbox per market, subscribed to that country's job alerts, read over IMAP."
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
            <Button size="sm" onClick={() => setDialog({ open: true, editing: null })}>
              <Plus className="h-3.5 w-3.5" /> Add mailbox
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
              Until one is added, the feed only carries what the public job-board sources return —
              nothing country-specific, and no market for users to pick at signup.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <EmptyState
              icon={Inbox}
              title="Add your first market"
              description="Create a mailbox on your domain, subscribe it to that country's LinkedIn, Indeed or Glassdoor alerts, then point HuntOps at it."
              action={
                <Button size="sm" onClick={() => setDialog({ open: true, editing: null })}>
                  <Plus className="h-3.5 w-3.5" /> Add mailbox
                </Button>
              }
            />
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {mailboxes.map((mailbox) => (
            <MailboxRow
              key={mailbox.id}
              mailbox={mailbox}
              onEdit={() => setDialog({ open: true, editing: mailbox })}
            />
          ))}
          <p className="flex items-center gap-1.5 pt-1 text-xs text-ink-faint">
            <Check className="h-3 w-3" /> Passwords are encrypted at rest and never sent back to
            this page.
          </p>
        </div>
      )}

      {/* Keyed so switching between add and edit remounts with fresh state
          rather than showing the previous mailbox's values. */}
      {dialog.open && (
        <AddDialog
          key={dialog.editing?.id ?? "new"}
          open
          onOpenChange={(v) => setDialog({ open: v, editing: v ? dialog.editing : null })}
          existing={dialog.editing}
        />
      )}
    </div>
  );
}
