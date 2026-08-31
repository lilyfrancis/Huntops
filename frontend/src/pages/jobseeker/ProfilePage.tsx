import { useForm } from "react-hook-form";
import { useMutation } from "@tanstack/react-query";
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

const TIERS: { id: "pro" | "elite"; name: string; price: string; blurb: string }[] = [
  { id: "pro", name: "Pro", price: "$24/mo", blurb: "Geo-aware matching, email-alert bridge, 100 credits" },
  { id: "elite", name: "Elite", price: "$89/mo", blurb: "Everything in Pro + Autopilot Outreach, 500 credits" },
];

export function ProfilePage() {
  const { user, setUser } = useAuth();

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
          {TIERS.map((tier) => (
            <div key={tier.id} className="rounded-lg border border-border bg-surface-2 p-4">
              <div className="mb-1 flex items-baseline justify-between">
                <span className="font-mono text-sm font-semibold text-ink">{tier.name}</span>
                <span className="font-mono text-sm text-accent-strong">{tier.price}</span>
              </div>
              <p className="mb-3 text-xs text-ink-muted">{tier.blurb}</p>
              <Button
                size="sm"
                variant={user.subscription_tier === tier.id ? "outline" : "solid"}
                className="w-full"
                disabled={user.subscription_tier === tier.id || checkoutMutation.isPending}
                onClick={() => checkoutMutation.mutate(tier.id)}
              >
                {user.subscription_tier === tier.id ? "Current plan" : `Upgrade to ${tier.name}`}
              </Button>
            </div>
          ))}
        </CardContent>
        {user.subscription_tier !== "free" && (
          <CardFooter>
            <Button size="sm" variant="outline" onClick={() => portalMutation.mutate()} disabled={portalMutation.isPending}>
              Manage billing
            </Button>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}
