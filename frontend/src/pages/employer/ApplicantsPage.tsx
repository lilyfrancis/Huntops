import { useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { Users } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { applicationsApi, jobsApi } from "@/lib/api";
import type { ApplicationStatus } from "@/lib/types";

const STATUSES: ApplicationStatus[] = ["pending", "reviewed", "interviewing", "offered", "rejected", "withdrawn"];

export function ApplicantsPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const queryClient = useQueryClient();

  const { data: job } = useQuery({ queryKey: ["jobs", jobId], queryFn: () => jobsApi.get(jobId!), enabled: !!jobId });
  const { data: applications, isLoading } = useQuery({
    queryKey: ["applications", "job", jobId],
    queryFn: () => applicationsApi.forJob(jobId!),
    enabled: !!jobId,
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ApplicationStatus }) => applicationsApi.updateStatus(id, status),
    onSuccess: () => {
      toast.success("Status updated");
      queryClient.invalidateQueries({ queryKey: ["applications", "job", jobId] });
    },
  });

  return (
    <div>
      <PageHeader eyebrow="Applicants" title={job?.title ?? "Job"} description={job ? `${job.location} · ${job.job_type.replace("_", " ")}` : undefined} />

      {isLoading ? (
        <PageSpinner />
      ) : !applications || applications.length === 0 ? (
        <EmptyState icon={Users} title="No applicants yet" description="Applications will show up here as candidates apply." />
      ) : (
        <div className="space-y-3">
          {applications.map((app) => (
            <Card key={app.id} className="flex items-center justify-between gap-4 p-4">
              <div className="min-w-0">
                <p className="truncate text-sm font-medium text-ink">{app.candidate_name}</p>
                <p className="truncate text-xs text-ink-muted">{app.candidate_email}</p>
                {app.cover_letter && <p className="mt-1 line-clamp-2 text-xs text-ink-muted">{app.cover_letter}</p>}
                <p className="mt-1 font-mono text-[0.7rem] text-ink-faint">
                  Applied {formatDistanceToNow(new Date(app.created_at), { addSuffix: true })}
                </p>
              </div>
              <Select
                value={app.status}
                onValueChange={(status) => statusMutation.mutate({ id: app.id, status: status as ApplicationStatus })}
              >
                <SelectTrigger className="w-40 shrink-0">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
