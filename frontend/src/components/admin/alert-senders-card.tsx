import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { AlertSender } from "@/lib/types";

/**
 * The domains whose mail counts as a job alert.
 *
 * Editable here rather than in config because opening a market means meeting
 * boards nobody anticipated, and a missing one is a board whose alerts are
 * silently discarded. Mailboxes report the domains they skipped, so the fix
 * and the diagnosis live on the same screen.
 */
export function AlertSendersCard() {
  const queryClient = useQueryClient();
  const [domain, setDomain] = useState("");
  const [note, setNote] = useState("");

  const { data: senders } = useQuery({ queryKey: ["admin", "alert-senders"], queryFn: adminApi.alertSenders });
  const invalidate = () => queryClient.invalidateQueries({ queryKey: ["admin", "alert-senders"] });

  const addMutation = useMutation({
    mutationFn: () => adminApi.addAlertSender(domain.trim(), note.trim() || undefined),
    onSuccess: (sender) => {
      toast.success(`${sender.domain} will be read from the next sync`);
      setDomain("");
      setNote("");
      invalidate();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't add that domain"),
  });

  const removeMutation = useMutation({
    mutationFn: (id: string) => adminApi.deleteAlertSender(id),
    onSuccess: invalidate,
  });

  /* Grouped by the free-text note, which is the only thing keeping a list of
     thirty domains across six markets readable. */
  const grouped = (senders ?? []).reduce<Record<string, AlertSender[]>>((acc, sender) => {
    const key = sender.note || "Other";
    (acc[key] ??= []).push(sender);
    return acc;
  }, {});

  return (
    <Card>
      <CardHeader>
        <CardTitle>Alert senders</CardTitle>
        <CardDescription>
          Mail from anything not listed is skipped without costing an AI call — which also means a
          board that is missing here has its alerts quietly discarded. Subdomains match
          automatically. Changes apply from the next sync; no redeploy.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-48 flex-1 space-y-1.5">
            <label htmlFor="sender-domain" className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
              Domain
            </label>
            <Input
              id="sender-domain"
              placeholder="e.g. bayt.com"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && domain.trim() && addMutation.mutate()}
            />
          </div>
          <div className="w-32 space-y-1.5">
            <label htmlFor="sender-note" className="text-xs font-semibold uppercase tracking-wide text-ink-faint">
              Market
            </label>
            <Input
              id="sender-note"
              placeholder="e.g. Gulf"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && domain.trim() && addMutation.mutate()}
            />
          </div>
          <Button size="md" onClick={() => addMutation.mutate()} disabled={!domain.trim() || addMutation.isPending}>
            <Plus className="h-3.5 w-3.5" /> Add
          </Button>
        </div>

        <div className="space-y-3">
          {Object.entries(grouped).map(([group, items]) => (
            <div key={group}>
              <p className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-ink-faint">{group}</p>
              <div className="flex flex-wrap gap-1.5">
                {items.map((sender) => (
                  <span
                    key={sender.id}
                    className="inline-flex items-center gap-1.5 rounded-full border border-border-strong bg-surface-2 px-2.5 py-1 font-mono text-xs text-ink-muted"
                  >
                    {sender.domain}
                    <button
                      type="button"
                      onClick={() => removeMutation.mutate(sender.id)}
                      aria-label={`Remove ${sender.domain}`}
                      className="rounded-full p-0.5 transition-colors hover:bg-danger-soft hover:text-danger"
                    >
                      <X className="h-3 w-3" strokeWidth={2.5} />
                    </button>
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
