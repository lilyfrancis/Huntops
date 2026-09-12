import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, MinusCircle, RefreshCw, TriangleAlert } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { adminApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { cn } from "@/lib/utils";
import type { IntegrationStatus } from "@/lib/types";

/* What each one actually powers, so "not configured" is a decision rather
   than a mystery. */
const INTEGRATIONS: Record<string, { title: string; powers: string; envVar: string }> = {
  anthropic: {
    title: "Anthropic",
    powers: "Fit scoring, job extraction from alert emails, mock interviews, outreach drafting",
    envVar: "ANTHROPIC_API_KEY",
  },
  apollo: {
    title: "Apollo",
    powers: "Finding a hiring contact for outreach. Without it, pitches are drafted but have nobody to go to.",
    envVar: "APOLLO_API_KEY",
  },
  smtp: {
    title: "Outbound email",
    powers: "The daily digest, and outreach sent on a user's behalf",
    envVar: "SMTP_HOST / SMTP_USERNAME / SMTP_PASSWORD",
  },
  whatsapp: {
    title: "WhatsApp",
    powers: "An alternative channel for the daily digest, for users who choose it over email",
    envVar: "WHATSAPP_PHONE_NUMBER_ID / WHATSAPP_ACCESS_TOKEN / WHATSAPP_TEMPLATE_NAME",
  },
  paystack: {
    title: "Paystack",
    powers: "Subscriptions. Without it nobody can move off the free tier.",
    envVar: "PAYSTACK_SECRET_KEY / PAYSTACK_PLAN_PRO / PAYSTACK_PLAN_ELITE",
  },
};

function StatusBadge({ status }: { status: IntegrationStatus }) {
  if (!status.configured) return <Badge tone="neutral">Not set up</Badge>;
  if (status.ok) return <Badge tone="good">Working</Badge>;
  return <Badge tone="danger">Failing</Badge>;
}

function Row({ status }: { status: IntegrationStatus }) {
  const queryClient = useQueryClient();
  const meta = INTEGRATIONS[status.name] ?? { title: status.name, powers: "", envVar: "" };

  const testMutation = useMutation({
    mutationFn: () => adminApi.testIntegration(status.name),
    onSuccess: (result) => {
      if (result.ok) toast.success(`${meta.title}: ${result.detail}`);
      else toast.error(`${meta.title}: ${result.detail}`, { duration: 14000 });
      queryClient.invalidateQueries({ queryKey: ["admin", "integrations"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Test failed"),
  });

  const Icon = !status.configured ? MinusCircle : status.ok ? Check : TriangleAlert;
  const tone = !status.configured ? "text-ink-faint" : status.ok ? "text-good" : "text-danger";

  return (
    <Card className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex min-w-0 gap-3">
          <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", tone)} strokeWidth={2} />
          <div className="min-w-0">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <h3 className="text-base font-semibold text-ink">{meta.title}</h3>
              <StatusBadge status={status} />
            </div>
            <p className="text-sm text-ink-muted">{meta.powers}</p>
            <p
              className={cn(
                "mt-2 break-words text-sm",
                status.configured && !status.ok ? "text-danger" : "text-ink-faint"
              )}
            >
              {status.detail}
            </p>
            {meta.envVar && (
              <p className="mt-2 font-mono text-xs text-ink-faint">
                Set in backend/.env — {meta.envVar}
              </p>
            )}
          </div>
        </div>

        <Button size="sm" variant="outline" onClick={() => testMutation.mutate()} disabled={testMutation.isPending}>
          <RefreshCw className="h-3.5 w-3.5" />
          {testMutation.isPending ? "Testing…" : "Test"}
        </Button>
      </div>
    </Card>
  );
}

export function AdminIntegrationsPage() {
  const { data: integrations, isLoading, refetch, isFetching } = useQuery({
    queryKey: ["admin", "integrations"],
    /* Not on a timer: each load makes a real call to every provider. */
    staleTime: Infinity,
    queryFn: adminApi.integrations,
  });

  return (
    <div>
      <PageHeader
        eyebrow="Configuration"
        title="Integrations"
        description="Each of these makes a real call to the provider. A key that is present but rejected looks identical to a working one until someone hits the feature — this is how you find out first."
        action={
          <Button size="sm" variant="outline" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className="h-3.5 w-3.5" />
            {isFetching ? "Checking…" : "Re-check all"}
          </Button>
        }
      />

      {isLoading ? (
        <PageSpinner />
      ) : (
        <div className="space-y-3">
          {(integrations ?? []).map((status) => (
            <Row key={status.name} status={status} />
          ))}
          <p className="pt-1 text-xs text-ink-faint">
            Keys live in <code className="font-mono">backend/.env</code> on the server, not in the
            database — after editing, recreate the containers with{" "}
            <code className="font-mono">docker compose -f docker-compose.prod.yml up -d api scheduler</code>.
            A plain restart keeps the old values.
          </p>
        </div>
      )}
    </div>
  );
}
