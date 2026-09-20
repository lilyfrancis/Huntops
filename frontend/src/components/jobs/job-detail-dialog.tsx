import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Building2, MapPin, ExternalLink, Wand2 } from "lucide-react";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { GhostBadge, GhostReasons } from "@/components/jobs/ghost-badge";
import { applicationsApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import type { ApplicationDraft, Job } from "@/lib/types";

// Mirrors TAILOR_CREDIT_COST on the server.
const TAILOR_COST = 10;
import { useAuth } from "@/hooks/use-auth";

export function JobDetailDialog({ job, open, onOpenChange }: { job: Job | null; open: boolean; onOpenChange: (v: boolean) => void }) {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [coverLetter, setCoverLetter] = useState("");
  const [bullets, setBullets] = useState<string[]>([]);
  const [draft, setDraft] = useState<ApplicationDraft | null>(null);

  // Cleared between jobs: leaving one role's letter in the box while the
  // next one's description is on screen is how the wrong thing gets sent.
  useEffect(() => {
    setCoverLetter("");
    setBullets([]);
    setDraft(null);
  }, [job?.id]);

  // Read before the click so the cost and what is left can be stated up
  // front. A button that charges and then refuses is worse than one that
  // says what it will do.
  const { data: allowance } = useQuery({
    queryKey: ["concierge", "allowance"],
    queryFn: applicationsApi.conciergeAllowance,
    enabled: user?.role === "job_seeker",
  });

  const draftMutation = useMutation({
    mutationFn: (regenerate: boolean) => applicationsApi.draft(job!.id, regenerate),
    onSuccess: (result) => {
      setDraft(result);
      setCoverLetter(result.cover_letter);
      setBullets(result.bullets);
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Couldn't write the draft"),
  });

  const applyMutation = useMutation({
    mutationFn: async (jobId: string) => {
      // Saved before applying so the edits survive as the draft too — the
      // application records what was sent, the draft is what they can come
      // back to.
      if (draft && (coverLetter !== draft.cover_letter || bullets.join("\u0000") !== draft.bullets.join("\u0000"))) {
        await applicationsApi.saveDraft(jobId, coverLetter, bullets);
      }
      return applicationsApi.apply(jobId, coverLetter || undefined, bullets);
    },
    onSuccess: () => {
      toast.success("Application sent");
      queryClient.invalidateQueries({ queryKey: ["applications", "mine"] });
      queryClient.invalidateQueries({ queryKey: ["concierge", "allowance"] });
      onOpenChange(false);
      setCoverLetter("");
      setBullets([]);
      setDraft(null);
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
          <GhostBadge band={job.ghost_band} />
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

        <div className="mt-3">
          <GhostReasons band={job.ghost_band} flags={job.ghost_flags} />
        </div>

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

        {/* No link to the original listing for a job seeker. Sending them
            there hands back the work this product exists to remove, and an
            admin files it for them instead. Admins keep the link — they are
            the ones who have to go and use it. */}
        {job.source_url && user?.role !== "job_seeker" && (
          <a
            href={job.source_url}
            target="_blank"
            rel="noreferrer"
            className="mt-3 inline-flex items-center gap-1.5 text-sm text-cyan hover:underline"
          >
            View original listing <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}

        {user?.role === "job_seeker" && (
          <div className="mt-5 space-y-3 border-t border-border pt-4">
            {job.source === "internal" && (
            <div className="flex items-center justify-between gap-3">
              <p className="text-xs text-ink-muted">
                {bullets.length > 0
                  ? draft?.edited
                    ? "Your edits will be sent."
                    : "Written for this role. Edit anything before you send it."
                  : `Write it for this role — ${TAILOR_COST} credits, once per job.`}
              </p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => draftMutation.mutate(bullets.length > 0)}
                disabled={draftMutation.isPending}
              >
                <Wand2 className="h-3.5 w-3.5" />
                {draftMutation.isPending
                  ? "Writing…"
                  : bullets.length > 0
                    ? "Rewrite"
                    : "Tailor for this job"}
              </Button>
            </div>
            )}

            {job.source === "internal" && (
            <Textarea
              placeholder="Cover letter (optional)"
              value={coverLetter}
              onChange={(e) => setCoverLetter(e.target.value)}
              rows={bullets.length > 0 ? 8 : 3}
            />
            )}

            {job.source === "internal" && bullets.length > 0 && (
              <div>
                <p className="mb-1.5 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">
                  Résumé bullets for this role
                </p>
                <ul className="space-y-1.5">
                  {bullets.map((bullet, i) => (
                    <li key={i}>
                      <Input
                        value={bullet}
                        onChange={(e) =>
                          setBullets(bullets.map((b, n) => (n === i ? e.target.value : b)))
                        }
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <Button
              className="w-full"
              onClick={() => applyMutation.mutate(job.id)}
              disabled={applyMutation.isPending}
            >
              {applyMutation.isPending ? "Applying…" : "Apply"}
            </Button>
          </div>
        )}
        {user?.role === "job_seeker" && job.source !== "internal" && (
          <p className="mt-2 text-xs text-ink-faint">
            {allowance?.remaining === null
              ? `We file this one for you. ${allowance.credit_cost} credits.`
              : allowance
                ? `We file this one for you — ${allowance.remaining} of ${allowance.allowance} left on your plan, ${allowance.credit_cost} credits each.`
                : "We file this one for you."}
          </p>
        )}
      </DialogContent>
    </Dialog>
  );
}
