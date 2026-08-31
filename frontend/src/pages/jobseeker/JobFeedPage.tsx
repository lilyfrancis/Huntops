import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Briefcase, Search } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { JobCard } from "@/components/jobs/job-card";
import { JobDetailDialog } from "@/components/jobs/job-detail-dialog";
import { Input } from "@/components/ui/input";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { jobsApi } from "@/lib/api";
import type { Job } from "@/lib/types";

export function JobFeedPage() {
  const [location, setLocation] = useState("");
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);

  const { data: jobs, isLoading } = useQuery({
    queryKey: ["jobs", { location }],
    queryFn: () => jobsApi.list({ location: location || undefined, limit: 50 }),
  });

  return (
    <div>
      <PageHeader
        eyebrow="Live feed"
        title="Job feed"
        description="Aggregated from six live sources plus jobs posted directly on HuntOps."
      />

      <div className="mb-6 flex items-center gap-2">
        <div className="relative max-w-xs flex-1">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-faint" />
          <Input
            placeholder="Filter by location…"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            className="pl-9"
          />
        </div>
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : !jobs || jobs.length === 0 ? (
        <EmptyState icon={Briefcase} title="No jobs match yet" description="Try clearing the location filter, or check back after the next aggregation run." />
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} onClick={() => setSelectedJob(job)} />
          ))}
        </div>
      )}

      <JobDetailDialog job={selectedJob} open={!!selectedJob} onOpenChange={(v) => !v && setSelectedJob(null)} />
    </div>
  );
}
