import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Wallet as WalletIcon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { billingApi, applicationsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";
import type { CreditPack } from "@/lib/types";

/** Roughly what a balance buys, in the thing people came here for.
 *
 * A number on its own is not information — nobody knows whether 240 is a
 * lot. What they want to know is how many jobs they can still act on.
 */
function inApplications(credits: number, costPerApply: number): string {
  const n = Math.floor(credits / costPerApply);
  if (n === 0) return "not enough for an application";
  return `about ${n} application${n === 1 ? "" : "s"}`;
}

function money(pack: CreditPack): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency: pack.currency,
      maximumFractionDigits: 0,
    }).format(pack.price);
  } catch {
    // An unrecognised currency code should cost a symbol, not the dialog.
    return `${pack.currency} ${pack.price.toLocaleString()}`;
  }
}

interface WalletProps {
  /** "sidebar" is the full-width block in the nav; "compact" is the pill in
      the mobile top bar, where there is room for a number and nothing else. */
  variant?: "sidebar" | "compact";
}

export function Wallet({ variant = "sidebar" }: WalletProps) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);

  // Prices come from the server, and only when the wallet is opened — this
  // sits in the sidebar of every page and does not need to fetch on each.
  const { data: packs } = useQuery({
    queryKey: ["billing", "credit-packs"],
    queryFn: billingApi.creditPacks,
    enabled: open,
  });
  const { data: costs } = useQuery({
    queryKey: ["concierge", "allowance"],
    queryFn: applicationsApi.conciergeAllowance,
    enabled: open,
  });

  const buy = useMutation({
    mutationFn: (code: string) => billingApi.buyCredits(code),
    onSuccess: ({ checkout_url }) => {
      window.location.href = checkout_url;
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start checkout"),
  });

  if (!user || user.role !== "job_seeker") return null;

  const applyCost = costs?.credit_cost ?? 15;
  const unlockCost = costs?.unlock_credit_cost ?? 5;
  const best = packs?.length
    ? packs.reduce((a, b) => (a.price / a.credits <= b.price / b.credits ? a : b))
    : null;

  return (
    <>
      {variant === "compact" ? (
        <button
          onClick={() => setOpen(true)}
          className="flex items-center gap-1.5 rounded-full border border-border bg-surface-2 px-2.5 py-1.5 text-sm font-semibold text-violet-dark transition-colors hover:bg-surface-3"
          aria-label={`${user.ai_credits} credits — open wallet`}
        >
          <WalletIcon className="h-4 w-4" strokeWidth={2} />
          {user.ai_credits}
        </button>
      ) : (
        <button
          onClick={() => setOpen(true)}
          className="w-full rounded-lg bg-surface-2 px-3 py-2 text-left transition-colors hover:bg-surface-3"
        >
          <div className="flex items-center justify-between">
            <span className="text-[0.7rem] font-semibold uppercase tracking-wide text-ink-faint">Credits</span>
            <span className="text-sm font-bold text-violet-dark">{user.ai_credits}</span>
          </div>
          <p className="mt-0.5 text-[0.7rem] text-ink-faint">Tap to top up</p>
        </button>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg">
          <DialogTitle>Your credits</DialogTitle>
          <DialogDescription>
            Credits are how you act on a job: {unlockCost} to see one in full, {applyCost} to have us
            apply for you. Nothing expires.
          </DialogDescription>

          <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-2 p-4">
            <WalletIcon className="h-5 w-5 shrink-0 text-violet" />
            <div>
              <p className="text-2xl font-bold text-ink">{user.ai_credits}</p>
              <p className="text-xs text-ink-muted">{inApplications(user.ai_credits, applyCost)} left</p>
            </div>
          </div>

          <div className="mt-2 space-y-2">
            {(packs ?? []).map((pack) => (
              <button
                key={pack.code}
                onClick={() => buy.mutate(pack.code)}
                disabled={buy.isPending}
                className="flex w-full items-center justify-between gap-3 rounded-xl border border-border bg-white p-3 text-left transition-colors hover:border-violet disabled:opacity-60"
              >
                <div className="min-w-0">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
                    {pack.credits.toLocaleString()} credits
                    {best?.code === pack.code && <Badge tone="good">Best value</Badge>}
                  </p>
                  <p className="text-xs text-ink-muted">{inApplications(pack.credits, applyCost)}</p>
                </div>
                <span className="shrink-0 text-sm font-bold text-ink">{money(pack)}</span>
              </button>
            ))}
            {open && !packs && <p className="text-sm text-ink-faint">Loading packs…</p>}
          </div>

          <p className="mt-3 text-xs text-ink-faint">
            A plan gives you credits every month at a better rate than buying a pack at a time.{" "}
            <a href="/app/profile" className="text-violet underline">
              See plans
            </a>
          </p>
        </DialogContent>
      </Dialog>
    </>
  );
}
