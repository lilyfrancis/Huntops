import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { CheckCircle2, Clock, XCircle } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { adminApi } from "@/lib/api";
import type { Job } from "@/lib/types";

export function PendingJobsPage() {
  const queryClient = useQueryClient();
  const [rejectTarget, setRejectTarget] = useState<Job | null>(null);
  const [reason, setReason] = useState("");

  const { data: jobs, isLoading } = useQuery({ queryKey: ["admin", "jobs", "pending"], queryFn: adminApi.pendingJobs });

  const approveMutation = useMutation({
    mutationFn: (jobId: string) => adminApi.approveJob(jobId),
    onSuccess: () => {
      toast.success("Job approved");
      queryClient.invalidateQueries({ queryKey: ["admin", "jobs", "pending"] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => adminApi.rejectJob(rejectTarget!.id, reason),
    onSuccess: () => {
      toast.success("Job rejected");
      queryClient.invalidateQueries({ queryKey: ["admin", "jobs", "pending"] });
      setRejectTarget(null);
      setReason("");
    },
  });

  return (
    <div>
      <PageHeader eyebrow="Moderation" title="Pending jobs" description="Employer listings waiting for review." />

      {isLoading ? (
        <PageSpinner />
      ) : !jobs || jobs.length === 0 ? (
        <EmptyState icon={Clock} title="Nothing pending" description="New employer listings will show up here for review." />
      ) : (
        <div className="space-y-3">
          {jobs.map((job) => (
            <Card key={job.id} className="flex items-start justify-between gap-4 p-4">
              <div className="min-w-0">
                <p className="text-sm font-medium text-ink">{job.title}</p>
                <p className="text-xs text-ink-muted">
                  {job.company_name ?? job.employer_name} · {job.location}
                </p>
                <p className="mt-2 line-clamp-2 text-xs text-ink-muted">{job.description}</p>
              </div>
              <div className="flex shrink-0 gap-2">
                <Button size="sm" onClick={() => approveMutation.mutate(job.id)} disabled={approveMutation.isPending}>
                  <CheckCircle2 className="h-3.5 w-3.5" /> Approve
                </Button>
                <Button size="sm" variant="danger" onClick={() => setRejectTarget(job)}>
                  <XCircle className="h-3.5 w-3.5" /> Reject
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Dialog open={!!rejectTarget} onOpenChange={(v) => !v && setRejectTarget(null)}>
        <DialogContent>
          <DialogTitle>Reject "{rejectTarget?.title}"</DialogTitle>
          <DialogDescription>The employer will see this reason.</DialogDescription>
          <Textarea value={reason} onChange={(e) => setReason(e.target.value)} rows={3} placeholder="Reason for rejection" />
          <Button className="mt-4 w-full" variant="danger" disabled={!reason.trim() || rejectMutation.isPending} onClick={() => rejectMutation.mutate()}>
            {rejectMutation.isPending ? "Rejecting…" : "Confirm rejection"}
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
