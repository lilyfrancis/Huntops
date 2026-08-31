import { api } from "../api-client";
import type { JobMatch } from "../types";

export const matchesApi = {
  list: (limit = 10) => api.get<JobMatch[]>(`/api/ai/match-jobs?limit=${limit}`),
};
