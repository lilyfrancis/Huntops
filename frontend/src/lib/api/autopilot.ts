import { api } from "../api-client";
import type { AutopilotAction, AutopilotRunSummary } from "../types";

export const autopilotApi = {
  actions: (limit = 25) => api.get<AutopilotAction[]>(`/api/autopilot/actions?limit=${limit}`),
  runNow: () => api.post<AutopilotRunSummary>("/api/autopilot/run"),
};
