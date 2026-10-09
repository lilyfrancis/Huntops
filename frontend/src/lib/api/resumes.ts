import { api } from "../api-client";
import type { Resume } from "../types";

export const resumesApi = {
  /** Every CV on the account, primary first. */
  list: () => api.get<Resume[]>("/api/resumes"),
  /** The fallback CV. Kept for the places that want one without a job. */
  me: () => api.get<Resume>("/api/resumes/me"),
  /** Adds a CV. Pass `replaces` to overwrite one instead of adding another —
      without it, re-uploading would leave two copies rather than updating. */
  upload: (file: File, opts?: { label?: string; replaces?: string }) => {
    const form = new FormData();
    form.append("file", file);
    if (opts?.label) form.append("label", opts.label);
    if (opts?.replaces) form.append("replaces", opts.replaces);
    return api.post<Resume>("/api/resumes/upload", form, { isForm: true });
  },
  update: (id: string, payload: { label?: string; lanes?: string[]; is_primary?: boolean }) =>
    api.patch<Resume>(`/api/resumes/${id}`, payload),
  remove: (id: string) => api.delete<void>(`/api/resumes/${id}`),
};
