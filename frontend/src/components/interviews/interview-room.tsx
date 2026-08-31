import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ArrowLeft, CheckCircle2, CircleDot, Lightbulb, ThumbsUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { ScoreBar } from "@/components/ui/score-bar";
import { interviewsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { InterviewTurn } from "@/lib/types";
import { cn } from "@/lib/utils";

function TurnFeedback({ turn }: { turn: InterviewTurn }) {
  if (turn.score === null) return null;
  return (
    <div className="mt-4 space-y-4 border-t border-border pt-4">
      <ScoreBar value={turn.score} label="Answer score" />

      {turn.strengths.length > 0 && (
        <div>
          <p className="mb-1.5 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-good">
            <ThumbsUp className="h-3 w-3" /> What worked
          </p>
          <ul className="space-y-1">
            {turn.strengths.map((item) => (
              <li key={item} className="text-sm text-ink-muted">
                — {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {turn.improvements.length > 0 && (
        <div>
          <p className="mb-1.5 flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-warning">
            <Lightbulb className="h-3 w-3" /> Sharpen this
          </p>
          <ul className="space-y-1">
            {turn.improvements.map((item) => (
              <li key={item} className="text-sm text-ink-muted">
                — {item}
              </li>
            ))}
          </ul>
        </div>
      )}

      {turn.model_answer && (
        <div className="rounded-lg border border-border bg-surface-2 p-3">
          <p className="mb-1.5 font-mono text-[11px] uppercase tracking-widest text-cyan">
            A stronger answer
          </p>
          <p className="text-sm text-ink-muted">{turn.model_answer}</p>
        </div>
      )}
    </div>
  );
}

export function InterviewRoom({ sessionId, onExit }: { sessionId: string; onExit: () => void }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState("");

  const { data: session, isLoading } = useQuery({
    queryKey: ["interviews", sessionId],
    queryFn: () => interviewsApi.get(sessionId),
  });

  const answerMutation = useMutation({
    mutationFn: (position: number) => interviewsApi.answer(sessionId, position, draft.trim()),
    onSuccess: () => {
      setDraft("");
      queryClient.invalidateQueries({ queryKey: ["interviews", sessionId] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't grade that answer"),
  });

  const completeMutation = useMutation({
    mutationFn: () => interviewsApi.complete(sessionId),
    onSuccess: () => {
      toast.success("Interview complete");
      queryClient.invalidateQueries({ queryKey: ["interviews", sessionId] });
      queryClient.invalidateQueries({ queryKey: ["interviews", "mine"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't wrap up the interview"),
  });

  if (isLoading || !session) return <PageSpinner />;

  const answered = session.turns.filter((t) => t.score !== null).length;
  const current = session.turns.find((t) => t.score === null);
  const isDone = session.status === "completed";

  return (
    <div>
      <Button variant="ghost" size="sm" onClick={onExit} className="mb-4">
        <ArrowLeft className="h-3.5 w-3.5" /> All interviews
      </Button>

      <div className="mb-6">
        <span className="eyebrow">Mock interview</span>
        <h1 className="mt-1 text-3xl">{session.role_title}</h1>
        <div className="mt-2 flex items-center gap-3 text-sm text-ink-muted">
          <span className="font-mono text-xs uppercase tracking-widest">
            {answered} / {session.turns.length} answered
          </span>
          {session.average_score !== null && (
            <Badge tone="cyan">Average {Math.round(session.average_score)} / 100</Badge>
          )}
        </div>
      </div>

      {isDone && session.summary && (
        <Card className="mb-6 border-good/40">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <CheckCircle2 className="h-4 w-4 text-good" /> How you did
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-ink-muted">{session.summary}</p>
            {session.next_steps.length > 0 && (
              <ul className="mt-3 space-y-1">
                {session.next_steps.map((step) => (
                  <li key={step} className="text-sm text-ink-muted">
                    — {step}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      <div className="space-y-4">
        {session.turns.map((turn) => {
          const isCurrent = !isDone && current?.id === turn.id;
          return (
            <Card key={turn.id} className={cn(isCurrent && "border-accent/50")}>
              <CardHeader>
                <div className="flex items-center gap-2">
                  <CircleDot
                    className={cn("h-3.5 w-3.5", turn.score !== null ? "text-good" : "text-ink-faint")}
                  />
                  <span className="font-mono text-[11px] uppercase tracking-widest text-ink-faint">
                    Question {turn.position + 1}
                  </span>
                </div>
                <CardTitle className="mt-1 text-base leading-snug">{turn.question}</CardTitle>
              </CardHeader>
              <CardContent>
                {turn.answer && (
                  <p className="whitespace-pre-wrap rounded-lg border border-border bg-surface-2 p-3 text-sm text-ink-muted">
                    {turn.answer}
                  </p>
                )}

                {isCurrent && (
                  <div className="space-y-2">
                    <Textarea
                      placeholder="Answer out loud, then type the version you'd actually say…"
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      rows={5}
                    />
                    <Button
                      onClick={() => answerMutation.mutate(turn.position)}
                      disabled={!draft.trim() || answerMutation.isPending}
                    >
                      {answerMutation.isPending ? "Grading…" : "Submit answer"}
                    </Button>
                  </div>
                )}

                {!isCurrent && !turn.answer && (
                  <p className="text-sm text-ink-faint">
                    {isDone ? "Not answered." : "Answer the questions above first."}
                  </p>
                )}

                <TurnFeedback turn={turn} />
              </CardContent>
            </Card>
          );
        })}
      </div>

      {!isDone && answered > 0 && (
        <div className="mt-6">
          <Button
            variant="outline"
            onClick={() => completeMutation.mutate()}
            disabled={completeMutation.isPending}
          >
            {completeMutation.isPending ? "Wrapping up…" : "Finish and get my summary"}
          </Button>
        </div>
      )}
    </div>
  );
}
