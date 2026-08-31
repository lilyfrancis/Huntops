import { api } from "../api-client";
import type { Application, ApplicationStatus } from "../types";

export const applicationsApi = {
  apply: (jobId: string, coverLetter?: string) =>
    api.post<Application>("/api/applications", { job_id: jobId, cover_letter: coverLetter }),
  mine: () => api.get<Application[]>("/api/applications/mine"),
  forJob: (jobId: string) => api.get<Application[]>(`/api/applications/job/${jobId}`),
  updateStatus: (applicationId: string, status: ApplicationStatus) =>
    api.put<Application>(`/api/applications/${applicationId}/status`, { status }),
};
