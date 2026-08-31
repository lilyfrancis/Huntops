import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { Mail, RefreshCw, Unplug } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { integrationsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";

export function IntegrationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();

  const { data: status, isLoading } = useQuery({
    queryKey: ["gmail", "status"],
    queryFn: integrationsApi.gmailStatus,
  });

  useEffect(() => {
    const gmailResult = searchParams.get("gmail");
    if (gmailResult === "connected") {
      toast.success("Gmail connected — routing rules are set up automatically");
      queryClient.invalidateQueries({ queryKey: ["gmail", "status"] });
    } else if (gmailResult === "error") {
      toast.error(searchParams.get("message") ?? "Couldn't connect Gmail");
    }
    if (gmailResult) {
      searchParams.delete("gmail");
      searchParams.delete("message");
      setSearchParams(searchParams, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const connectMutation = useMutation({
    mutationFn: integrationsApi.gmailConnect,
    onSuccess: (result) => {
      window.location.href = result.authorization_url;
    },
    onError: () => toast.error("Couldn't start Gmail connection"),
  });

  const disconnectMutation = useMutation({
    mutationFn: integrationsApi.gmailDisconnect,
    onSuccess: () => {
      toast.success("Gmail disconnected");
      queryClient.invalidateQueries({ queryKey: ["gmail", "status"] });
    },
  });

  const syncMutation = useMutation({
    mutationFn: integrationsApi.gmailSync,
    onSuccess: (result) => {
      toast.success(`Synced — ${result.inserted} new job${result.inserted === 1 ? "" : "s"} found`);
      queryClient.invalidateQueries({ queryKey: ["gmail", "status"] });
      queryClient.invalidateQueries({ queryKey: ["jobs"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Sync failed"),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Email-alert bridge"
        title="Gmail"
        description="Connect once — HuntOps mines your existing LinkedIn/Indeed/Glassdoor job alerts automatically."
      />

      {isLoading ? (
        <PageSpinner />
      ) : (
        <Card className="max-w-lg">
          <CardHeader className="flex-row items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2">
                <Mail className="h-4 w-4 text-ink-muted" />
              </div>
              <div>
                <CardTitle>Gmail</CardTitle>
                <CardDescription>Reads only what's labeled "HuntOps"</CardDescription>
              </div>
            </div>
            <Badge tone={status?.connected ? "good" : "neutral"}>{status?.connected ? "Connected" : "Not connected"}</Badge>
          </CardHeader>
          <CardContent>
            {status?.connected ? (
              <p className="text-sm text-ink-muted">
                Last synced{" "}
                {status.last_synced_at
                  ? formatDistanceToNow(new Date(status.last_synced_at), { addSuffix: true })
                  : "never — runs daily at 07:10 UTC, or trigger one now"}
                .
              </p>
            ) : (
              <p className="text-sm text-ink-muted">
                Connecting creates a "HuntOps" label and routing filters in your Gmail automatically — nothing to set
                up by hand.
              </p>
            )}
          </CardContent>
          <CardFooter>
            {status?.connected ? (
              <>
                <Button size="sm" onClick={() => syncMutation.mutate()} disabled={syncMutation.isPending}>
                  <RefreshCw className="h-3.5 w-3.5" />
                  {syncMutation.isPending ? "Syncing…" : "Sync now"}
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => disconnectMutation.mutate()}
                  disabled={disconnectMutation.isPending}
                >
                  <Unplug className="h-3.5 w-3.5" /> Disconnect
                </Button>
              </>
            ) : (
              <Button size="sm" onClick={() => connectMutation.mutate()} disabled={connectMutation.isPending}>
                {connectMutation.isPending ? "Redirecting…" : "Connect Gmail"}
              </Button>
            )}
          </CardFooter>
        </Card>
      )}
    </div>
  );
}
