import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, FileText, Star, Trash2, Upload } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ChipGroup } from "@/components/ui/chip-group";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { preferencesApi, resumesApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";
import { humanize } from "@/lib/labels";
import type { Resume } from "@/lib/types";

/*
  Several CVs, one per career track.

  One CV cannot do two jobs: somebody applying for engineering roles and for
  sales roles has two different stories to tell. Which CV a given job uses is
  decided by the fields each one covers, and that choice is visible here —
  before anything is scored or written, rather than as a surprise in the
  application that already went out.
*/
export function ResumePage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [replacing, setReplacing] = useState<string | null>(null);

  const { data: resumes, isLoading } = useQuery({
    queryKey: ["resumes"],
    queryFn: resumesApi.list,
    retry: false,
  });
  const { data: options } = useQuery({
    queryKey: ["preference-options"],
    queryFn: preferencesApi.options,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["resumes"] });
  const fail = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Something went wrong");

  const uploadMutation = useMutation({
    mutationFn: ({ file, replaces }: { file: File; replaces?: string }) =>
      resumesApi.upload(file, { replaces }),
    onSuccess: () => {
      toast.success(replacing ? "Résumé replaced" : "Résumé added");
      setReplacing(null);
      refresh();
    },
    onError: (e) => {
      setReplacing(null);
      fail(e);
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, ...payload }: { id: string; label?: string; lanes?: string[]; is_primary?: boolean }) =>
      resumesApi.update(id, payload),
    onSuccess: refresh,
    onError: fail,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => resumesApi.remove(id),
    onSuccess: () => {
      toast.success("Résumé removed");
      refresh();
    },
    onError: fail,
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadMutation.mutate({ file, replaces: replacing ?? undefined });
    e.target.value = "";
  };

  const pick = (replaces?: string) => {
    setReplacing(replaces ?? null);
    fileInputRef.current?.click();
  };

  const lanes = options?.lanes ?? [];

  return (
    <div>
      <PageHeader
        eyebrow="Résumé"
        title="Your CVs"
        description="Keep one per kind of role. Each job is scored, tailored and pitched from the CV that covers its field."
        action={
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              className="hidden"
              onChange={handleFileChange}
            />
            <Button onClick={() => pick()} disabled={uploadMutation.isPending} size="sm">
              <Upload className="h-3.5 w-3.5" />
              {uploadMutation.isPending ? "Parsing…" : "Add a CV"}
            </Button>
          </>
        }
      />

      {isLoading ? (
        <PageSpinner />
      ) : !resumes || resumes.length === 0 ? (
        <EmptyState
          icon={FileText}
          title="No CV uploaded yet"
          description="PDF, DOCX or TXT — parsed into skills, experience and achievements, then used to score every job."
        />
      ) : (
        <div className="space-y-4">
          {resumes.map((resume) => (
            <ResumeCard
              key={resume.id}
              resume={resume}
              lanes={lanes}
              onlyOne={resumes.length === 1}
              busy={updateMutation.isPending || deleteMutation.isPending}
              onLanes={(next) => updateMutation.mutate({ id: resume.id, lanes: next })}
              onLabel={(label) => updateMutation.mutate({ id: resume.id, label })}
              onPrimary={() => updateMutation.mutate({ id: resume.id, is_primary: true })}
              onReplace={() => pick(resume.id)}
              onDelete={() => deleteMutation.mutate(resume.id)}
            />
          ))}

          <p className="px-1 text-sm text-ink-muted">
            A job whose field no CV covers uses the one marked{" "}
            <span className="font-semibold text-ink">Default</span>.
          </p>
        </div>
      )}
    </div>
  );
}

interface CardProps {
  resume: Resume;
  lanes: string[];
  onlyOne: boolean;
  busy: boolean;
  onLanes: (next: string[]) => void;
  onLabel: (label: string) => void;
  onPrimary: () => void;
  onReplace: () => void;
  onDelete: () => void;
}

function ResumeCard({
  resume,
  lanes,
  onlyOne,
  busy,
  onLanes,
  onLabel,
  onPrimary,
  onReplace,
  onDelete,
}: CardProps) {
  const [editingLabel, setEditingLabel] = useState(false);
  const [draftLabel, setDraftLabel] = useState(resume.label);
  const [confirmDelete, setConfirmDelete] = useState(false);

  const saveLabel = () => {
    setEditingLabel(false);
    const next = draftLabel.trim();
    if (next && next !== resume.label) onLabel(next);
    else setDraftLabel(resume.label);
  };

  return (
    <Card>
      <CardHeader className="flex-col items-start gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          {editingLabel ? (
            <input
              autoFocus
              value={draftLabel}
              onChange={(e) => setDraftLabel(e.target.value)}
              onBlur={saveLabel}
              onKeyDown={(e) => {
                if (e.key === "Enter") saveLabel();
                if (e.key === "Escape") {
                  setDraftLabel(resume.label);
                  setEditingLabel(false);
                }
              }}
              className="w-full rounded-md border border-border-strong px-2 py-1 text-base font-semibold text-ink"
              maxLength={80}
            />
          ) : (
            <button onClick={() => setEditingLabel(true)} className="text-left hover:underline" title="Rename">
              <CardTitle>{resume.label}</CardTitle>
            </button>
          )}
          <p className="mt-1 text-xs text-ink-faint">
            {resume.file_name ?? "No file name"} · {resume.experience_years ?? "?"} yrs experience
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {resume.is_primary ? (
            <Badge tone="accent">
              <Star className="h-3 w-3" /> Default
            </Badge>
          ) : (
            <Button variant="outline" size="sm" onClick={onPrimary} disabled={busy}>
              Make default
            </Button>
          )}
          <Button variant="outline" size="sm" onClick={onReplace} disabled={busy}>
            Replace file
          </Button>
          {/* The only CV cannot go: deleting it would leave scoring and
              tailoring with nothing to work from. */}
          {!onlyOne &&
            (confirmDelete ? (
              <Button variant="outline" size="sm" onClick={onDelete} disabled={busy} className="text-danger">
                <Check className="h-3.5 w-3.5" /> Confirm
              </Button>
            ) : (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setConfirmDelete(true)}
                disabled={busy}
                aria-label={`Delete ${resume.label}`}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            ))}
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="space-y-2">
          <p className="font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">Use this CV for</p>
          <ChipGroup
            aria-label={`Job families for ${resume.label}`}
            options={lanes.map((lane) => ({ value: lane, label: humanize(lane) }))}
            value={resume.lanes}
            onChange={onLanes}
          />
          {resume.lanes.length === 0 && (
            <p className="text-xs text-ink-faint">
              No field picked — this CV is only used{" "}
              {resume.is_primary ? "as the default" : "if you make it the default"}.
            </p>
          )}
        </div>

        {resume.summary && <p className="text-sm text-ink-muted">{resume.summary}</p>}

        <div>
          <p className="mb-1.5 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">Skills</p>
          <div className="flex flex-wrap gap-1.5">
            {resume.parsed_skills.map((skill) => (
              <Badge key={skill} tone="accent">
                {skill}
              </Badge>
            ))}
          </div>
        </div>

        {resume.achievements.length > 0 && (
          <div>
            <p className="mb-1.5 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">Achievements</p>
            <ul className="list-inside list-disc space-y-1 text-sm text-ink-muted">
              {resume.achievements.map((achievement, i) => (
                <li key={i}>{achievement}</li>
              ))}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
