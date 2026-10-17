import { api } from "../api-client";
import type { MatchRun } from "../types";

export const matchesApi = {
  list: (limit = 10, skip = 0) =>
    api.get<MatchRun>(`/api/ai/match-jobs?limit=${limit}&skip=${skip}`),
};
