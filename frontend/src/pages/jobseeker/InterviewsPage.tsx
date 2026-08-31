import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { MessageSquare, Play, Sparkles } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { InterviewRoom } from "@/components/interviews/interview-room";
import { interviewsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { useAuth } from "@/hooks/use-auth";

export function InterviewsPage() {
  const { user, refreshUser } = useAuth();
  const queryClient = useQueryClient();
  const [roleTitle, setRoleTitle] = useState("");
  const [activeId, setActiveId] = useState<string | null>(null);

  const { data: sessions, isLoading } = useQuery({
    queryKey: ["interviews", "mine"],
    queryFn: interviewsApi.mine,
  });

  const startMutation = useMutation({
    mutationFn: () => interviewsApi.start({ role_title: roleTitle.trim() }),
    onSuccess: (session) => {
      toast.success("Interview ready — good luck");
      setRoleTitle("");
      setActiveId(session.id);
      queryClient.invalidateQueries({ queryKey: ["interviews", "mine"] });
      void refreshUser();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't start the interview"),
  });

  if (activeId) {
    return <InterviewRoom sessionId={activeId} onExit={() => setActiveId(null)} />;
  }

  const isFree = user?.subscription_tier === "free";

  return (
    <div>
      <PageHeader
        eyebrow="Practice"
        title="Mock interview"
        description="A real screening interview for the role you're chasing, graded answer by answer."
      />

      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-accent" /> Start a new interview
          </CardTitle>
        </CardHeader>
        <CardContent>
          {isFree ? (
            <p className="text-sm text-ink-muted">
              Mock interviews are available on Pro and Elite. Upgrade to practise before the real thing.
            </p>
          ) : (
            <div className="flex flex-col gap-3 sm:flex-row">
              <Input
                placeholder="Role you're interviewing for — e.g. Senior RevOps Manager"
                value={roleTitle}
                onChange={(e) => setRoleTitle(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && roleTitle.trim()) startMutation.mutate();
                }}
              />
              <Button
                onClick={() => startMutation.mutate()}
                disabled={!roleTitle.trim() || startMutation.isPending}
              >
                <Play className="h-3.5 w-3.5" />
                {startMutation.isPending ? "Preparing…" : "Start interview"}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {isLoading ? (
        <PageSpinner />
      ) : !sessions || sessions.length === 0 ? (
        <EmptyState
          icon={MessageSquare}
          title="No interviews yet"
          description="Start one above — you'll get five role-specific questions and feedback on every answer."
        />
      ) : (
        <div className="space-y-3">
          {sessions.map((session) => (
            <Card
              key={session.id}
              onClick={() => setActiveId(session.id)}
              role="button"
              className="cursor-pointer p-4 transition-colors hover:border-border-strong"
            >
              <div className="flex items-center justify-between gap-4">
                <div className="min-w-0">
                  <div className="mb-1 flex items-center gap-2">
                    <Badge tone={session.status === "completed" ? "good" : "accent"}>
                      {session.status === "completed" ? "Completed" : "In progress"}
                    </Badge>
                    {session.average_score !== null && (
                      <Badge tone="cyan">{Math.round(session.average_score)} / 100</Badge>
                    )}
                  </div>
                  <p className="truncate font-semibold text-ink">{session.role_title}</p>
                  {session.company_name && (
                    <p className="text-sm text-ink-muted">{session.company_name}</p>
                  )}
                </div>
                <span className="shrink-0 font-mono text-xs text-ink-faint">
                  {formatDistanceToNow(new Date(session.created_at), { addSuffix: true })}
                </span>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
