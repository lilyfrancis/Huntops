import { formatDistanceToNow } from "date-fns";
import {
  Building2,
  Check,
  ExternalLink,
  Globe2,
  MapPin,
  Radio,
  Send,
} from "lucide-react";
import type { FeedItem } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { GhostBadge } from "@/components/jobs/ghost-badge";
import { cn } from "@/lib/utils";
import { sourceLabel } from "@/lib/labels";

const JOB_TYPE_LABEL: Record<FeedItem["job"]["job_type"], string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  internship: "Internship",
};

/** Fit is the number people act on, so it gets colour, not just a digit. */
function fitTone(score: number): string {
  if (score >= 85) return "bg-good-soft text-good border-good/30";
  if (score >= 70) return "bg-violet-soft text-violet-dark border-violet/25";
  return "bg-surface-2 text-ink-muted border-border-strong";
}

interface FeedCardProps {
  item: FeedItem;
  onOpen: () => void;
  onApply: () => void;
  onOutreach: () => void;
  isApplying?: boolean;
  isDrafting?: boolean;
}

export function FeedCard({ item, onOpen, onApply, onOutreach, isApplying, isDrafting }: FeedCardProps) {
  const { job } = item;

  return (
    <Card className="p-5 transition-colors hover:border-border-strong">
      <div className="flex items-start justify-between gap-4">
        <button type="button" onClick={onOpen} className="min-w-0 flex-1 text-left">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            {job.is_featured && <Badge tone="accent">Featured</Badge>}
            {job.market && (
              <Badge tone="neutral">
                <Globe2 className="h-2.5 w-2.5" /> {job.market}
              </Badge>
            )}
            {job.is_remote && (
              <Badge tone="cyan">
                <Radio className="h-2.5 w-2.5" /> Remote
              </Badge>
            )}
            <GhostBadge band={job.ghost_band} />
          </div>

          <h3 className="truncate text-base font-semibold text-ink">{job.title}</h3>

          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-ink-muted">
            <span className="flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5" /> {job.company_name ?? "Company withheld"}
            </span>
            <span className="flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5" /> {job.location}
            </span>
            <span>{JOB_TYPE_LABEL[job.job_type]}</span>
            {job.salary_range && <span>{job.salary_range}</span>}
          </div>

          {item.fit_reason && <p className="mt-2 line-clamp-2 text-sm text-ink-muted">{item.fit_reason}</p>}
        </button>

        <div className="flex shrink-0 flex-col items-end gap-2">
          {item.fit_score !== null ? (
            <span
              className={cn(
                "rounded-lg border px-2 py-1 font-mono text-sm font-bold tabular-nums",
                fitTone(item.fit_score)
              )}
              title="Fit score against your résumé"
            >
              {Math.round(item.fit_score)}
            </span>
          ) : (
            <span className="font-mono text-[11px] uppercase tracking-widest text-ink-faint">Unscored</span>
          )}
          <span className="whitespace-nowrap font-mono text-xs text-ink-faint">
            {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
          </span>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-3">
        {item.applied ? (
          <span className="inline-flex items-center gap-1.5 text-sm font-medium text-good">
            <Check className="h-4 w-4" strokeWidth={2.5} /> Applied
          </span>
        ) : item.can_apply_directly ? (
          <Button size="sm" onClick={onApply} disabled={isApplying}>
            {isApplying ? "Applying…" : "Apply"}
          </Button>
        ) : (
          /*
            An aggregated listing lives behind someone else's form on someone
            else's site — we can't submit it. The honest pair of affordances is
            a link out and outreach to a human, never a button that pretends.
          */
          <Button size="sm" variant="outline" asChild>
            <a href={job.source_url ?? "#"} target="_blank" rel="noreferrer noopener">
              Apply on {sourceLabel(job.source)} <ExternalLink className="h-3.5 w-3.5" />
            </a>
          </Button>
        )}

        {item.outreach_sent ? (
          <span className="inline-flex items-center gap-1.5 text-sm text-ink-muted">
            <Send className="h-3.5 w-3.5" /> Outreach sent
          </span>
        ) : (
          <Button size="sm" variant="ghost" onClick={onOutreach} disabled={isDrafting}>
            <Send className="h-3.5 w-3.5" />
            {isDrafting ? "Drafting…" : "Find a contact"}
          </Button>
        )}
      </div>
    </Card>
  );
}
