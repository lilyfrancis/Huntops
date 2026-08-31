import { api } from "../api-client";
import type { HuntStats } from "../types";

export const statsApi = {
  me: () => api.get<HuntStats>("/api/stats/me"),
};
