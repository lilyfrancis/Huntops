import { Building2, MapPin, Send } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScoreBar } from "@/components/ui/score-bar";
import type { JobMatch } from "@/lib/types";

interface MatchCardProps {
  match: JobMatch;
  onViewJob: () => void;
  onRequestOutreach: () => void;
  outreachPending: boolean;
  outreachDisabled: boolean;
}

export function MatchCard({ match, onViewJob, onRequestOutreach, outreachPending, outreachDisabled }: MatchCardProps) {
  const { job } = match;
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            {match.geo_boost_applied && <Badge tone="good">Home market</Badge>}
            {job.is_remote && <Badge tone="cyan">Remote</Badge>}
          </div>
          <button onClick={onViewJob} className="text-left text-base font-semibold text-ink hover:text-accent-strong">
            {job.title}
          </button>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-muted">
            <span className="flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5" /> {job.company_name ?? "Company withheld"}
            </span>
            <span className="flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5" /> {job.location}
            </span>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-center rounded-lg border border-border bg-surface-2 px-3 py-2">
          <span className="font-mono text-lg font-semibold text-accent-strong">{Math.round(match.fit_score)}</span>
          <span className="font-mono text-[0.6rem] uppercase tracking-wide text-ink-faint">fit</span>
        </div>
      </div>

      {match.reason && <p className="mt-3 text-sm text-ink-muted">{match.reason}</p>}

      <div className="mt-4 space-y-2">
        <ScoreBar label="Skills" value={match.skills_score} />
        <ScoreBar label="Experience" value={match.experience_score} />
        <ScoreBar label="Location" value={match.geo_score} tone="cyan" />
      </div>

      <div className="mt-4 flex items-center gap-2 border-t border-border pt-4">
        <Button variant="outline" size="sm" onClick={onViewJob}>
          View job
        </Button>
        <Button
          size="sm"
          onClick={onRequestOutreach}
          disabled={outreachDisabled || outreachPending}
          title={outreachDisabled ? "Elite tier required" : undefined}
        >
          <Send className="h-3.5 w-3.5" />
          {outreachPending ? "Reaching out…" : "Autopilot outreach"}
        </Button>
      </div>
    </Card>
  );
}
