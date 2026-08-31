import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Building2, MapPin, ExternalLink } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { applicationsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { Job } from "@/lib/types";
import { useAuth } from "@/hooks/use-auth";

export function JobDetailDialog({ job, open, onOpenChange }: { job: Job | null; open: boolean; onOpenChange: (v: boolean) => void }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [coverLetter, setCoverLetter] = useState("");

  const applyMutation = useMutation({
    mutationFn: (jobId: string) => applicationsApi.apply(jobId, coverLetter || undefined),
    onSuccess: () => {
      toast.success("Application sent");
      queryClient.invalidateQueries({ queryKey: ["applications", "mine"] });
      onOpenChange(false);
      setCoverLetter("");
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't apply"),
  });

  if (!job) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <div className="mb-3 flex flex-wrap gap-2">
          {job.is_featured && <Badge tone="accent">Featured</Badge>}
          {job.is_remote && <Badge tone="cyan">Remote</Badge>}
          {job.lane && <Badge tone="neutral">{job.lane.replace("_", " ")}</Badge>}
        </div>
        <DialogTitle>{job.title}</DialogTitle>
        <DialogDescription asChild>
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-sm">
            <span className="flex items-center gap-1">
              <Building2 className="h-3.5 w-3.5" /> {job.company_name ?? "Company withheld"}
            </span>
            <span className="flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5" /> {job.location}
            </span>
            {job.salary_range && <span>{job.salary_range}</span>}
          </div>
        </DialogDescription>

        <div className="max-h-64 overflow-y-auto rounded-lg border border-border bg-surface-2 p-4 text-sm text-ink-muted whitespace-pre-wrap">
          {job.description}
        </div>

        {job.requirements.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {job.requirements.map((req) => (
              <Badge key={req} tone="neutral">
                {req}
              </Badge>
            ))}
          </div>
        )}

        {job.source_url && (
          <a
            href={job.source_url}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex items-center gap-1.5 text-sm text-cyan hover:underline"
          >
            View original listing <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}

        {user?.role === "job_seeker" && job.source === "internal" && (
          <div className="mt-5 space-y-2 border-t border-border pt-4">
            <Textarea
              placeholder="Cover letter (optional)"
              value={coverLetter}
              onChange={(e) => setCoverLetter(e.target.value)}
              rows={3}
            />
            <Button
              className="w-full"
              onClick={() => applyMutation.mutate(job.id)}
              disabled={applyMutation.isPending}
            >
              {applyMutation.isPending ? "Applying…" : "Apply"}
            </Button>
          </div>
        )}
        {job.source !== "internal" && (
          <p className="mt-4 border-t border-border pt-4 text-xs text-ink-faint">
            This listing came from an external source — apply via the original listing link above.
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
