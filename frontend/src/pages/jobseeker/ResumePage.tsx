import { useRef } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileText, Upload } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageSpinner } from "@/components/ui/spinner";
import { EmptyState } from "@/components/ui/empty-state";
import { resumesApi } from "@/lib/api";
import { ApiError } from "@/lib/api-client";

export function ResumePage() {
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: resume, isLoading } = useQuery({ queryKey: ["resume", "me"], queryFn: resumesApi.me, retry: false });

  const uploadMutation = useMutation({
    mutationFn: (file: File) => resumesApi.upload(file),
    onSuccess: () => {
      toast.success("Résumé parsed");
      queryClient.invalidateQueries({ queryKey: ["resume", "me"] });
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Upload failed"),
  });

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadMutation.mutate(file);
    e.target.value = "";
  };

  return (
    <div>
      <PageHeader
        eyebrow="Résumé"
        title="Your résumé"
        description="Parsed once, used to score every job and personalize every outreach draft."
        action={
          <>
            <input ref={fileInputRef} type="file" accept=".pdf,.docx,.txt" className="hidden" onChange={handleFileChange} />
            <Button onClick={() => fileInputRef.current?.click()} disabled={uploadMutation.isPending} size="sm">
              <Upload className="h-3.5 w-3.5" />
              {uploadMutation.isPending ? "Parsing…" : resume ? "Re-upload" : "Upload résumé"}
            </Button>
          </>
        }
      />

      {isLoading ? (
        <PageSpinner />
      ) : !resume ? (
        <EmptyState
          icon={FileText}
          title="No résumé uploaded yet"
          description="PDF, DOCX, or TXT — parsed by Claude into skills, experience, and achievements."
        />
      ) : (
        <div className="space-y-4">
          <Card>
            <CardHeader className="flex-row items-center justify-between">
              <CardTitle>{resume.file_name ?? "Résumé"}</CardTitle>
              <span className="font-mono text-xs text-ink-faint">
                {resume.experience_years ?? "?"} yrs experience
              </span>
            </CardHeader>
            <CardContent className="space-y-4">
              {resume.summary && <p className="text-sm text-ink-muted">{resume.summary}</p>}

              <div>
                <p className="mb-1.5 font-mono text-[0.7rem] uppercase tracking-wide text-ink-faint">Education</p>
                <p className="text-sm text-ink">{resume.education ?? "Not specified"}</p>
              </div>

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
        </div>
      )}
    </div>
  );
}
