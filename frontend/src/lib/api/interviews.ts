import { api } from "../api-client";
import type { InterviewSession, InterviewSessionSummary, InterviewTurn } from "../types";

export const interviewsApi = {
  start: (payload: { job_id?: string; role_title?: string }) =>
    api.post<InterviewSession>("/api/interviews", payload),
  mine: () => api.get<InterviewSessionSummary[]>("/api/interviews"),
  get: (sessionId: string) => api.get<InterviewSession>(`/api/interviews/${sessionId}`),
  answer: (sessionId: string, position: number, answer: string) =>
    api.post<InterviewTurn>(`/api/interviews/${sessionId}/turns/${position}/answer`, { answer }),
  complete: (sessionId: string) => api.post<InterviewSession>(`/api/interviews/${sessionId}/complete`),
};
