import { useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { Mail, Unplug } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { integrationsApi } from "@/lib/api";
import { useAuth } from "@/hooks/use-auth";

export function IntegrationsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const { data: status, isLoading } = useQuery({
    queryKey: ["gmail", "status"],
    queryFn: integrationsApi.gmailStatus,
  });

  useEffect(() => {
    const gmailResult = searchParams.get("gmail");
    if (gmailResult === "connected") {
      toast.success("Gmail connected — outreach will send from your address");
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
      toast.success("Gmail disconnected — outreach will send from HuntOps instead");
      queryClient.invalidateQueries({ queryKey: ["gmail", "status"] });
    },
  });

  return (
    <div>
      <PageHeader
        eyebrow="Optional"
        title="Send outreach from your own Gmail"
        description="Your job feed doesn't need this — we run the alert mailboxes for you. This only changes who your outreach appears to come from."
      />

      {isLoading ? (
        <PageSpinner />
      ) : !status?.available && !status?.connected ? (
        /* The feature is switched off, so there is no button to press. Say
           what happens instead, rather than leaving a page that looks broken. */
        <Card className="max-w-lg">
          <CardHeader>
            <CardTitle>Not available</CardTitle>
            <CardDescription>Nothing is missing from your account</CardDescription>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-ink-muted">
              Outreach is sent for you from HuntOps with{" "}
              <span className="font-medium text-ink">{user?.email}</span> as the reply-to address,
              so anyone who replies reaches you directly. Sending from your own Gmail instead isn't
              offered right now.
            </p>
          </CardContent>
        </Card>
      ) : (
        <Card className="max-w-lg">
          <CardHeader className="flex-row items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-surface-2">
                <Mail className="h-4 w-4 text-ink-muted" />
              </div>
              <div>
                <CardTitle>Gmail</CardTitle>
                <CardDescription>Send permission only — we never read your mail</CardDescription>
              </div>
            </div>
            <Badge tone={status?.connected ? "good" : "neutral"}>
              {status?.connected ? "Connected" : "Not connected"}
            </Badge>
          </CardHeader>
          <CardContent>
            {status?.connected ? (
              <p className="text-sm text-ink-muted">
                Outreach sends from your address, and replies land in your inbox. Connected{" "}
                {status.connected_at
                  ? formatDistanceToNow(new Date(status.connected_at), { addSuffix: true })
                  : "recently"}
                .
              </p>
            ) : (
              <p className="text-sm text-ink-muted">
                Right now outreach sends from HuntOps with{" "}
                <span className="font-medium text-ink">{user?.email}</span> as the reply-to address, so replies still
                reach you. Connecting Gmail sends it from your own address instead, which tends to get better
                response rates.
              </p>
            )}
          </CardContent>
          <CardFooter>
            {status?.connected ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() => disconnectMutation.mutate()}
                disabled={disconnectMutation.isPending}
              >
                <Unplug className="h-3.5 w-3.5" /> Disconnect
              </Button>
            ) : !status?.available ? null : (
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
