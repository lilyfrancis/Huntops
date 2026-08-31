import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Briefcase, PlusCircle, Trash2, Users } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { jobsApi } from "@/lib/api";
import type { JobStatus } from "@/lib/types";

const STATUS_TONE: Record<JobStatus, "neutral" | "good" | "danger" | "accent"> = {
  pending: "accent",
  active: "good",
  rejected: "danger",
  closed: "neutral",
};

export function MyJobsPage() {
  const queryClient = useQueryClient();
  const { data: jobs, isLoading } = useQuery({ queryKey: ["jobs", "mine"], queryFn: jobsApi.mine });

  const deleteMutation = useMutation({
    mutationFn: (jobId: string) => jobsApi.delete(jobId),
    onSuccess: () => {
      toast.success("Job removed");
      queryClient.invalidateQueries({ queryKey: ["jobs", "mine"] });
    },
  });

  return (
    <div>
      <PageHeader
        eyebrow="Employer"
        title="My jobs"
        action={
          <Button asChild size="sm">
            <Link to="/employer/post">
              <PlusCircle className="h-3.5 w-3.5" /> Post a job
            </Link>
          </Button>
        }
      />

      {isLoading ? (
        <PageSpinner />
      ) : !jobs || jobs.length === 0 ? (
        <EmptyState icon={Briefcase} title="No jobs posted yet" description="Post your first listing to start receiving applicants." />
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <Card key={job.id} className="flex items-center justify-between gap-4 p-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <p className="truncate text-sm font-medium text-ink">{job.title}</p>
                  <Badge tone={STATUS_TONE[job.status]}>{job.status}</Badge>
                </div>
                <p className="text-xs text-ink-muted">
                  {job.location} · {job.application_count} applicant{job.application_count === 1 ? "" : "s"}
                </p>
                {job.status === "rejected" && job.rejection_reason && (
                  <p className="mt-1 text-xs text-danger">Rejected: {job.rejection_reason}</p>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <Button asChild variant="outline" size="sm">
                  <Link to={`/employer/jobs/${job.id}/applicants`}>
                    <Users className="h-3.5 w-3.5" /> Applicants
                  </Link>
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => deleteMutation.mutate(job.id)}
                  disabled={deleteMutation.isPending}
                  aria-label="Delete job"
                >
                  <Trash2 className="h-4 w-4 text-ink-faint hover:text-danger" />
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
