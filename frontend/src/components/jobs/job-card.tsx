import { formatDistanceToNow } from "date-fns";
import { Building2, MapPin, Radio } from "lucide-react";
import type { Job } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

const JOB_TYPE_LABEL: Record<Job["job_type"], string> = {
  full_time: "Full-time",
  part_time: "Part-time",
  contract: "Contract",
  internship: "Internship",
};

export function JobCard({ job, onClick }: { job: Job; onClick?: () => void }) {
  return (
    <Card
      onClick={onClick}
      className="cursor-pointer p-5 transition-colors hover:border-border-strong"
      role={onClick ? "button" : undefined}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="mb-1.5 flex flex-wrap items-center gap-2">
            {job.is_featured && <Badge tone="accent">Featured</Badge>}
            {job.is_remote && (
              <Badge tone="cyan">
                <Radio className="h-2.5 w-2.5" /> Remote
              </Badge>
            )}
            {job.source !== "internal" && <Badge tone="neutral">{job.source}</Badge>}
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
        </div>
        <span className="shrink-0 whitespace-nowrap font-mono text-xs text-ink-faint">
          {formatDistanceToNow(new Date(job.created_at), { addSuffix: true })}
        </span>
      </div>
    </Card>
  );
}
