import { api } from "../api-client";
import type { ExperienceLevel, Job, JobType } from "../types";

export interface JobFilters {
  location?: string;
  job_type?: JobType;
  featured_only?: boolean;
  hide_ghosts?: boolean;
  skip?: number;
  limit?: number;
}

export interface JobCreatePayload {
  title: string;
  description: string;
  requirements: string[];
  location: string;
  salary_range?: string;
  job_type: JobType;
  experience_level: ExperienceLevel;
}

function toQuery(params: object): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

export const jobsApi = {
  list: (filters: JobFilters = {}) => api.get<Job[]>(`/api/jobs${toQuery(filters)}`, { skipAuth: true }),
  get: (jobId: string) => api.get<Job>(`/api/jobs/${jobId}`, { skipAuth: true }),
  create: (payload: JobCreatePayload) => api.post<Job>("/api/jobs", payload),
  update: (jobId: string, payload: Partial<JobCreatePayload>) => api.put<Job>(`/api/jobs/${jobId}`, payload),
  delete: (jobId: string) => api.delete<void>(`/api/jobs/${jobId}`),
  mine: () => api.get<Job[]>("/api/jobs/employer/mine"),
};
