import { api } from "../api-client";
import type { AdminAnalytics, EmailSyncRun, IngestionRun, Job, User } from "../types";

export const adminApi = {
  users: (skip = 0, limit = 50) => api.get<User[]>(`/api/admin/users?skip=${skip}&limit=${limit}`),
  approveUser: (userId: string) => api.put<User>(`/api/admin/users/${userId}/approve`),
  suspendUser: (userId: string) => api.put<User>(`/api/admin/users/${userId}/suspend`),

  pendingJobs: () => api.get<Job[]>("/api/admin/jobs/pending"),
  approveJob: (jobId: string) => api.put<Job>(`/api/admin/jobs/${jobId}/approve`),
  rejectJob: (jobId: string, reason: string) => api.put<Job>(`/api/admin/jobs/${jobId}/reject`, { reason }),

  triggerAggregation: () => api.post<Record<string, { fetched: number; inserted: number; status: string }>>(
    "/api/admin/jobs/aggregate"
  ),
  aggregationRuns: () => api.get<IngestionRun[]>("/api/admin/jobs/aggregation-runs"),
  emailSyncRuns: () => api.get<EmailSyncRun[]>("/api/admin/email-sync-runs"),
  analytics: () => api.get<AdminAnalytics>("/api/admin/analytics"),
};
