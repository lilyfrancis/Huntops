import { api } from "../api-client";
import type { PreferenceOptions, Preferences, PreferencesUpdate } from "../types";

export const preferencesApi = {
  get: () => api.get<Preferences>("/api/users/preferences"),
  options: () => api.get<PreferenceOptions>("/api/users/preferences/options"),
  update: (payload: PreferencesUpdate) => api.put<Preferences>("/api/users/preferences", payload),
};
