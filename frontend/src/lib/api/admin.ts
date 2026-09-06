import { api } from "../api-client";
import type {
  AdminAnalytics,
  AlertMailbox,
  EmailSyncRun,
  IngestionRun,
  Job,
  JobLane,
  MailboxSyncResult,
  User,
} from "../types";

export interface MailboxConnectPayload {
  market: string;
  label?: string;
  lanes?: JobLane[];
}

export interface MailboxUpdatePayload {
  label?: string;
  market?: string;
  lanes?: JobLane[];
  is_active?: boolean;
}

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
  rescanGhosts: () =>
    api.post<{ scanned: number; clean: number; caution: number; likely_ghost: number }>(
      "/api/admin/jobs/rescan-ghosts"
    ),
  aggregationRuns: () => api.get<IngestionRun[]>("/api/admin/jobs/aggregation-runs"),
  emailSyncRuns: () => api.get<EmailSyncRun[]>("/api/admin/email-sync-runs"),
  analytics: () => api.get<AdminAnalytics>("/api/admin/analytics"),

  mailboxes: () => api.get<AlertMailbox[]>("/api/admin/mailboxes"),
  connectMailbox: (payload: MailboxConnectPayload) =>
    api.post<{ authorization_url: string }>("/api/admin/mailboxes/connect", payload),
  updateMailbox: (id: string, payload: MailboxUpdatePayload) =>
    api.patch<AlertMailbox>(`/api/admin/mailboxes/${id}`, payload),
  deleteMailbox: (id: string) => api.delete<void>(`/api/admin/mailboxes/${id}`),
  syncMailbox: (id: string) => api.post<MailboxSyncResult>(`/api/admin/mailboxes/${id}/sync`),
  syncAllMailboxes: () => api.post<MailboxSyncResult[]>("/api/admin/mailboxes/sync"),
};
