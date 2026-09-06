import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/hooks/use-auth";
import { authApi } from "@/lib/api";
import { billingApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";

interface ProfileFormValues {
  full_name: string;
  home_market: string;
  positioning_statement: string;
}

/* Names and blurbs only. The price is served with the plan, because the real
   figure lives on the Paystack plan and a copy in here would eventually
   disagree with what the card is actually charged. */
const TIER_COPY: Record<"pro" | "elite", { name: string; blurb: string }> = {
  pro: { name: "Pro", blurb: "Geo-aware matching, interview practice, negotiation coach, 100 credits" },
  elite: { name: "Elite", blurb: "Everything in Pro + Autopilot, 500 credits" },
};

/* Ordered cheapest-first so a plan can be compared against the current one.
   Labelling a downgrade "Upgrade to Pro" — which is what an Elite user saw —
   is the kind of wrong word that makes someone distrust the whole page. */
const TIER_RANK: Record<string, number> = { free: 0, pro: 1, elite: 2 };

function formatPrice(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: amount % 1 === 0 ? 0 : 2,
    }).format(amount);
  } catch {
    // An unrecognised currency code throws rather than degrading, and a
    // pricing card that crashes the page is worse than an unstyled number.
    return `${amount.toLocaleString()} ${currency}`;
  }
}

export function ProfilePage() {
  const { user, setUser, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();

  const { data: billing } = useQuery({ queryKey: ["billing", "status"], queryFn: billingApi.status });

  /* Paystack redirects here after payment. The redirect proves nothing — a
     user could type this URL — so entitlement waits for the signed webhook,
     and all this does is say so and re-check shortly. */
  useEffect(() => {
    if (searchParams.get("billing") !== "processing") return;
    toast.success("Payment received — your plan will activate in a moment");
    const timer = setTimeout(() => {
      refreshUser();
      queryClient.invalidateQueries({ queryKey: ["billing", "status"] });
    }, 4000);
    searchParams.delete("billing");
    setSearchParams(searchParams, { replace: true });
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const { register, handleSubmit, formState: { isSubmitting, isDirty } } = useForm<ProfileFormValues>({
    defaultValues: {
      full_name: user?.full_name ?? "",
      home_market: user?.home_market ?? "",
      positioning_statement: user?.positioning_statement ?? "",
    },
  });

  const onSubmit = async (values: ProfileFormValues) => {
    try {
      const updated = await authApi.updateProfile(values);
      setUser(updated);
      toast.success("Profile updated");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Couldn't save");
    }
  };

  const checkoutMutation = useMutation({
    mutationFn: (tier: "pro" | "elite") => billingApi.checkoutSession(tier),
    onSuccess: (result) => {
      window.location.href = result.checkout_url;
    },
    onError: () => toast.error("Couldn't start checkout — billing may not be configured yet"),
  });

  const cancelMutation = useMutation({
    mutationFn: billingApi.cancel,
    onSuccess: () => {
      toast.success("Subscription cancelled — you keep your plan until the period you've paid for ends");
      queryClient.invalidateQueries({ queryKey: ["billing", "status"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't cancel"),
  });

  const portalMutation = useMutation({
    mutationFn: billingApi.portal,
    onSuccess: (result) => {
      window.location.href = result.portal_url;
    },
    onError: () => toast.error("Couldn't open billing portal"),
  });

  if (!user) return null;

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Account" title="Profile" description="How HuntOps scores and pitches on your behalf." />

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
          <CardDescription>Home market drives the geo-fit boost; positioning steers outreach tone.</CardDescription>
        </CardHeader>
        <form onSubmit={handleSubmit(onSubmit)}>
          <CardContent className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="full_name">Full name</Label>
              <Input id="full_name" {...register("full_name")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="home_market">Home market</Label>
              <Input id="home_market" placeholder="e.g. Nigeria, Philippines" {...register("home_market")} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="positioning_statement">Positioning statement (optional)</Label>
              <Textarea
                id="positioning_statement"
                placeholder="e.g. pivoting from sales into RevOps"
                rows={2}
                {...register("positioning_statement")}
              />
            </div>
          </CardContent>
          <CardFooter>
            <Button type="submit" size="sm" disabled={isSubmitting || !isDirty}>
              {isSubmitting ? "Saving…" : "Save changes"}
            </Button>
          </CardFooter>
        </form>
      </Card>

      <Card>
        <CardHeader className="flex-row items-center justify-between">
          <div>
            <CardTitle>Billing</CardTitle>
            <CardDescription>{user.ai_credits} credits remaining</CardDescription>
          </div>
          <Badge tone={user.subscription_tier === "elite" ? "accent" : "neutral"}>{user.subscription_tier}</Badge>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          {(billing?.plans ?? []).map((plan) => {
            const copy = TIER_COPY[plan.tier as "pro" | "elite"];
            if (!copy) return null;
            const isCurrent = user.subscription_tier === plan.tier;
            return (
              <div key={plan.tier} className="rounded-lg border border-border bg-surface-2 p-4">
                <div className="mb-1 flex items-baseline justify-between">
                  <span className="font-mono text-sm font-semibold text-ink">{copy.name}</span>
                  <span className="font-mono text-sm text-accent-strong">
                    {formatPrice(plan.price, plan.currency)}/mo
                  </span>
                </div>
                <p className="mb-3 text-xs text-ink-muted">{copy.blurb}</p>
                <Button
                  size="sm"
                  variant={isCurrent ? "outline" : "solid"}
                  className="w-full"
                  disabled={isCurrent || !plan.available || checkoutMutation.isPending}
                  onClick={() => checkoutMutation.mutate(plan.tier as "pro" | "elite")}
                >
                  {isCurrent
                    ? "Current plan"
                    : !plan.available
                      ? "Not available yet"
                      : TIER_RANK[plan.tier] > TIER_RANK[user.subscription_tier]
                        ? `Upgrade to ${copy.name}`
                        : `Switch to ${copy.name}`}
                </Button>
              </div>
            );
          })}
        </CardContent>
        {/* Keyed on the subscription, not the tier: someone who cancelled is
            still on their paid tier until the period ends, but has nothing
            left to manage or cancel. */}
        {billing?.has_subscription && (
          <CardFooter>
            <Button size="sm" variant="outline" onClick={() => portalMutation.mutate()} disabled={portalMutation.isPending}>
              Update card
            </Button>
            <Button size="sm" variant="danger" onClick={() => cancelMutation.mutate()} disabled={cancelMutation.isPending}>
              {cancelMutation.isPending ? "Cancelling…" : "Cancel subscription"}
            </Button>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}
