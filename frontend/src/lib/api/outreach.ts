import { api } from "../api-client";
import type { Outreach } from "../types";

export const outreachApi = {
  create: (jobId: string) => api.post<Outreach>("/api/outreach", { job_id: jobId }),
  mine: () => api.get<Outreach[]>("/api/outreach/mine"),
  get: (id: string) => api.get<Outreach>(`/api/outreach/${id}`),
};
