import { api } from "../api-client";
import type { Resume } from "../types";

export const resumesApi = {
  me: () => api.get<Resume>("/api/resumes/me"),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post<Resume>("/api/resumes/upload", form, { isForm: true });
  },
};
