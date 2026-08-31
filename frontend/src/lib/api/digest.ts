import { api } from "../api-client";
import type { DigestPreview } from "../types";

export const digestApi = {
  preview: () => api.get<DigestPreview>("/api/digest/preview"),
};
