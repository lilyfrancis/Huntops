import { api } from "../api-client";
import type { Application, ApplicationDraft, ApplicationStatus } from "../types";

export const applicationsApi = {
  apply: (jobId: string, coverLetter?: string, bullets?: string[]) =>
    api.post<Application>("/api/applications", {
      job_id: jobId,
      cover_letter: coverLetter,
      tailored_bullets: bullets ?? [],
    }),
  // POST because the first call spends credits and creates a row; later
  // calls return the cached draft and cost nothing.
  draft: (jobId: string, regenerate = false) =>
    api.post<ApplicationDraft>(`/api/applications/draft/${jobId}?regenerate=${regenerate}`, {}),
  saveDraft: (jobId: string, coverLetter: string, bullets: string[]) =>
    api.put<ApplicationDraft>(`/api/applications/draft/${jobId}`, {
      cover_letter: coverLetter,
      bullets,
    }),
  mine: () => api.get<Application[]>("/api/applications/mine"),
  forJob: (jobId: string) => api.get<Application[]>(`/api/applications/job/${jobId}`),
  updateStatus: (applicationId: string, status: ApplicationStatus) =>
    api.put<Application>(`/api/applications/${applicationId}/status`, { status }),
};
